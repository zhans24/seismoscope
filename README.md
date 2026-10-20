# SeismoScope

Веб-система для поиска сейсмических событий, выбора ближайших станций и сравнения их записей. Данные о событиях поступают из USGS, метаданные станций и MiniSEED-записи — из EarthScope FDSN.

## Быстрый запуск

Требования: Docker Desktop (или Docker Engine с Compose v2) и два свободных порта для интерфейса и API.

```bash
cp infra/.env.example infra/.env
docker compose --env-file infra/.env -f infra/docker-compose.yml up --build
```

После запуска откройте:

- интерфейс: http://localhost:5173
- API: http://localhost:8000
- OpenAPI/Swagger: http://localhost:8000/docs
- проверка готовности API: http://localhost:8000/api/v1/health/ready

При первом запуске API автоматически применит миграции PostgreSQL. Исходные MiniSEED-записи и результаты обработки сохраняются в Docker-томах. Redis используется как временный общий кэш ответов USGS и EarthScope; постоянное хранение для него не требуется.

Для запуска в фоне:

```bash
docker compose --env-file infra/.env -f infra/docker-compose.yml up --build --detach
```

Проверить состояние сервисов и посмотреть логи:

```bash
docker compose --env-file infra/.env -f infra/docker-compose.yml ps
docker compose --env-file infra/.env -f infra/docker-compose.yml logs --follow api worker redis
```

Остановить сервисы:

```bash
docker compose --env-file infra/.env -f infra/docker-compose.yml down
```

Команда `down` не удаляет данные PostgreSQL и записи сейсмограмм. Чтобы удалить их намеренно вместе с Docker-томами, используйте `docker compose --env-file infra/.env -f infra/docker-compose.yml down --volumes`.

## Как выполнить анализ

1. На карте задайте период и минимальную магнитуду.
2. Выберите событие из каталога.
3. Отметьте до пяти ближайших станций.
4. При необходимости измените временное окно, частоты фильтра и нормировку.
5. Нажмите «Загрузить и сравнить записи».

На странице результата доступны обработанные графики, характеристики сигнала и оценка времени прихода. Автоматическая оценка прихода является предварительной и требует проверки специалистом.

## Переменные окружения

Конфигурация хранится в `infra/.env` и создаётся на основе `infra/.env.example`.

| Переменная | Назначение |
| --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Параметры PostgreSQL |
| `FRONTEND_PORT` | Внешний порт веб-интерфейса, по умолчанию `5173` |
| `API_PORT` | Внешний порт API, по умолчанию `8000` |
| `DATABASE_URL` | Строка подключения API к PostgreSQL |
| `REDIS_URL` | Строка подключения к Redis, по умолчанию `redis://redis:6379/0` |
| `WAVEFORM_STORAGE_PATH` | Путь хранения MiniSEED внутри контейнера |
| `USGS_EVENT_BASE_URL` | Базовый URL USGS Event API |
| `EARTHSCOPE_BASE_URL` | Базовый URL EarthScope FDSN |
| `LOG_LEVEL` | Уровень журналирования, например `INFO` |
| `EVENT_CACHE_TTL_SECONDS` | Кэш актуального каталога USGS, по умолчанию 5 минут |
| `HISTORICAL_EVENT_CACHE_TTL_SECONDS` | Кэш исторического каталога старше суток, по умолчанию 24 часа |
| `STATION_CACHE_TTL_SECONDS` | Кэш поиска станций EarthScope, по умолчанию 1 час |
| `PLATE_CACHE_TTL_SECONDS` | Кэш границ тектонических плит, по умолчанию 24 часа |
| `STALE_CACHE_TTL_SECONDS` | Срок хранения резервной копии ответа для сбоев источника, по умолчанию 7 суток |

Не добавляйте `infra/.env` в Git: файл уже исключён в `.gitignore`.

## Кэширование Redis

Backend кэширует одинаковые запросы каталога землетрясений, поиска ближайших станций и границ тектонических плит. Ключ учитывает все параметры запроса, поэтому данные разных периодов, стран и фильтров не смешиваются. Одновременные одинаковые запросы защищены короткой блокировкой от массового обращения к внешнему API.

Каждый кэшируемый ответ содержит диагностический заголовок `X-Cache`:

- `MISS` — данные получены у внешнего источника и записаны в Redis;
- `HIT` — результат отдан из актуального кэша;
- `STALE` — источник недоступен, отдана ранее сохранённая копия;
- `BYPASS` — Redis недоступен, запрос выполнен напрямую.

Redis настроен с лимитом памяти 256 МБ и политикой `allkeys-lru`: при заполнении удаляются давно неиспользуемые записи. Отказ Redis не останавливает API, но временно отключает кэш и резервные ответы. Проверить работу можно двумя одинаковыми запросами и сравнением заголовка:

```bash
curl -sS -D - -o /dev/null "http://localhost:8000/api/v1/layers/plate-boundaries"
```

### Порты на сервере

Если на сервере уже работают другие проекты, задайте свободные порты в `infra/.env`, например:

```dotenv
FRONTEND_PORT=5174
API_PORT=8001
```

После запуска интерфейс будет доступен на `http://SERVER_IP:5174`, а API и Swagger — на `http://SERVER_IP:8001` и `http://SERVER_IP:8001/docs`. В текущем выводе `docker ps` порты `5173` и `8000` не заняты, поэтому менять их необязательно.

## Деплой через GitHub Actions

После push автоматически выполняются только проверки изменённых частей проекта. Деплой запускается вручную через **Actions → Deploy SeismoScope → Run workflow**. Он использует SSH-ключ, а не пароль сервера. Для дополнительного подтверждения деплоя создайте в **Settings → Environments** окружение `production`, добавьте себя в **Required reviewers** и оставьте **Prevent self-review** выключенным. Доступность этой настройки зависит от типа репозитория и тарифа GitHub.

Для деплоя можно использовать отдельный SSH-ключ, публичная часть которого добавлена в `/home/ubuntu/.ssh/authorized_keys`. Если такого ключа нет, создайте его на своём компьютере:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/seismoscope_github_actions -C "github-actions-seismoscope"
```

Добавьте содержимое `~/.ssh/seismoscope_github_actions.pub` в `/home/ubuntu/.ssh/authorized_keys` на сервере. Затем в репозитории GitHub откройте **Settings → Secrets and variables → Actions** и создайте:

| Тип | Имя | Значение |
| --- | --- | --- |
| Secret | `DEPLOY_SSH_KEY` | содержимое закрытого ключа `~/.ssh/seismoscope_github_actions` |
| Secret | `DEPLOY_KNOWN_HOSTS` | вывод `ssh-keyscan -H 91.201.214.206` |
| Variable | `DEPLOY_HOST` | `91.201.214.206` |
| Variable | `DEPLOY_USER` | `ubuntu` |
| Variable | `DEPLOY_PATH` | `/var/www/seismoscope` |

На сервере файл `infra/.env` должен быть создан до первого деплоя и не должен попадать в Git. Workflow обновляет существующий Git-клон до выбранного коммита без merge-коммита, сохраняет `infra/.env` и записывает последний успешно развёрнутый коммит в `.deploy-revision`. При следующем деплое он пересобирает только изменённые сервисы. Если изменилась инфраструктура или это первый деплой, пересобираются все сервисы. Docker кеширует зависимости по `pyproject.toml` и `package-lock.json`: правка исходников не скачивает Python- или npm-пакеты заново. Закрытый ключ и пароли не добавляйте ни в репозиторий, ни в комментарии к задачам.

## Если запись станции не найдена

Станция в списке означает, что у неё есть подходящий канал в метаданных EarthScope. Это не гарантирует наличие записи за конкретные минуты: данные могут поступить с задержкой, быть закрытыми или отсутствовать в архиве. В таком случае интерфейс покажет «Нет записи за этот интервал» для конкретной станции; выберите другую станцию или повторите запрос позже.

## Проверки

Проверка сборки фронтенда:

```bash
docker compose --env-file infra/.env -f infra/docker-compose.yml build frontend
```

Тесты обработки ответов EarthScope:

```bash
docker compose --env-file infra/.env -f infra/docker-compose.yml run --rm --no-deps \
  -v "$PWD/backend/tests:/app/tests" api \
  python -m unittest discover -s tests -v
```
