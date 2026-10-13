# Service

Прод: https://test.example.com

## Что делает
_(заполнить после выполнения задания)_

## API
| Метод | Путь | Описание |
|---|---|---|
| GET | `/health` | проверка живости |
| GET | `/api/items` | список |
| POST | `/api/items` | создать `{"text": "..."}` |
| DELETE | `/api/items/{id}` | удалить |

## Запуск локально
```bash
pip install -r requirements.txt
DB_PATH=./data/app.db uvicorn app.main:app --reload
```

## Деплой
```bash
./deploy.sh
```
Стек: FastAPI + SQLite, Docker Compose, Caddy (авто-HTTPS).
