# LightRAG Local

Полнофункциональная система **RAG (Retrieval-Augmented Generation)** для локального использования в **полностью закрытых средах** (air-gapped, без интернета).

Всё работает локально: LLM, embeddings, reranker, БД, парсинг документов. Можно развернуть на машине без доступа в интернет.

---

## 🌟 Возможности

- **Гибридный поиск** — комбинирует вектор-поиск, полнотекстовый поиск (PGroonga) и граф (Neo4j)
- **Фразовый поиск** — "кавычки" для точного совпадения (новое в PGroonga)
- **Поддержка аббревиатур** — ОАО, НМСК и т.п. — ищут как есть, без стемминга
- **Многоязычный поиск** — русский + английский в одном индексе
- **Граф знаний** — автоматическое извлечение сущностей и связей в Neo4j
- **Расширение запроса** — LLM переформулирует вопросы для лучшего поиска
- **Переранжирование** — кросс-энкодер улучшает релевантность результатов
- **100% локально** — никакие запросы не уходят в облако
- **Множество форматов** — PDF, DOCX, TXT, MD, HTML (Apache Tika)

---

## 📋 Таблица совместимости с интернетом

| Компонент | Требует интернета? | Способ работы |
|---|---|---|
| API (FastAPI) | **НЕТ** | Локально в контейнере |
| LLM | **НЕТ** | llama.cpp сервер (локальный) |
| Embeddings | **НЕТ** | Qwen3-Embedding-0.6B (llama.cpp) |
| Reranker | **НЕТ** | BGE-reranker-v2-m3 (llama.cpp) |
| PostgreSQL | **НЕТ** | Локальная БД, PGroonga FTS |
| Neo4j | **НЕТ** | Локальный граф |
| Tika (парсинг) | **НЕТ** | Локальный сервис |
| OpenRouter fallback | **ДА** | Опционально (разработка) |

**Вывод:** ✅ **Да, работает полностью без интернета.** OpenRouter используется только если явно включён в .env для разработки.

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI                                  │
│                    /api/v1/ingest, /api/v1/search                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│ Vector Search  │  │  Full-Text     │  │   GraphRAG     │
│  (pgvector)    │  │   Search       │  │   (LightRAG)   │
│  HNSW индекс   │  │  (PGroonga)    │  │   (Neo4j)      │
│  cosine dist   │  │  Groonga query │  │   Entity links │
└────────────────┘  └────────────────┘  └────────────────┘
        │                  │                  │
        └──────────────────┴──────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Reranker   │
                    │ BGE-v2-m3   │
                    │(llama.cpp)  │
                    └─────────────┘
                           │
                    ┌──────▼──────┐
                    │  Result     │
                    │  Fusion     │
                    │  (RRF)      │
                    └─────────────┘
```

---

## 🚀 Быстрый старт

### 1. Подготовка моделей

Моделей нужно скачать один раз. Они весят ~2.5GB в сумме.

```bash
# Создать директорию для моделей
mkdir -p models

# Скачать embedding модель (0.6B параметров)
huggingface-cli download Qwen/Qwen3-Embedding-0.6B \
    --local-dir models/embeddings

# Скачать reranker модель
huggingface-cli download BAAI/bge-reranker-v2-m3 \
    --local-dir models/reranker

# Скачать LLM модель (здесь Qwen 0.5B для примера)
# Или любой GGUF формат: Llama, Mistral, Phi-3, и т.п.
huggingface-cli download Qwen/Qwen2.5-0.5B-Instruct-GGUF \
    --local-dir models/llm
```

После этого в директориях будут `.gguf` файлы моделей.

### 2. Конфигурация

```bash
# Скопировать пример конфига
cp .env.example .env

# Отредактировать .env (опционально)
# Главное: USE_OPENROUTER=false для offline режима
```

### 3. Запуск контейнеров

```bash
# Поднять всё (API, БД, LLM сервисы)
docker-compose up -d

# Проверить статус
docker-compose ps

# Смотреть логи API
docker-compose logs -f api

# Смотреть логи LLM (для отладки)
docker-compose logs -f llamacpp-llm
```

### 4. Загрузить данные

#### Вариант 1: Через Python CLI

```bash
# Один документ
python scripts/client_ingest.py documents/report.pdf --workspace my_project

# Папка документов (batch)
python scripts/client_ingest.py documents/ --batch --workspace my_project

# С кастомными метаданными
python scripts/client_ingest.py doc.pdf --workspace my_project \
    --metadata '{"category": "finance", "year": 2024}'
```

#### Вариант 2: Через API (curl)

```bash
# Загрузить один файл
curl -X POST http://localhost:18000/api/v1/ingest \
    -F "file=@documents/report.pdf" \
    -F "workspace_name=my_project" \
    -F "extract_entities=true"

# Ответ:
# {
#   "document_id": "550e8400-e29b-41d4-a716-446655440000",
#   "filename": "report.pdf",
#   "status": "completed",
#   "chunk_count": 42,
#   "entity_count": 15
# }
```

### 5. Поиск

#### Вариант 1: Python CLI

```bash
# Гибридный поиск (по умолчанию)
python scripts/client_search.py "Что такое ОАО?" --workspace my_project

# Фразовый поиск (новое!)
python scripts/client_search.py '"Григорий Баженов"' --workspace my_project

# Только полнотекстовый с булевыми операторами
python scripts/client_search.py 'ОАО AND экспорт' --mode fts

# Исключение (NOT)
python scripts/client_search.py 'ОАО -импорт' --mode fts

# Только вектор-поиск (семантика)
python scripts/client_search.py "финансовые показатели" --mode vector

# Только граф
python scripts/client_search.py "Кто работает в компании?" --mode graph
```

#### Вариант 2: Через API (curl или Python requests)

```bash
# Гибридный поиск с полной конфигурацией
curl -X POST http://localhost:18000/api/v1/search \
    -H "Content-Type: application/json" \
    -d '{
        "query": "Какие кварталы показали рост?",
        "workspace_name": "my_project",
        "mode": "hybrid",
        "use_vector": true,
        "use_fts": true,
        "use_graph": true,
        "expand_query": true,
        "rerank": true,
        "top_k": 10,
        "rerank_top_k": 5,
        "vector_weight": 0.5,
        "fts_weight": 0.3,
        "graph_weight": 0.2
    }'

# Фразовый поиск с точным совпадением
curl -X POST http://localhost:18000/api/v1/search \
    -H "Content-Type: application/json" \
    -d '{
        "query": "\"Григорий Баженов\"",
        "workspace_name": "my_project",
        "mode": "fts",
        "top_k": 5
    }'
```

---

## 📁 Структура проекта

```
light_rag_local/
├── README.md                    # Этот файл
├── docker-compose.yml           # Конфигурация контейнеров
├── Dockerfile                   # FastAPI приложение
├── Dockerfile.tika              # Apache Tika для парсинга
├── requirements.txt             # Python зависимости
│
├── .env                         # Конфигурация (НЕ коммитить!)
├── .env.example                 # Шаблон конфигурации
│
├── models/                      # Локальные модели (~2.5GB)
│   ├── llm/                     # LLM GGUF (Qwen, Llama, etc)
│   ├── embeddings/              # Qwen3-Embedding-0.6B
│   └── reranker/                # BGE-reranker-v2-m3
│
├── data/
│   └── uploads/                 # Загруженные файлы (хранилище)
│
├── app/                         # FastAPI приложение
│   ├── main.py                  # Точка входа (FastAPI app)
│   ├── config.py                # Конфигурация (settings)
│   ├── dependencies.py          # DI контейнер (инициализация сервисов)
│   │
│   ├── api/
│   │   ├── routes/
│   │   │   ├── ingest.py        # POST /api/v1/ingest (загрузка документов)
│   │   │   └── search.py        # POST /api/v1/search (поиск)
│   │   └── schemas/
│   │       ├── ingest.py        # Pydantic модели для ingestion
│   │       └── search.py        # Pydantic модели для search
│   └── __init__.py
│
├── core/                        # Основная RAG логика
│   ├── document_processor.py    # Парсинг, чанкинг, токенизация
│   ├── hybrid_search.py         # Оркестрация трёх видов поиска
│   ├── lightrag_engine.py       # Извлечение сущностей, граф поиск
│   ├── query_expansion.py       # Расширение запроса через LLM
│   └── __init__.py
│
├── services/                    # Внешние сервисы (обёртки)
│   ├── llm_service.py           # LLM inference (llama.cpp + fallback OpenRouter)
│   ├── embedding_service.py     # Embeddings (Qwen3, llama.cpp)
│   ├── reranker_service.py      # Переранжирование (BGE, llama.cpp)
│   ├── tika_service.py          # Парсинг документов (Apache Tika)
│   └── __init__.py
│
├── db/                          # Database слой
│   ├── postgres/
│   │   ├── connection.py        # asyncpg пулинг
│   │   ├── vector_store.py      # Vector search (HNSW + pgvector)
│   │   ├── fts_store.py         # **Full-text search (PGroonga)**
│   │   └── init.sql             # DDL: таблицы, индексы, функции
│   │
│   ├── neo4j/
│   │   ├── connection.py        # Neo4j драйвер
│   │   └── graph_store.py       # Граф операции (CRUD сущностей/связей)
│   └── __init__.py
│
├── scripts/                     # Клиентские утилиты
│   ├── client_ingest.py         # CLI для загрузки документов
│   ├── client_search.py         # CLI для поиска
│   └── __init__.py
│
├── tests/
│   ├── test_api.py
│   └── __init__.py
│
└── testdata/                    # Примеры документов (русский текст)
    ├── Григорий_Баженов_part_001.md
    ├── Григорий_Баженов_part_002.md
    └── ...
```

---

## 🔍 Подробно про поиск

### PGroonga (Полнотекстовый поиск)

**Файл:** `db/postgres/fts_store.py`

PGroonga — это расширение PostgreSQL на базе Groonga (японской поисковой машины). Вместо старого tsvector теперь используется `&@~` оператор с синтаксисом Groonga.

#### Синтаксис запросов Groonga:

```bash
# Простые слова → AND (неявный)
python scripts/client_search.py "ОАО экспорт" --mode fts
# → поиск документов со словами ОАО И экспорт

# Фраза в кавычках → точное совпадение
python scripts/client_search.py '"Григорий Баженов"' --mode fts
# → только этот порядок слов

# OR оператор
python scripts/client_search.py "ОАО OR компания" --mode fts
# → ОАО или компания (или оба)

# NOT (исключение) → минус перед словом
python scripts/client_search.py "ОАО -импорт" --mode fts
# → ОАО, но без импорта

# Комбо: фраза + ключевое слово
python scripts/client_search.py '"Григорий Баженов" ОАО' --mode fts
# → точная фраза "Григорий Баженов" И слово ОАО
```

#### Преимущества над tsvector:

| Свойство | tsvector | PGroonga |
|----------|----------|----------|
| "Кавычки" | Нет (срезались) | ✅ Да |
| Аббревиатуры | Стемминг → искажение | ✅ TokenICU, без стемминга |
| Русский + английский | Нужны два tsvector | ✅ Один индекс |
| Булевы операторы | Нет | ✅ OR, AND, NOT, () |
| Фраза поиск | phraseto_tsquery, но ненадёжно | ✅ Встроено в синтаксис |

### Vector Search (Семантический поиск)

**Файл:** `db/postgres/vector_store.py`

- **Модель:** Qwen3-Embedding-0.6B (1024 размерность)
- **Индекс:** HNSW (иерархические малые миры)
- **Метрика:** cosine distance
- **Скорость:** ~1ms для поиска (благодаря HNSW)

```bash
python scripts/client_search.py "финансовые инвестиции" --mode vector
# → найдёт документы с похожим смыслом, даже если слова другие
```

### GraphRAG (LightRAG, Neo4j)

**Файл:** `core/lightrag_engine.py`, `db/neo4j/graph_store.py`

LLM автоматически извлекает из документов:
- **Сущности:** люди, организации, места, события
- **Связи:** работает в, расположена в, связана с, и т.п.

Хранится в Neo4j для обхода графа.

```bash
# Поиск по сущностям и их окружению
python scripts/client_search.py "Кто связан с ОАО?" --mode graph
```

### Гибридный поиск (Hybrid)

Комбинирует три вида поиска с взвешиванием:

```python
score = (vector_score * 0.5) + (fts_score * 0.3) + (graph_score * 0.2)
```

Веса настраиваются в запросе:

```bash
curl -X POST http://localhost:18000/api/v1/search \
    -H "Content-Type: application/json" \
    -d '{
        "query": "ОАО экспорт",
        "mode": "hybrid",
        "vector_weight": 0.4,  # вектор важнее
        "fts_weight": 0.4,     # FTS тоже важен
        "graph_weight": 0.2    # граф меньше влияет
    }'
```

---

## ⚙️ Конфигурация

### Основные переменные в `.env`

| Переменная | Значение | Описание |
|---|---|---|
| `APP_ENV` | `production` / `development` | Режим приложения |
| `DEBUG` | `true` / `false` | Debug логи |
| `LOG_LEVEL` | `INFO`, `DEBUG`, `WARNING` | Уровень логирования |
| `USE_OPENROUTER` | `false` (для offline) | Использовать облако LLM |
| `CHUNK_SIZE` | `512` | Токены на чанк |
| `CHUNK_OVERLAP` | `50` | Перекрытие чанков |
| `DEFAULT_TOP_K` | `10` | Результаты по умолчанию |
| `RERANK_TOP_K` | `5` | После переранжирования |

### Для offline режима (воздушный зазор)

```bash
# .env
USE_OPENROUTER=false          # Выключить облако

# Все остальное локально:
# - LLM_API_URL указывает на контейнер llama.cpp
# - EMBEDDING_API_URL то же самое
# - RERANKER_API_URL то же самое
# - Postgres, Neo4j локальные
```

### Для разработки с OpenRouter (опционально)

```bash
USE_OPENROUTER=true
OPENROUTER_API_KEY=sk-or-v1-xxxx
OPENROUTER_MODEL=deepseek/deepseek-r1
```

---

## 🐳 Docker контейнеры

Все контейнеры уже настроены в `docker-compose.yml`. Что запускается:

### Основной контейнер

- **lightrag-api** — FastAPI приложение (порт 18000)

### LLM сервисы (llama.cpp)

- **lightrag-llamacpp-llm** — LLM inference (порт 8081)
- **lightrag-llamacpp-embeddings** — Embeddings (порт 8082)
- **lightrag-llamacpp-reranker** — Reranker (порт 8083)

### БД

- **lightrag-postgres** — PostgreSQL + PGroonga (порт 15432)
- **lightrag-neo4j** — Neo4j (порт 17474 браузер, 17687 болт)
- **lightrag-tika** — Apache Tika парсер (порт 9999)

### Управление

```bash
# Поднять всё
docker-compose up -d

# Проверить
docker-compose ps

# Логи
docker-compose logs -f api
docker-compose logs -f postgres
docker-compose logs -f neo4j

# Остановить
docker-compose down

# Удалить всё включая БД
docker-compose down -v
```

---

## 🔌 API эндпоинты

### POST /api/v1/ingest

Загрузить и обработать документ.

**Запрос (multipart/form-data):**

```
file: @document.pdf
workspace_name: my_project
extract_entities: true
custom_metadata: {"category": "finance"}
```

**Ответ:**

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.pdf",
  "status": "completed",
  "chunk_count": 42,
  "entity_count": 15,
  "relationship_count": 8,
  "processing_time_ms": 5432
}
```

### POST /api/v1/search

Выполнить поиск (гибридный или специфичный).

**Запрос:**

```json
{
  "query": "ОАО AND экспорт",
  "workspace_name": "my_project",
  "mode": "hybrid",
  "use_vector": true,
  "use_fts": true,
  "use_graph": true,
  "expand_query": true,
  "rerank": true,
  "top_k": 10,
  "rerank_top_k": 5,
  "vector_weight": 0.5,
  "fts_weight": 0.3,
  "graph_weight": 0.2,
  "lightrag_mode": "hybrid"
}
```

**Ответ:**

```json
{
  "query": "ОАО AND экспорт",
  "mode": "hybrid",
  "results": [
    {
      "chunk_id": "uuid",
      "content": "ОАО занимается экспортом...",
      "score": 0.85,
      "source": {
        "document_id": "uuid",
        "filename": "document.pdf",
        "chunk_index": 3
      },
      "vector_score": 0.82,
      "fts_score": 0.90,
      "graph_score": 0.75,
      "rerank_score": 0.87,
      "highlighted_content": "...&lt;mark&gt;ОАО&lt;/mark&gt; занимается &lt;mark&gt;экспортом&lt;/mark&gt;..."
    }
  ],
  "total_results": 1,
  "search_time_ms": 234,
  "vector_search_time_ms": 45,
  "fts_search_time_ms": 67,
  "graph_search_time_ms": 89,
  "rerank_time_ms": 33
}
```

### Другие эндпоинты

```
POST /api/v1/search/vector          — Только вектор-поиск
POST /api/v1/search/fts             — Только FTS
POST /api/v1/search/graph           — Только граф
GET  /api/v1/search/suggest?query=  — Подсказки автодополнения
GET  /api/v1/entities/{workspace}   — Список сущностей из графа
GET  /health                        — Здоровье сервиса
```

---

## 🖥️ Локальная разработка (без контейнеров)

Если нужно разрабатывать на хосте:

```bash
# 1. Создать venv
python -m venv venv
source venv/bin/activate

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Поднять только БД в контейнерах
docker-compose up -d postgres neo4j tika
docker-compose up -d llamacpp-llm llamacpp-embeddings llamacpp-reranker

# 4. Проверить что БД запущена
psql -h localhost -p 15432 -U lightrag -d lightrag -c "SELECT version();"

# 5. Инициализировать БД (первый раз)
psql -h localhost -p 15432 -U lightrag -d lightrag -f db/postgres/init.sql

# 6. Запустить FastAPI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Теперь API доступен на http://localhost:8000

---

## 🧪 Тестирование

### Запустить тесты

```bash
pytest tests/ -v
pytest tests/test_api.py -v -s
```

### Проверить здоровье сервиса

```bash
curl http://localhost:18000/health
# → {"status": "healthy", "timestamp": "2024-..."}
```

### Проверить БД

```bash
# PostgreSQL
psql -h localhost -p 15432 -U lightrag -c "SELECT * FROM documents LIMIT 1;"

# Neo4j браузер
# http://localhost:17474
# User: neo4j, Password: neo4j_secure_password
```

---

## 📊 Мониторинг

### Логи контейнеров

```bash
# API
docker-compose logs -f api

# LLM сервис
docker-compose logs -f llamacpp-llm

# PostgreSQL
docker-compose logs -f postgres

# Neo4j
docker-compose logs -f neo4j
```

### Размер БД

```bash
# Объём данных Postgres
docker-compose exec postgres psql -U lightrag -c \
    "SELECT pg_database.datname, pg_size_pretty(pg_database_size(pg_database.datname)) \
    FROM pg_database WHERE datname='lightrag';"

# Объём Neo4j
docker-compose exec neo4j cypher "CALL db.info()" | grep size
```

---

## 🌐 Сетевые порты

| Сервис | Локальный порт | Контейнерный порт | Использование |
|---|---|---|---|
| API (FastAPI) | 18000 | 8000 | HTTP запросы |
| LLM (llama.cpp) | 8081 | 8080 | Только внутри контейнеров |
| Embeddings | 8082 | 8080 | Только внутри контейнеров |
| Reranker | 8083 | 8080 | Только внутри контейнеров |
| PostgreSQL | 15432 | 5432 | psql клиент, DBeaver и т.п. |
| Neo4j Browser | 17474 | 7474 | Вебинтерфейс |
| Neo4j Bolt | 17687 | 7687 | Драйверы, Cypher запросы |
| Tika | 9999 | 9998 | Внутри контейнеров |

---

## 🔒 Безопасность

### Для production

```bash
# .env
DEBUG=false
APP_ENV=production

# Изменить пароли по умолчанию!
POSTGRES_PASSWORD=ваш_сложный_пароль
NEO4J_PASSWORD=ваш_сложный_пароль

# Использовать https/TLS
# (Примечание: нужен реверс-прокси типа nginx)
```

### Изоляция сети

Все контейнеры работают в приватной сети `lightrag-network`. API доступен только на 18000 порту.

---

## 🐛 Troubleshooting

### "Connection refused" при старте API

```bash
# API ждёт БД. Проверить что Postgres запущен
docker-compose ps

# Если Postgres не здоров:
docker-compose logs postgres

# Перезагрузить Postgres
docker-compose restart postgres
```

### PGroonga не работает / ошибка индекса

```bash
# Проверить что индекс был создан
docker-compose exec postgres psql -U lightrag -d lightrag -c \
    "SELECT * FROM pg_indexes WHERE tablename='chunks';"

# Пересоздать индекс (если нужно)
docker-compose exec postgres psql -U lightrag -d lightrag -c \
    "DROP INDEX IF EXISTS idx_chunks_pgroonga; \
    CREATE INDEX idx_chunks_pgroonga ON chunks \
    USING pgroonga (content pgroonga_text_full_text_search_ops_v2) \
    WITH (tokenizer = 'TokenICU(\"default\")');"
```

### Медленный поиск

- Проверить индексы: `SELECT * FROM pg_stat_user_indexes WHERE schemaname='public';`
- Увеличить память PostgreSQL в docker-compose.yml
- Снизить `top_k` значение (получать меньше результатов)

### LLM сервис не отвечает

```bash
# Проверить логи llama.cpp
docker-compose logs llamacpp-llm

# Убедиться что модель загружена
ls -lh models/llm/*.gguf

# Перезагрузить
docker-compose restart llamacpp-llm
```

---

---

## 📤 Загрузка данных — все варианты

### Поддерживаемые форматы

| Формат | Расширение | Поддержка | Примечание |
|---|---|---|---|
| PDF | `.pdf` | ✅ Отлично | Включая отсканированные (OCR) |
| Word | `.docx`, `.doc` | ✅ Отлично | С таблицами и форматированием |
| Текст | `.txt` | ✅ Отлично | Простой текст |
| Markdown | `.md` | ✅ Отлично | С заголовками и списками |
| HTML | `.html`, `.htm` | ✅ Отлично | Веб-страницы |
| RTF | `.rtf` | ✅ Хорошо | Rich Text Format |
| JSON | `.json` | ✅ Можно | Парсится как текст |

Парсинг делает Apache Tika, он поддерживает 100+ форматов.

### Вариант 1: CLI загрузка (Python скрипт)

#### 1a. Один файл

```bash
# Простая загрузка
python scripts/client_ingest.py documents/report.pdf

# С workspace'ом (проектом)
python scripts/client_ingest.py documents/report.pdf --workspace my_project

# С метаданными
python scripts/client_ingest.py documents/report.pdf \
    --workspace my_project \
    --metadata '{"category": "finance", "year": 2024, "author": "John"}'

# Без извлечения сущностей (быстрее)
python scripts/client_ingest.py documents/report.pdf \
    --workspace my_project \
    --no-entities
```

#### 1b. Папка документов (batch)

```bash
# Загрузить всё из папки рекурсивно
python scripts/client_ingest.py ./documents --batch --workspace reports_2024

# С фильтром по расширению (например, только PDF)
python scripts/client_ingest.py ./documents --batch --workspace reports_2024 --pattern "*.pdf"

# Тихий режим (без логов)
python scripts/client_ingest.py ./documents --batch --workspace reports_2024 --quiet

# Параллельная загрузка (4 потока)
python scripts/client_ingest.py ./documents --batch --workspace reports_2024 --workers 4
```

#### 1c. Разные типы файлов в одной команде

```bash
# PDF документы
python scripts/client_ingest.py ./pdfs --batch --workspace archive

# Word документы
python scripts/client_ingest.py ./word_docs --batch --workspace archive

# Markdown файлы
python scripts/client_ingest.py ./markdown --batch --workspace wiki

# HTML страницы
python scripts/client_ingest.py ./html_exports --batch --workspace web_pages

# Все вместе в одну папку
python scripts/client_ingest.py ./all_documents --batch --workspace everything
```

### Вариант 2: API загрузка (curl)

#### 2a. Один файл через curl

```bash
# Базовая загрузка
curl -X POST http://localhost:18000/api/v1/ingest \
    -F "file=@documents/report.pdf"

# С workspace'ом
curl -X POST http://localhost:18000/api/v1/ingest \
    -F "file=@documents/report.pdf" \
    -F "workspace_name=my_project"

# С метаданными
curl -X POST http://localhost:18000/api/v1/ingest \
    -F "file=@documents/report.pdf" \
    -F "workspace_name=my_project" \
    -F "custom_metadata={\"department\": \"Finance\", \"date\": \"2024-01-15\"}"

# Без извлечения сущностей
curl -X POST http://localhost:18000/api/v1/ingest \
    -F "file=@documents/report.pdf" \
    -F "extract_entities=false"

# С кастомными размерами чанков
curl -X POST http://localhost:18000/api/v1/ingest \
    -F "file=@documents/report.pdf" \
    -F "chunk_size=256" \
    -F "chunk_overlap=32"
```

#### 2b. Несколько файлов через curl (скрипт bash)

```bash
#!/bin/bash

WORKSPACE="documents_batch"
API="http://localhost:18000/api/v1/ingest"

# Загрузить все файлы из папки
for file in ./documents/*; do
    echo "Загружаю: $file"
    curl -X POST "$API" \
        -F "file=@$file" \
        -F "workspace_name=$WORKSPACE"
    echo "✓ Done"
done
```

#### 2c. Word документ через API

```bash
curl -X POST http://localhost:18000/api/v1/ingest \
    -F "file=@./reports/quarterly_report.docx" \
    -F "workspace_name=quarterly_reports" \
    -F "custom_metadata={\"quarter\": \"Q1\", \"year\": 2024}"
```

#### 2d. HTML файл

```bash
curl -X POST http://localhost:18000/api/v1/ingest \
    -F "file=@./pages/company_page.html" \
    -F "workspace_name=website_content"
```

### Вариант 3: Python requests (программно)

```python
import requests
import json

API_URL = "http://localhost:18000/api/v1/ingest"

def upload_document(file_path, workspace="default", metadata=None):
    """Загрузить документ через API"""

    with open(file_path, 'rb') as f:
        files = {'file': f}
        data = {
            'workspace_name': workspace,
            'extract_entities': 'true',
        }
        if metadata:
            data['custom_metadata'] = json.dumps(metadata)

        response = requests.post(API_URL, files=files, data=data)
        return response.json()

# Пример 1: Загрузить PDF
result = upload_document(
    './documents/report.pdf',
    workspace='finance',
    metadata={'year': 2024, 'quarter': 'Q1'}
)
print(f"✓ Загружен: {result['document_id']}")
print(f"  Чанков: {result['chunk_count']}")
print(f"  Сущностей: {result['entity_count']}")

# Пример 2: Загрузить папку
import os
from pathlib import Path

docs_dir = Path('./documents')
for file_path in docs_dir.glob('**/*.pdf'):  # Только PDF
    result = upload_document(file_path, workspace='archive')
    print(f"✓ {file_path.name} → {result['status']}")

# Пример 3: Загрузить с прогресс-баром
from tqdm import tqdm

files = list(Path('./documents').glob('*'))
for file_path in tqdm(files, desc="Загрузка"):
    try:
        upload_document(file_path, workspace='batch')
    except Exception as e:
        print(f"✗ Ошибка: {file_path.name} - {e}")
```

### Вариант 4: Docker прямо из контейнера

```bash
# Скопировать файлы в контейнер
docker cp ./documents/report.pdf lightrag-api:/tmp/

# Выполнить ingestion внутри контейнера
docker exec lightrag-api python scripts/client_ingest.py /tmp/report.pdf --workspace imported

# Или через mount: добавить в docker-compose.yml
#   volumes:
#     - ./documents:/app/documents:ro
# Потом:
docker exec lightrag-api python scripts/client_ingest.py /app/documents --batch --workspace mounted
```

### Чек-лист загрузки

```bash
# 1. Проверить что API работает
curl http://localhost:18000/health
# → {"status": "healthy"}

# 2. Проверить что файл существует
ls -lh documents/report.pdf

# 3. Загрузить
python scripts/client_ingest.py documents/report.pdf --workspace test

# 4. Проверить в БД
docker exec lightrag-postgres psql -U lightrag -d lightrag -c \
    "SELECT filename, chunk_count, status FROM documents WHERE filename LIKE '%report%';"

# 5. Проверить в Neo4j
docker exec lightrag-neo4j cypher "MATCH (e:Entity) RETURN COUNT(e) as entity_count;"
```

---

## 🔎 Поиск — все варианты

### Сценарий 1: Простой текстовый поиск

```bash
# Ключевое слово
python scripts/client_search.py "экспорт" --workspace reports

# Несколько слов (AND)
python scripts/client_search.py "ОАО экспорт" --workspace reports

# Результаты ограничение
python scripts/client_search.py "ОАО" --workspace reports --top-k 20
```

**API эквивалент:**
```bash
curl -X POST http://localhost:18000/api/v1/search \
    -H "Content-Type: application/json" \
    -d '{
        "query": "ОАО экспорт",
        "workspace_name": "reports",
        "mode": "hybrid",
        "top_k": 20
    }'
```

---

### Сценарий 2: Фразовый поиск (точное совпадение)

```bash
# Найти точную фразу в кавычках
python scripts/client_search.py '"Григорий Баженов"' --workspace documents --mode fts

# Фраза + слово
python scripts/client_search.py '"компания АБВ" экспорт' --workspace documents --mode fts

# Длинная фраза
python scripts/client_search.py '"Квартальный доход составил 1.5 млн рублей"' --workspace reports --mode fts
```

**Groonga синтаксис в API:**
```bash
curl -X POST http://localhost:18000/api/v1/search \
    -H "Content-Type: application/json" \
    -d '{
        "query": "\"Григорий Баженов\" экспорт",
        "workspace_name": "documents",
        "mode": "fts",
        "top_k": 10
    }'
```

---

### Сценарий 3: Булевы операторы (FTS)

#### OR (альтернатива)

```bash
# ОАО ИЛИ компания
python scripts/client_search.py "ОАО OR компания" --workspace reports --mode fts

# С кавычками
python scripts/client_search.py '"ООО Рога и Копыта" OR "ООО Пиковая Дама"' --workspace reports --mode fts

# Три варианта
python scripts/client_search.py "экспорт OR импорт OR реэкспорт" --workspace reports --mode fts
```

#### NOT (исключение)

```bash
# ОАО, но без импорта
python scripts/client_search.py "ОАО -импорт" --workspace reports --mode fts

# С фразой
python scripts/client_search.py '"ООО СООИсх" -"филиал"' --workspace reports --mode fts

# Несколько исключений
python scripts/client_search.py "ОАО -филиал -представительство -агентство" --workspace reports --mode fts
```

#### Комбинированно

```bash
# (ОАО OR ООО) И экспорт, но не импорт
python scripts/client_search.py '"ОАО" OR "ООО" экспорт -импорт' --workspace reports --mode fts

# ОАО И (экспорт ИЛИ импорт)
python scripts/client_search.py 'ОАО (экспорт OR импорт)' --workspace reports --mode fts
```

---

### Сценарий 4: Семантический поиск (вектор)

```bash
# Поиск по смыслу (даже если слова другие)
python scripts/client_search.py "финансовые показатели компании" --workspace reports --mode vector

# Вопрос
python scripts/client_search.py "Какие были выручка и прибыль?" --workspace reports --mode vector

# Описание
python scripts/client_search.py "основная деятельность и направления развития" --workspace reports --mode vector

# Много результатов для семантического поиска
python scripts/client_search.py "инвестиции" --workspace reports --mode vector --top-k 50
```

---

### Сценарий 5: Граф-поиск (Neo4j)

```bash
# Найти сущности и их связи
python scripts/client_search.py "Кто работает в компании?" --workspace documents --mode graph

# Найти организации
python scripts/client_search.py "ООО" --workspace documents --mode graph

# Найти людей
python scripts/client_search.py "Иван Петров" --workspace documents --mode graph

# Глубокий поиск по графу
python scripts/client_search.py "все партнеры" --workspace documents --mode graph --lightrag-mode global
```

---

### Сценарий 6: Только полнотекстовый (FTS)

```bash
# Без семантики, чистый текст
python scripts/client_search.py "экспорт" --workspace reports --mode fts --no-expand --no-rerank

# Быстро, без переранжирования
python scripts/client_search.py "ОАО" --workspace reports --mode fts --no-rerank

# Много результатов для ручного отбора
python scripts/client_search.py "компания" --workspace reports --mode fts --top-k 100
```

---

### Сценарий 7: Гибридный поиск с кастомными весами

#### Важен смысл (вектор)

```bash
python scripts/client_search.py "финансовая стабильность" \
    --workspace reports \
    --mode hybrid \
    --vector-weight 0.7 \
    --fts-weight 0.2 \
    --graph-weight 0.1
```

**API:**
```bash
curl -X POST http://localhost:18000/api/v1/search \
    -H "Content-Type: application/json" \
    -d '{
        "query": "финансовая стабильность",
        "workspace_name": "reports",
        "mode": "hybrid",
        "vector_weight": 0.7,
        "fts_weight": 0.2,
        "graph_weight": 0.1
    }'
```

#### Важен точный поиск (FTS)

```bash
python scripts/client_search.py '"ООО Рога и Копыта"' \
    --workspace reports \
    --mode hybrid \
    --vector-weight 0.2 \
    --fts-weight 0.7 \
    --graph-weight 0.1
```

#### Граф важнее (сущности и связи)

```bash
python scripts/client_search.py "организационная структура" \
    --workspace reports \
    --mode hybrid \
    --vector-weight 0.2 \
    --fts-weight 0.2 \
    --graph-weight 0.6
```

---

### Сценарий 8: Расширение запроса

```bash
# LLM переформулирует вопрос перед поиском
python scripts/client_search.py "Сколько зарабатывает компания?" \
    --workspace reports \
    --expand  # По умолчанию включено

# Без расширения (быстрее, но может меньше результатов)
python scripts/client_search.py "Сколько зарабатывает компания?" \
    --workspace reports \
    --no-expand
```

---

### Сценарий 9: Специфичные поиски

#### Поиск по аббревиатурам (новое в PGroonga!)

```bash
# Точно аббревиатура
python scripts/client_search.py '"ОАО"' --workspace reports --mode fts

# С другими словами
python scripts/client_search.py '"ОАО" "НМСК"' --workspace reports --mode fts

# Несколько аббревиатур
python scripts/client_search.py '"ООО" OR "ОАО" OR "ЗАО"' --workspace reports --mode fts
```

#### Поиск по именам

```bash
# Точное имя
python scripts/client_search.py '"Иван Иванович Петров"' --workspace documents --mode fts

# Только фамилия
python scripts/client_search.py '"Петров"' --workspace documents --mode fts --top-k 50

# С отчеством
python scripts/client_search.py '"Иван" "Иванович"' --workspace documents --mode fts
```

#### Поиск по датам

```bash
# Год
python scripts/client_search.py '2024' --workspace reports --mode fts

# Месяц и год
python scripts/client_search.py '"январь 2024"' --workspace reports --mode fts

# Период
python scripts/client_search.py '"2024-01" OR "2024-02" OR "2024-03"' --workspace reports --mode fts
```

#### Поиск по суммам

```bash
# Число с миллионами
python scripts/client_search.py '"1.5 млн"' --workspace reports --mode fts

# Диапазон
python scripts/client_search.py '1000000 OR 2000000' --workspace reports --mode fts
```

---

### Сценарий 10: Сложные комбинированные запросы

#### Многоуровневый поиск

```bash
# 1. Найти все про компании (граф)
python scripts/client_search.py "компания" --workspace reports --mode graph

# 2. Из результатов найти финансовые данные (семантика)
python scripts/client_search.py "выручка прибыль" --workspace reports --mode vector --top-k 30

# 3. Уточнить точным текстом
python scripts/client_search.py '"выручка 2024"' --workspace reports --mode fts
```

#### Поиск с фильтрацией

```bash
# Файлы за 2024 год
python scripts/client_search.py "ОАО" --workspace reports --mode fts --date-from 2024-01-01

# Только из PDF'ов
python scripts/client_search.py "экспорт" --workspace reports --filename "*.pdf"

# Конкретный документ
python scripts/client_search.py "финансы" --workspace reports --filename "quarterly_report.pdf"
```

---

### Сценарий 11: API с полной конфигурацией

```python
import requests

API = "http://localhost:18000/api/v1/search"

# Максимально настроенный запрос
query = {
    "query": '"ООО Рога и Копыта" экспорт',
    "workspace_name": "trade_documents",
    "mode": "hybrid",

    # Какие модули включать
    "use_vector": True,
    "use_fts": True,
    "use_graph": True,

    # Расширение и переранжирование
    "expand_query": True,
    "rerank": True,

    # Сколько результатов
    "top_k": 20,
    "rerank_top_k": 5,

    # Веса для гибридного поиска
    "vector_weight": 0.4,
    "fts_weight": 0.4,
    "graph_weight": 0.2,

    # LightRAG граф режимы
    "lightrag_mode": "hybrid",  # или: local, global, naive
}

response = requests.post(API, json=query)
results = response.json()

print(f"Найдено: {results['total_results']} результатов")
print(f"Время поиска: {results['search_time_ms']}ms")
print()

for i, result in enumerate(results['results'], 1):
    print(f"{i}. Документ: {result['source']['filename']}")
    print(f"   Совокупный скор: {result['score']:.3f}")
    print(f"   Вектор: {result['vector_score']:.3f}")
    print(f"   FTS: {result['fts_score']:.3f}")
    print(f"   Граф: {result['graph_score']:.3f}")
    if result['rerank_score']:
        print(f"   После переранжирования: {result['rerank_score']:.3f}")
    print(f"   Фрагмент: {result['content'][:100]}...")
    if result['related_entities']:
        print(f"   Сущности: {', '.join([e['name'] for e in result['related_entities'][:3]])}")
    print()
```

---

### Сценарий 12: Мониторинг и отладка поиска

```bash
# Посмотреть что поисковая машина видит
python scripts/client_search.py "ОАО" --workspace reports --debug

# Проверить статус индексов
docker exec lightrag-postgres psql -U lightrag -d lightrag -c \
    "SELECT schemaname, tablename, indexname FROM pg_indexes \
    WHERE tablename='chunks' ORDER BY indexname;"

# Проверить размер индекса
docker exec lightrag-postgres psql -U lightrag -d lightrag -c \
    "SELECT pg_size_pretty(pg_relation_size('idx_chunks_pgroonga')) as index_size;"

# Проверить сколько чанков в БД
docker exec lightrag-postgres psql -U lightrag -d lightrag -c \
    "SELECT COUNT(*) as chunk_count FROM chunks;"

# Проверить граф
docker exec lightrag-neo4j cypher "MATCH (e:Entity) RETURN COUNT(e) as entities;"
docker exec lightrag-neo4j cypher "MATCH ()-[r]->() RETURN COUNT(r) as relationships;"
```

---

### Сценарий 13: Batch поиск (несколько запросов)

```python
import requests
from tqdm import tqdm

API = "http://localhost:18000/api/v1/search"
WORKSPACE = "reports"

queries = [
    "Какие были доходы?",
    "Кто руководит?",
    "Где расположена компания?",
    "Какие продукты выпускаются?",
    "Какие партнеры?"
]

results_all = []

for query in tqdm(queries, desc="Поиск"):
    response = requests.post(API, json={
        "query": query,
        "workspace_name": WORKSPACE,
        "mode": "hybrid",
        "top_k": 5
    })

    results = response.json()
    results_all.append({
        'query': query,
        'count': results['total_results'],
        'time_ms': results['search_time_ms'],
        'top_match': results['results'][0]['score'] if results['results'] else 0
    })

# Вывести статистику
for r in results_all:
    print(f"Q: {r['query'][:30]}...")
    print(f"  Результатов: {r['count']}, Время: {r['time_ms']}ms, Топ скор: {r['top_match']:.3f}")
```

---

### Сценарий 14: Экспорт результатов

```bash
# В JSON
python scripts/client_search.py "экспорт" --workspace reports --output results.json

# В CSV
python scripts/client_search.py "экспорт" --workspace reports --output results.csv --format csv

# В HTML (красивый вид)
python scripts/client_search.py "экспорт" --workspace reports --output results.html --format html
```

---

### Таблица режимов поиска

| Режим | Команда | Примечание | Скорость |
|---|---|---|---|
| **Гибридный** | `--mode hybrid` | Все три метода с весами | Средняя |
| **Вектор** | `--mode vector` | Только семантика | Быстро ⚡ |
| **FTS** | `--mode fts` | Только текст + булевы ops | Средне |
| **Граф** | `--mode graph` | Только сущности и связи | Медленно |
| **Вектор+FTS** | `--mode vector_fts` | Без графа | Быстро ⚡ |

---

### Таблица флагов (CLI)

| Флаг | Значение | Описание |
|---|---|---|
| `--workspace` | имя | Проект для поиска |
| `--mode` | hybrid/vector/fts/graph | Режим поиска |
| `--top-k` | число | Сколько результатов |
| `--expand` / `--no-expand` | флаг | LLM расширение |
| `--rerank` / `--no-rerank` | флаг | Переранжирование |
| `--vector-weight` | 0.0-1.0 | Вес вектора |
| `--fts-weight` | 0.0-1.0 | Вес FTS |
| `--graph-weight` | 0.0-1.0 | Вес графа |
| `--lightrag-mode` | local/global/hybrid | Граф режим |
| `--output` | путь | Сохранить результаты |

---

---

## 💻 Готовые Python скрипты (без параметров)

### Скрипт 1: Загрузить один PDF файл

**Файл: `upload_single_file.py`**

```python
#!/usr/bin/env python3
"""
Загрузить один PDF файл в систему с извлечением сущностей
"""

import requests
import json
from pathlib import Path

# ===== КОНФИГУРАЦИЯ =====
API_URL = "http://localhost:18000/api/v1/ingest"
FILE_PATH = "./documents/quarterly_report_2024.pdf"
WORKSPACE = "finance_reports"
EXTRACT_ENTITIES = True
CUSTOM_METADATA = {
    "year": 2024,
    "quarter": "Q1",
    "department": "Finance",
    "classification": "Confidential"
}

# ===== ЗАГРУЗКА =====
print(f"📁 Загружаю файл: {FILE_PATH}")

# Проверить что файл существует
if not Path(FILE_PATH).exists():
    print(f"❌ Ошибка: файл не найден: {FILE_PATH}")
    exit(1)

# Подготовить данные
with open(FILE_PATH, 'rb') as f:
    files = {'file': f}
    data = {
        'workspace_name': WORKSPACE,
        'extract_entities': 'true' if EXTRACT_ENTITIES else 'false',
        'custom_metadata': json.dumps(CUSTOM_METADATA)
    }

    # Отправить запрос
    print("🚀 Отправляю на сервер...")
    response = requests.post(API_URL, files=files, data=data)

# Обработать ответ
if response.status_code == 200:
    result = response.json()
    print(f"✅ Успешно загружен!")
    print(f"   Document ID: {result['document_id']}")
    print(f"   Статус: {result['status']}")
    print(f"   Чанков: {result['chunk_count']}")
    print(f"   Сущностей: {result['entity_count']}")
    print(f"   Связей: {result['relationship_count']}")
    print(f"   Время обработки: {result['processing_time_ms']}ms")
else:
    print(f"❌ Ошибка: {response.status_code}")
    print(response.text)
```

**Запуск:**
```bash
python upload_single_file.py
```

---

### Скрипт 2: Загрузить папку документов (batch)

**Файл: `upload_folder_batch.py`**

```python
#!/usr/bin/env python3
"""
Загрузить все документы из папки (batch ingestion)
"""

import requests
import json
from pathlib import Path
from tqdm import tqdm

# ===== КОНФИГУРАЦИЯ =====
API_URL = "http://localhost:18000/api/v1/ingest"
DOCS_FOLDER = "./documents"
WORKSPACE = "archive_2024"
EXTRACT_ENTITIES = True

# Расширения которые загружать
SUPPORTED_FORMATS = {'.pdf', '.docx', '.doc', '.txt', '.md', '.html', '.htm', '.rtf'}

# ===== ЗАГРУЗКА =====
print(f"📁 Сканирую папку: {DOCS_FOLDER}")

# Найти все поддерживаемые файлы
docs_path = Path(DOCS_FOLDER)
files_to_upload = []

for ext in SUPPORTED_FORMATS:
    files_to_upload.extend(docs_path.glob(f"**/*{ext}"))
    files_to_upload.extend(docs_path.glob(f"**/*{ext.upper()}"))

files_to_upload = sorted(list(set(files_to_upload)))  # Удалить дубликаты

print(f"📄 Найдено файлов: {len(files_to_upload)}")

if not files_to_upload:
    print("❌ Файлы не найдены!")
    exit(1)

# ===== ЗАГРУЗИТЬ С ПРОГРЕСС-БАРОМ =====
successful = 0
failed = 0

for file_path in tqdm(files_to_upload, desc="Загрузка"):
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {
                'workspace_name': WORKSPACE,
                'extract_entities': 'true' if EXTRACT_ENTITIES else 'false',
                'custom_metadata': json.dumps({
                    'original_path': str(file_path),
                    'file_size_mb': file_path.stat().st_size / 1024 / 1024
                })
            }

            response = requests.post(API_URL, files=files, data=data)

            if response.status_code == 200:
                result = response.json()
                successful += 1
                # tqdm.write(f"  ✓ {file_path.name} ({result['chunk_count']} чанков)")
            else:
                failed += 1
                tqdm.write(f"  ✗ {file_path.name} - Error {response.status_code}")

    except Exception as e:
        failed += 1
        tqdm.write(f"  ✗ {file_path.name} - {str(e)}")

# ===== ИТОГИ =====
print(f"\n✅ Успешно: {successful}")
print(f"❌ Ошибок: {failed}")
print(f"📊 Всего обработано: {successful + failed}")
```

**Запуск:**
```bash
python upload_folder_batch.py
```

---

### Скрипт 3: Простой текстовый поиск (FTS)

**Файл: `search_text_simple.py`**

```python
#!/usr/bin/env python3
"""
Простой полнотекстовый поиск
"""

import requests
import json

# ===== КОНФИГУРАЦИЯ =====
API_URL = "http://localhost:18000/api/v1/search"
WORKSPACE = "finance_reports"

# Что искать
SEARCH_QUERY = "ОАО экспорт"

# ===== ПОИСК =====
print(f"🔍 Ищу: '{SEARCH_QUERY}'")
print(f"📁 Workspace: {WORKSPACE}\n")

query_data = {
    "query": SEARCH_QUERY,
    "workspace_name": WORKSPACE,
    "mode": "fts",  # Full-text search
    "top_k": 10,
    "expand_query": False,  # Без расширения (быстрее)
    "rerank": False  # Без переранжирования
}

response = requests.post(API_URL, json=query_data)

if response.status_code == 200:
    results = response.json()

    print(f"✅ Найдено результатов: {results['total_results']}")
    print(f"⏱️  Время поиска: {results['search_time_ms']}ms\n")

    # Вывести результаты
    for i, result in enumerate(results['results'], 1):
        print(f"\n{'='*70}")
        print(f"{i}. ДОКУМЕНТ: {result['source']['filename']}")
        print(f"   Релевантность: {result['score']:.3f}")
        print(f"   Раздел: {result['source']['chunk_index']}")
        print(f"{'='*70}")

        # Показать фрагмент
        content = result['content'][:200]
        print(f"\n📄 Фрагмент:\n{content}...\n")

        # Если есть выделение
        if result.get('highlighted_content'):
            print(f"🔆 С выделением:")
            print(result['highlighted_content'][:200])
else:
    print(f"❌ Ошибка поиска: {response.status_code}")
    print(response.text)
```

**Запуск:**
```bash
python search_text_simple.py
```

---

### Скрипт 4: Фразовый поиск (точное совпадение)

**Файл: `search_phrase_exact.py`**

```python
#!/usr/bin/env python3
"""
Поиск точной фразы в кавычках (новое в PGroonga!)
"""

import requests

# ===== КОНФИГУРАЦИЯ =====
API_URL = "http://localhost:18000/api/v1/search"
WORKSPACE = "documents"

# Поиск ТОЧНОЙ фразы
EXACT_PHRASE = "Григорий Баженов"  # В кавычках!

# ===== ПОИСК =====
print(f"🔎 Ищу точную фразу: \"{EXACT_PHRASE}\"")
print(f"📁 Workspace: {WORKSPACE}\n")

query_data = {
    "query": f'"{EXACT_PHRASE}"',  # Оборачиваем в кавычки
    "workspace_name": WORKSPACE,
    "mode": "fts",  # Полнотекстовый поиск (работает с Groonga синтаксисом)
    "top_k": 20
}

response = requests.post(API_URL, json=query_data)

if response.status_code == 200:
    results = response.json()

    if results['total_results'] > 0:
        print(f"✅ Найдено результатов: {results['total_results']}\n")

        for i, result in enumerate(results['results'], 1):
            print(f"{i}. {result['source']['filename']} (скор: {result['score']:.3f})")
            print(f"   >>> {result['content'][:150]}...\n")
    else:
        print(f"⚠️  Фраза не найдена")
else:
    print(f"❌ Ошибка: {response.status_code}")
```

**Запуск:**
```bash
python search_phrase_exact.py
```

---

### Скрипт 5: Булевы операторы (OR, AND, NOT)

**Файл: `search_boolean_operators.py`**

```python
#!/usr/bin/env python3
"""
Поиск с булевыми операторами (OR, AND, NOT)
Синтаксис Groonga в PGroonga
"""

import requests

# ===== КОНФИГУРАЦИЯ =====
API_URL = "http://localhost:18000/api/v1/search"
WORKSPACE = "trade_documents"

# Примеры запросов с булевыми операторами
QUERIES = [
    # OR (альтернатива)
    ("ОАО OR компания", "ОАО или компания"),

    # AND (оба слова обязательны)
    ("экспорт AND импорт", "оба слова обязательны"),

    # NOT (исключение)
    ("ОАО -филиал", "ОАО, но без 'филиал'"),

    # Комбинированно
    ('"ООО Рога" (экспорт OR импорт) -представительство', "сложный запрос"),

    # Аббревиатуры и организации
    ('"ОАО" AND "2024"', "точные аббревиатуры"),
]

# ===== ПОИСК =====
for query, description in QUERIES:
    print(f"\n{'='*70}")
    print(f"📌 {description}")
    print(f"🔍 Запрос: {query}")
    print(f"{'='*70}\n")

    query_data = {
        "query": query,
        "workspace_name": WORKSPACE,
        "mode": "fts",
        "top_k": 5
    }

    response = requests.post(API_URL, json=query_data)

    if response.status_code == 200:
        results = response.json()

        if results['total_results'] > 0:
            print(f"✅ Найдено: {results['total_results']} результатов")

            for i, result in enumerate(results['results'], 1):
                print(f"  {i}. {result['source']['filename']} ({result['score']:.3f})")
        else:
            print(f"⚠️  Ничего не найдено")
    else:
        print(f"❌ Ошибка: {response.status_code}")
```

**Запуск:**
```bash
python search_boolean_operators.py
```

---

### Скрипт 6: Семантический поиск (вектор)

**Файл: `search_semantic_vector.py`**

```python
#!/usr/bin/env python3
"""
Семантический поиск (поиск по смыслу, не по словам)
"""

import requests

# ===== КОНФИГУРАЦИЯ =====
API_URL = "http://localhost:18000/api/v1/search"
WORKSPACE = "reports"

# Семантические запросы (по смыслу)
SEMANTIC_QUERIES = [
    "Какие доходы и прибыль компании?",
    "Финансовые показатели и результаты",
    "Основная деятельность и направления развития",
    "Сотрудники и команда руководства",
    "Партнеры и стратегические альянсы"
]

# ===== ПОИСК =====
print(f"🧠 СЕМАНТИЧЕСКИЙ ПОИСК (поиск по смыслу)\n")

for query in SEMANTIC_QUERIES:
    print(f"❓ Вопрос: {query}")

    query_data = {
        "query": query,
        "workspace_name": WORKSPACE,
        "mode": "vector",  # Только вектор-поиск (семантика)
        "top_k": 3,
        "expand_query": False
    }

    response = requests.post(API_URL, json=query_data)

    if response.status_code == 200:
        results = response.json()

        if results['results']:
            for i, result in enumerate(results['results'], 1):
                print(f"  {i}. (вектор скор: {result['vector_score']:.3f})")
                print(f"     {result['content'][:120]}...")
        else:
            print(f"  ⚠️  Нет результатов")

    print()
```

**Запуск:**
```bash
python search_semantic_vector.py
```

---

### Скрипт 7: Гибридный поиск с кастомными весами

**Файл: `search_hybrid_custom_weights.py`**

```python
#!/usr/bin/env python3
"""
Гибридный поиск с кастомными весами для каждого модуля
"""

import requests

# ===== КОНФИГУРАЦИЯ =====
API_URL = "http://localhost:18000/api/v1/search"
WORKSPACE = "finance_2024"
SEARCH_QUERY = "выручка ОАО"

# Три сценария с разными весами

# Сценарий 1: Важен СМЫСЛ (вектор)
SCENARIO_1 = {
    "name": "Важен смысл (вектор доминирует)",
    "weights": {
        "vector_weight": 0.7,      # 70% - вектор
        "fts_weight": 0.2,         # 20% - текст
        "graph_weight": 0.1        # 10% - граф
    }
}

# Сценарий 2: Важен ТОЧНЫЙ ТЕКСТ (FTS)
SCENARIO_2 = {
    "name": "Важен точный текст (FTS доминирует)",
    "weights": {
        "vector_weight": 0.1,
        "fts_weight": 0.8,         # 80% - текст
        "graph_weight": 0.1
    }
}

# Сценарий 3: Важны СУЩНОСТИ и СВЯЗИ (граф)
SCENARIO_3 = {
    "name": "Важны сущности и связи (граф доминирует)",
    "weights": {
        "vector_weight": 0.2,
        "fts_weight": 0.2,
        "graph_weight": 0.6        # 60% - граф
    }
}

# ===== ПОИСК =====
scenarios = [SCENARIO_1, SCENARIO_2, SCENARIO_3]

for scenario in scenarios:
    print(f"\n{'='*70}")
    print(f"📌 {scenario['name']}")
    print(f"🔍 Запрос: {SEARCH_QUERY}")
    print(f"{'='*70}\n")

    query_data = {
        "query": SEARCH_QUERY,
        "workspace_name": WORKSPACE,
        "mode": "hybrid",
        "top_k": 3,
        "vector_weight": scenario['weights']['vector_weight'],
        "fts_weight": scenario['weights']['fts_weight'],
        "graph_weight": scenario['weights']['graph_weight']
    }

    response = requests.post(API_URL, json=query_data)

    if response.status_code == 200:
        results = response.json()

        print(f"✅ Найдено: {results['total_results']}")
        print(f"⏱️  Время: {results['search_time_ms']}ms\n")

        for i, result in enumerate(results['results'], 1):
            print(f"{i}. {result['source']['filename']}")
            print(f"   Совокупный скор: {result['score']:.3f}")
            print(f"   - Вектор: {result.get('vector_score', 0):.3f}")
            print(f"   - FTS: {result.get('fts_score', 0):.3f}")
            print(f"   - Граф: {result.get('graph_score', 0):.3f}")
            print()
```

**Запуск:**
```bash
python search_hybrid_custom_weights.py
```

---

### Скрипт 8: Граф-поиск (сущности и связи)

**Файл: `search_graph_entities.py`**

```python
#!/usr/bin/env python3
"""
Поиск через граф (сущности и их связи)
"""

import requests

# ===== КОНФИГУРАЦИЯ =====
API_URL = "http://localhost:18000/api/v1/search"
WORKSPACE = "organizational_data"

# Примеры поиска через граф
ENTITY_QUERIES = [
    ("ООО", "Организации"),
    ("Иван", "Люди с именем Иван"),
    ("Москва", "Места и локации"),
    ("технология", "Технологии и инновации"),
]

# Режимы поиска в графе
GRAPH_MODES = ["local", "global", "hybrid"]  # local=1-хоп, global=паттерны, hybrid=оба

# ===== ПОИСК =====
for query, description in ENTITY_QUERIES:
    print(f"\n{'='*70}")
    print(f"📌 {description}: {query}")
    print(f"{'='*70}\n")

    for mode in GRAPH_MODES:
        query_data = {
            "query": query,
            "workspace_name": WORKSPACE,
            "mode": "graph",
            "lightrag_mode": mode,  # local / global / hybrid
            "top_k": 2
        }

        response = requests.post(API_URL, json=query_data)

        if response.status_code == 200:
            results = response.json()

            print(f"🔍 Режим: {mode.upper()} - {results['total_results']} результатов")

            for result in results['results'][:2]:
                print(f"  ✓ {result['content'][:80]}...")

            if results.get('graph_context'):
                context = results['graph_context']
                print(f"  Сущностей: {len(context.get('entities', []))}")
                print(f"  Связей: {len(context.get('relationships', []))}")

        print()
```

**Запуск:**
```bash
python search_graph_entities.py
```

---

### Скрипт 9: Обработка и сохранение результатов

**Файл: `search_and_export_results.py`**

```python
#!/usr/bin/env python3
"""
Поиск, обработка и сохранение результатов в разные форматы
"""

import requests
import json
import csv
from datetime import datetime

# ===== КОНФИГУРАЦИЯ =====
API_URL = "http://localhost:18000/api/v1/search"
WORKSPACE = "documents"
SEARCH_QUERY = "финансовые показатели"

# Папка для результатов
OUTPUT_DIR = "./search_results"

# ===== ПОИСК =====
print(f"🔍 Ищу: {SEARCH_QUERY}")

query_data = {
    "query": SEARCH_QUERY,
    "workspace_name": WORKSPACE,
    "mode": "hybrid",
    "top_k": 20
}

response = requests.post(API_URL, json=query_data)

if response.status_code != 200:
    print(f"❌ Ошибка: {response.status_code}")
    exit(1)

results = response.json()
print(f"✅ Найдено: {results['total_results']} результатов\n")

# ===== СОХРАНИТЬ В JSON =====
json_file = f"{OUTPUT_DIR}/results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

with open(json_file, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"💾 JSON сохранён: {json_file}")

# ===== СОХРАНИТЬ В CSV =====
csv_file = f"{OUTPUT_DIR}/results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

with open(csv_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)

    # Заголовок
    writer.writerow([
        'Номер', 'Документ', 'Скор', 'Вектор', 'FTS', 'Граф',
        'Чанк', 'Фрагмент'
    ])

    # Данные
    for i, result in enumerate(results['results'], 1):
        writer.writerow([
            i,
            result['source']['filename'],
            f"{result['score']:.3f}",
            f"{result.get('vector_score', 0):.3f}",
            f"{result.get('fts_score', 0):.3f}",
            f"{result.get('graph_score', 0):.3f}",
            result['source']['chunk_index'],
            result['content'][:100].replace('\n', ' ')
        ])

print(f"💾 CSV сохранён: {csv_file}")

# ===== ВЫВЕСТИ СТАТИСТИКУ =====
print(f"\n📊 СТАТИСТИКА:")
print(f"   Всего результатов: {results['total_results']}")
print(f"   Время поиска: {results['search_time_ms']}ms")

if results['results']:
    scores = [r['score'] for r in results['results']]
    print(f"   Средний скор: {sum(scores)/len(scores):.3f}")
    print(f"   Макс скор: {max(scores):.3f}")
    print(f"   Мин скор: {min(scores):.3f}")

    # По источникам
    sources = {}
    for r in results['results']:
        filename = r['source']['filename']
        sources[filename] = sources.get(filename, 0) + 1

    print(f"\n📄 ПО ДОКУМЕНТАМ:")
    for filename, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
        print(f"   {filename}: {count} результатов")
```

**Запуск:**
```bash
python search_and_export_results.py
```

---

### Скрипт 10: Batch поиск (несколько вопросов подряд)

**Файл: `search_batch_multiple_queries.py`**

```python
#!/usr/bin/env python3
"""
Batch поиск - несколько вопросов подряд с одного скрипта
"""

import requests
from tqdm import tqdm
from datetime import datetime

# ===== КОНФИГУРАЦИЯ =====
API_URL = "http://localhost:18000/api/v1/search"
WORKSPACE = "company_data"

# Список вопросов для поиска
QUESTIONS = [
    "Какие доходы в 2024?",
    "Кто руководит компанией?",
    "Где расположены офисы?",
    "Какие продукты выпускаются?",
    "Кто партнеры и контрагенты?",
    "Какие инвестиции и капиталовложения?",
    "Какая численность и состав сотрудников?",
    "Какие проекты в разработке?",
]

# ===== ПОИСК =====
print(f"🔍 Batch поиск по {len(QUESTIONS)} вопросам\n")

results_all = []
total_time_ms = 0

for i, question in enumerate(QUESTIONS, 1):
    query_data = {
        "query": question,
        "workspace_name": WORKSPACE,
        "mode": "hybrid",
        "top_k": 5,
        "expand_query": True,  # Расширить запрос через LLM
        "rerank": True  # Переранжировать результаты
    }

    try:
        response = requests.post(API_URL, json=query_data)

        if response.status_code == 200:
            results = response.json()
            total_time_ms += results['search_time_ms']

            # Сохранить результаты
            results_all.append({
                'question': question,
                'result_count': results['total_results'],
                'time_ms': results['search_time_ms'],
                'top_score': results['results'][0]['score'] if results['results'] else 0,
                'results': results['results']
            })

            print(f"✓ {i}. {question[:50]}")
            print(f"     Найдено: {results['total_results']}, время: {results['search_time_ms']}ms\n")
        else:
            print(f"✗ {i}. Ошибка {response.status_code}\n")

    except Exception as e:
        print(f"✗ {i}. Исключение: {str(e)}\n")

# ===== ИТОГИ =====
print(f"\n{'='*70}")
print(f"📊 ИТОГИ BATCH ПОИСКА")
print(f"{'='*70}\n")

print(f"Обработано вопросов: {len(results_all)}")
print(f"Всего времени: {total_time_ms}ms")
print(f"Среднее время на вопрос: {total_time_ms/len(results_all):.0f}ms\n")

# Статистика
total_found = sum(r['result_count'] for r in results_all)
avg_score = sum(r['top_score'] for r in results_all) / len(results_all) if results_all else 0

print(f"Всего найдено результатов: {total_found}")
print(f"Средний топ-скор: {avg_score:.3f}\n")

# Вопросы без результатов
zero_results = [r for r in results_all if r['result_count'] == 0]
if zero_results:
    print(f"⚠️  Вопросы без результатов ({len(zero_results)}):")
    for r in zero_results:
        print(f"   - {r['question']}")
```

**Запуск:**
```bash
python search_batch_multiple_queries.py
```

---

### Скрипт 11: Проверка здоровья и статистика

**Файл: `check_health_and_stats.py`**

```python
#!/usr/bin/env python3
"""
Проверить что всё работает и получить статистику по системе
"""

import requests
import subprocess
from datetime import datetime

# ===== КОНФИГУРАЦИЯ =====
API_URL = "http://localhost:18000/api/v1/search"
HEALTH_URL = "http://localhost:18000/health"

print("="*70)
print("🏥 ПРОВЕРКА ЗДОРОВЬЯ СИСТЕМЫ")
print("="*70)

# 1. Проверить API
print("\n1️⃣  API (FastAPI)...")
try:
    response = requests.get(HEALTH_URL)
    if response.status_code == 200:
        print("   ✅ API работает")
    else:
        print(f"   ❌ API возвращает {response.status_code}")
except:
    print("   ❌ API недоступен на localhost:18000")

# 2. Проверить PostgreSQL
print("\n2️⃣  PostgreSQL (с PGroonga)...")
try:
    result = subprocess.run(
        ['docker', 'exec', 'lightrag-postgres', 'pg_isready', '-U', 'lightrag'],
        capture_output=True,
        timeout=5
    )
    if result.returncode == 0:
        print("   ✅ PostgreSQL работает")

        # Получить статистику
        result = subprocess.run(
            ['docker', 'exec', 'lightrag-postgres', 'psql', '-U', 'lightrag', '-d', 'lightrag',
             '-c', 'SELECT COUNT(*) as documents FROM documents;'],
            capture_output=True,
            text=True,
            timeout=5
        )
        print(f"   Документов в БД: {result.stdout.strip()}")
    else:
        print("   ❌ PostgreSQL недоступен")
except:
    print("   ⚠️  Не удалось проверить PostgreSQL")

# 3. Проверить Neo4j
print("\n3️⃣  Neo4j (граф)...")
try:
    result = subprocess.run(
        ['docker', 'exec', 'lightrag-neo4j', 'cypher', 'RETURN 1'],
        capture_output=True,
        timeout=5
    )
    if result.returncode == 0:
        print("   ✅ Neo4j работает")
    else:
        print("   ❌ Neo4j недоступен")
except:
    print("   ⚠️  Не удалось проверить Neo4j")

# 4. Проверить LLM сервисы
print("\n4️⃣  LLM сервисы (llama.cpp)...")
for name, port in [("LLM", 8081), ("Embeddings", 8082), ("Reranker", 8083)]:
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=2)
        if response.status_code == 200:
            print(f"   ✅ {name} работает (port {port})")
        else:
            print(f"   ❌ {name} недоступен (port {port})")
    except:
        print(f"   ❌ {name} недоступен (port {port})")

# 5. Проверить Tika
print("\n5️⃣  Apache Tika (парсер)...")
try:
    response = requests.get("http://localhost:9999/tika", timeout=2)
    if response.status_code == 200:
        print("   ✅ Tika работает (port 9999)")
    else:
        print(f"   ❌ Tika возвращает {response.status_code}")
except:
    print("   ❌ Tika недоступен (port 9999)")

# 6. Тестовый поиск
print("\n6️⃣  Тестовый поиск...")
try:
    query_data = {
        "query": "тест",
        "workspace_name": "default",
        "mode": "hybrid",
        "top_k": 1
    }
    response = requests.post(API_URL, json=query_data, timeout=10)
    if response.status_code == 200:
        results = response.json()
        print(f"   ✅ Поиск работает (найдено: {results['total_results']}, время: {results['search_time_ms']}ms)")
    else:
        print(f"   ❌ Поиск возвращает ошибку {response.status_code}")
except:
    print("   ❌ Поиск недоступен")

print("\n" + "="*70)
print(f"✅ Проверка завершена: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*70)
```

**Запуск:**
```bash
python check_health_and_stats.py
```

---

## 📋 Таблица скриптов

| Скрипт | Назначение | Сложность |
|---|---|---|
| `upload_single_file.py` | Загрузить 1 файл | ⭐ Легко |
| `upload_folder_batch.py` | Загрузить папку | ⭐ Легко |
| `search_text_simple.py` | Простой текстовый поиск | ⭐ Легко |
| `search_phrase_exact.py` | Фразовый поиск в кавычках | ⭐ Легко |
| `search_boolean_operators.py` | Булевы операторы (OR, AND, NOT) | ⭐⭐ Средне |
| `search_semantic_vector.py` | Семантический поиск | ⭐ Легко |
| `search_hybrid_custom_weights.py` | Гибридный с весами | ⭐⭐ Средне |
| `search_graph_entities.py` | Граф-поиск (сущности) | ⭐⭐ Средне |
| `search_and_export_results.py` | Поиск и экспорт (JSON, CSV) | ⭐⭐ Средне |
| `search_batch_multiple_queries.py` | Batch поиск (много вопросов) | ⭐⭐⭐ Сложно |
| `check_health_and_stats.py` | Проверка здоровья системы | ⭐ Легко |

---

## 🚀 Как использовать скрипты

### 1. Создать папку для скриптов
```bash
mkdir my_scripts
cd my_scripts
```

### 2. Скопировать код скрипта в файл
```bash
cat > upload_single_file.py << 'EOF'
#!/usr/bin/env python3
# ... весь код скрипта ...
EOF
```

### 3. Установить зависимости (если нужны)
```bash
pip install requests tqdm
```

### 4. Запустить скрипт
```bash
python upload_single_file.py
```

### 5. Отредактировать конфигурацию
Все параметры в начале скрипта - просто измените их:
```python
# ===== КОНФИГУРАЦИЯ =====
FILE_PATH = "./documents/my_file.pdf"
WORKSPACE = "my_workspace"
EXTRACT_ENTITIES = True
```

---

## 📚 Дополнительные ресурсы

- **PGroonga документация**: https://pgroonga.github.io/
- **Groonga синтаксис запросов**: https://groonga.org/docs/reference/grn_expr/query_syntax.html
- **pgvector**: https://github.com/pgvector/pgvector
- **LightRAG**: https://github.com/GRAG-JLU/LightRAG
- **llama.cpp**: https://github.com/ggml-org/llama.cpp

---

## 📝 Примеры

### Пример 1: Загрузить документ и найти информацию

```bash
# Загрузить
python scripts/client_ingest.py quarterly_report.pdf --workspace finance_q1

# Найти всё про финансовые показатели
python scripts/client_search.py "финансовые показатели" --workspace finance_q1

# Найти точную фразу
python scripts/client_search.py '"Квартальный доход составил"' --workspace finance_q1 --mode fts
```

### Пример 2: Работать через API

```python
import requests
import json

# Загрузить файл
with open('report.pdf', 'rb') as f:
    files = {'file': f}
    data = {'workspace_name': 'reports', 'extract_entities': 'true'}
    resp = requests.post('http://localhost:18000/api/v1/ingest',
                        files=files, data=data)
    print(resp.json())

# Поиск
query = {
    "query": '"ОАО" экспорт',
    "workspace_name": "reports",
    "mode": "fts",
    "top_k": 5
}
resp = requests.post('http://localhost:18000/api/v1/search', json=query)
results = resp.json()
for result in results['results']:
    print(f"Score: {result['score']:.2f}")
    print(f"Content: {result['content'][:100]}...")
    print()
```

### Пример 3: GraphRAG для аналитики

```bash
# Загрузить организационную структуру
python scripts/client_ingest.py org_structure.md --workspace org

# Найти все связи человека
python scripts/client_search.py "Иван работает в компании где?" --workspace org --mode graph

# Найти ключевых игроков (сущности с много связей)
curl http://localhost:17474  # Открыть Neo4j браузер
# Написать Cypher:
# MATCH (e:Entity)-[r]-() RETURN e.name, COUNT(r) as connections ORDER BY connections DESC
```

---

## 🤝 Внесение вклада

Пока это локальный проект, но если нужно развивать:

1. Форкировать
2. Создать ветку (`git checkout -b feature/amazing`)
3. Коммитить (`git commit -m "Add amazing feature"`)
4. Пушить (`git push origin feature/amazing`)
5. Открыть Pull Request

---

## 📄 Лицензия

MIT License — используй как угодно.

---

## ⚡ Быстрые команды

```bash
# Запустить всё
docker-compose up -d && sleep 10

# Проверить статус
docker-compose ps

# Загрузить папку документов
python scripts/client_ingest.py ./docs --batch --workspace default

# Быстрый поиск
python scripts/client_search.py "query" --workspace default

# Просмотреть логи в реальном времени
docker-compose logs -f api

# Остановить без удаления данных
docker-compose stop

# Полная очистка (внимание!)
docker-compose down -v
```

---

**Всё работает локально. Интернет не требуется. 🚀**
