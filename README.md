# Мини-синхронизатор заявок

**Живой URL:** https://144-31-229-139.sslip.io/api/clients

Сервис забирает заявки с `https://test.ooobs.ru/api/orders`, нормализует телефоны к `+7XXXXXXXXXX`,
отбрасывает невалидные, дедуплицирует по телефону и отдаёт результат в JSON.

## Правила
- Телефон: оставляем только цифры. 11 цифр, начинающихся с `7` или `8`, → `+7` + 10 цифр.
  10 цифр (без кода страны) → `+7` + 10 цифр. Всё остальное считается невалидным и отбрасывается.
- Дубли по телефону: побеждает запись с максимальным `amount`, при равенстве — более поздняя по `created_at`.
- Статистика: `received` — всего заявок, `invalid_dropped` — невалидные телефоны,
  `unique` — итоговые клиенты, `duplicates_merged` = валидные − уникальные.
- Идемпотентность: каждая синхронизация пересобирает снимок в SQLite (`phone` — PRIMARY KEY)
  в одной транзакции, поэтому повторный запуск даёт тот же результат.

## Если источник недоступен
Отдаётся последний успешный снимок (тело — строго по схеме), а проблема видна сразу в трёх местах:
- заголовки ответа: `X-Sync-Status: ok|stale`, `X-Last-Sync` (время последней успешной синхронизации), `X-Sync-Error`;
- `GET /api/sync/status` — `status`, `last_success_at`, `last_error`, `last_error_at` (удобно для мониторинга);
- лог контейнера: `sync failed, serving last snapshot: ...`.
Если снимка ещё нет вообще — `502`.

## API
| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/clients` (и `/`) | синхронизировать и вернуть `{clients, stats}` |
| POST | `/api/sync` | то же самое |
| GET | `/api/sync/status` | статус последней синхронизации и последняя ошибка |
| GET | `/health` | проверка живости |

```bash
curl https://144-31-229-139.sslip.io/api/clients
curl -sD - -o /dev/null https://144-31-229-139.sslip.io/api/clients | grep -i x-sync
curl https://144-31-229-139.sslip.io/api/sync/status
```

## Секреты
Секретов у сервиса нет: источник публичный. Адрес источника задаётся переменной окружения `SOURCE_URL`
(по умолчанию — URL из задания). Если бы появились ключи, они лежали бы в `.env` на сервере
(он в `.gitignore` и не попадает в репозиторий) и передавались в контейнер через `env_file`.

## Стек и деплой
FastAPI + SQLite, Docker Compose, Caddy (авто-HTTPS через Let's Encrypt), VPS.

- `scripts/server-setup.sh` — однократная подготовка сервера (Docker, порты 80/443).
- Caddy подключён к внешней docker-сети `proxy` и заодно проксирует n8n (`/opt/n8n`, отдельный compose).
  На новом сервере сеть нужно создать один раз: `docker network create proxy`.
- `deploy.conf` — ssh-хост и домен; `./deploy.sh` — заливка на сервер, `docker compose up -d --build`, ожидание `/health`.

Локальный запуск:
```bash
pip install -r requirements.txt
DB_PATH=./data/app.db uvicorn app.main:app --reload
```
