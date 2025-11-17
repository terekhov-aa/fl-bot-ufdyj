# FL.ru Order Aggregation Service

Сервис агрегирует заказы с FL.ru: получает их из RSS, обогащает данными от браузерного расширения и предоставляет объединённое API.

## Быстрый старт

1. Скопируйте и настройте переменные окружения:
   ```bash
   cp .env.example .env
   ```
   Отредактируйте `.env`, указав параметры подключения к PostgreSQL и другие настройки.
2. Поднимите инфраструктуру:
   ```bash
   docker-compose up -d
   ```
   Контейнер `db` поднимет PostgreSQL 15.
3. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
4. Примените миграции БД:
   ```bash
   alembic upgrade head
   ```
5. Запустите сервис:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
6. Проверьте документацию API:
   ```
   GET http://localhost:8000/docs
   ```

## Переменные окружения

| Переменная        | Описание                                                         |
|-------------------|------------------------------------------------------------------|
| `DATABASE_URL`    | URL подключения к PostgreSQL (psycopg).                          |
| `RSS_FEED_URL`    | Базовый URL RSS-ленты.                                          |
| `RSS_CATEGORY`    | Дополнительный фильтр `category` (опционально).                 |
| `RSS_SUBCATEGORY` | Дополнительный фильтр `subcategory` (опционально).              |
| `UPLOAD_DIR`      | Абсолютный путь для сохранения вложений.                        |
| `MAX_UPLOAD_MB`   | Максимальный размер загружаемого файла в мегабайтах.            |
| `BROWSERBASE_API_KEY` | API-ключ Browserbase для Stagehand.                         |
| `BROWSERBASE_PROJECT_ID` | Идентификатор проекта Browserbase.                       |
| `MODEL_API_KEY`   | Ключ LLM, используемый Stagehand (OpenAI/Gemini и др.).         |
| `STAGEHAND_MODEL_NAME` | Имя модели для Stagehand (например, `gpt-4o`).            |

## Тесты

```bash
pytest
```

## Примеры запросов

1. Инжест RSS вручную:
   ```bash
   curl -X POST http://localhost:8000/api/rss/ingest \
     -H "Content-Type: application/json" \
     -d '{"feed_url":"https://www.fl.ru/rss/all.xml","category":5,"subcategory":37,"limit":50}'
   ```
2. Метаданные от расширения:
   ```bash
   curl -X POST http://localhost:8000/api/upload \
     -F 'projectData={"id":"5468413","url":"https://www.fl.ru/projects/5468413/foo.html","title":"3D моделирование","links":["https://example.com"],"fileUrls":["https://www.fl.ru/download/.../file.pdf"],"fileNames":["ТЗ.pdf"],"budget":"по договоренности"}' \
     -F 'hasAttachments=true'
   ```
3. Вложение от расширения:
   ```bash
   curl -X POST http://localhost:8000/api/upload \
     -F 'type=attachment' \
     -F 'project_id=5468413' \
     -F 'page_url=https://www.fl.ru/projects/5468413/foo.html' \
     -F 'original_url=https://www.fl.ru/download/.../file.pdf' \
     -F 'filename=TZ.pdf' \
     -F 'file=@/path/to/TZ.pdf'
   ```
4. Получить объединённый заказ:
   ```bash
   curl http://localhost:8000/api/orders/5468413
   ```

## Структура проекта

```
app/
  __init__.py
  main.py
  config.py
  db.py
  models.py
  schemas.py
  rss.py
  routes/
    __init__.py
    ingest.py
    orders.py
    upload.py
  services/
    __init__.py
    orders.py
    storage.py
  utils/
    __init__.py
    parsing.py
    time.py
migrations/
  env.py
  versions/
    202405010001_create_orders_and_attachments.py
uploads/
  .gitkeep
Dockerfile
docker-compose.yml
requirements.txt
.env.example
README.md
```
