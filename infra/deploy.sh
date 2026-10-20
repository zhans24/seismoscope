#!/usr/bin/env bash
set -euo pipefail

revision=${1:?missing revision}
if [[ ! "$revision" =~ ^[0-9a-f]{40}$ ]] || [[ "$(git rev-parse HEAD)" != "$revision" ]]; then
    echo "Deployment revision does not match the checked-out commit" >&2
    exit 1
fi

previous=''
if [[ -f .deploy-revision ]]; then
    previous=$(< .deploy-revision)
fi
if [[ "$previous" =~ ^[0-9a-f]{40}$ ]] && git cat-file -e "${previous}^{commit}" 2>/dev/null; then
    changed=$(git diff --name-only "$previous" "$revision")
else
    changed=$'backend/\nfrontend/\ninfra/'
fi

backend_changed=0
frontend_changed=0
infrastructure_changed=0
while IFS= read -r path; do
    case "$path" in
        backend/*) backend_changed=1 ;;
        frontend/*) frontend_changed=1 ;;
        infra/*) infrastructure_changed=1 ;;
    esac
done <<< "$changed"

echo "Changes: backend=$backend_changed frontend=$frontend_changed infra=$infrastructure_changed"
compose=(docker compose --env-file infra/.env -f infra/docker-compose.yml)

if [[ "$infrastructure_changed" == 1 ]]; then
    "${compose[@]}" up --build --detach --remove-orphans
else
    if [[ "$backend_changed" == 1 ]]; then
        "${compose[@]}" build api worker
        "${compose[@]}" up --detach --no-deps api worker
    fi
    if [[ "$frontend_changed" == 1 ]]; then
        "${compose[@]}" build frontend
        "${compose[@]}" up --detach --no-deps frontend
    fi
fi

printf '%s\n' "$revision" > .deploy-revision.tmp
mv .deploy-revision.tmp .deploy-revision
