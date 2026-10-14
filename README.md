# SeismoScope

Веб-система для поиска сейсмических событий, выбора ближайших станций и сравнения их записей. Данные о событиях поступают из USGS, метаданные станций и MiniSEED-записи — из EarthScope FDSN.

## Быстрый запуск

Требования: Docker Desktop (или Docker Engine с Compose v2) и свободные порты `5173` и `8000`.

```bash
cp infra/.env.example infra/.env
docker compose --env-file infra/.env -f infra/docker-compose.yml up --build
```

После запуска откройте:

- интерфейс: http://localhost:5173
- API: http://localhost:8000
- OpenAPI/Swagger: http://localhost:8000/docs
- проверка готовности API: http://localhost:8000/api/v1/health/ready

При первом запуске API автоматически применит миграции PostgreSQL. Исходные MiniSEED-записи и результаты обработки сохраняются в Docker-томах.

Для запуска в фоне:

```bash
docker compose --env-file infra/.env -f infra/docker-compose.yml up --build --detach
```

Проверить состояние сервисов и посмотреть логи:

```bash
docker compose --env-file infra/.env -f infra/docker-compose.yml ps
docker compose --env-file infra/.env -f infra/docker-compose.yml logs --follow api worker
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
| `DATABASE_URL` | Строка подключения API к PostgreSQL |
| `WAVEFORM_STORAGE_PATH` | Путь хранения MiniSEED внутри контейнера |
| `USGS_EVENT_BASE_URL` | Базовый URL USGS Event API |
| `EARTHSCOPE_BASE_URL` | Базовый URL EarthScope FDSN |
| `LOG_LEVEL` | Уровень журналирования, например `INFO` |

Не добавляйте `infra/.env` в Git: файл уже исключён в `.gitignore`.

## Если запись станции не найдена

Станция в списке означает, что у неё есть подходящий канал в метаданных EarthScope. Это не гарантирует наличие записи за конкретные минуты: данные могут поступить с задержкой, быть закрытыми или отсутствовать в архиве. В таком случае интерфейс покажет «Нет записи за этот интервал» для конкретной станции; выберите другую станцию или повторите запрос позже.

## Проверки

Сборка фронтенда:

```bash
docker compose --env-file infra/.env -f infra/docker-compose.yml exec frontend npm run build
```

Тесты обработки ответов EarthScope:

```bash
docker compose --env-file infra/.env -f infra/docker-compose.yml run --rm --no-deps \
  -v "$PWD/backend/tests:/app/tests" api \
  python -m unittest discover -s tests -v
```
