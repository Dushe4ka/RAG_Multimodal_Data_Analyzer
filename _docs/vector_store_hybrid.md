# Векторное хранилище и гибридный поиск (Qdrant)

## Цель

Использовать Qdrant для RAG с **гибридным поиском**: объединение dense-векторов (семантика) и sparse-векторов (точное совпадение слов / ключевые слова) для более качественного поиска.

## Компоненты

### 1. Dense-векторы (уже есть)

- **Модуль:** `ai/vector/embed_model.py`
- **Классы:** `EmbedModel`, `QwenEmbeddings`, `OpenAIEmbeddings`
- **Роль:** преобразование текста в плотный вектор (семантическое сходство).
- **Использование:** для запросов и документов — один и тот же эмбеддер (Qwen или OpenAI).

### 2. Sparse-векторы (нужно добавить)

- **Библиотека:** [fastembed](https://github.com/qdrant/fastembed) — модель **SPLADE** (Sparse Lexical and Expansion).
- **Формат:** пары `(indices, values)` — индексы в словаре и веса токенов.
- **Роль:** точное/лексическое совпадение и расширение запроса (синонимы, связанные термины).
- **Модель по умолчанию:** `prithivida/Splade_PP_en_v1` (в fastembed; на HuggingFace — Qdrant/Splade_PP_en_v1).
- **Зависимость:** `pip install fastembed`.

### 3. Qdrant: коллекция с двумя представлениями

В одной коллекции у каждой точки два именованных вектора:

| Имя вектора | Тип    | Модель / источник                    |
|-------------|--------|--------------------------------------|
| `dense`     | dense  | `EmbedModel` (Qwen / OpenAI)         |
| `sparse`    | sparse | fastembed `SparseTextEmbedding`      |

- **Создание коллекции:**  
  `vectors_config={"dense": VectorParams(size=<dim>, distance=COSINE)}`,  
  `sparse_vectors_config={"sparse": SparseVectorParams()}`.
- **Имена** `dense` и `sparse` должны различаться (ограничение Qdrant).

### 4. Гибридный поиск (Query API, v1.10+)

Идея: выполнить два подзапроса (prefetch) — по dense и по sparse — и слить результаты одним из методов.

- **Prefetch:** для каждого подзапроса задаётся:
  - `query` — вектор (dense — список float, sparse — `SparseVector(indices=..., values=...)`);
  - `using` — имя вектора (`"dense"` или `"sparse"`);
  - `limit` — сколько кандидатов взять (рекомендуется не меньше чем `limit + offset` основного запроса).
- **Слияние (fusion):**
  - **RRF (Reciprocal Rank Fusion)** — по умолчанию: объединение по рангам, константа `k=2` (при необходимости параметризованный RRF с `k=60` и т.д.).
  - **DBSF** — нормализация по распределению скоров и суммирование (доступно с v1.11).

Пример запроса (псевдокод):

```text
query_points(
  collection_name=...,
  prefetch=[
    Prefetch(query=dense_vector, using="dense", limit=20),
    Prefetch(query=SparseVector(indices=..., values=...), using="sparse", limit=20),
  ],
  query=FusionQuery(fusion=Fusion.RRF),
  limit=10,
)
```

### 5. Поток данных для RAG

**Индексация документов:**

1. Текст чанка → dense-вектор через `EmbedModel.embed_documents`.
2. Тот же текст → sparse-вектор через fastembed `SparseTextEmbedding.embed`.
3. В Qdrant одна точка с `vector={"dense": [...], "sparse": SparseVector(...)}` и payload (например, `text`, `source`, `metadata`).

**Поиск (гибридный):**

1. Запрос пользователя → dense-вектор через `EmbedModel.embed_query`.
2. Тот же запрос → sparse-вектор через fastembed для одного текста.
3. Вызов `query_points` с двумя prefetch (dense + sparse) и `query=FusionQuery(fusion=Fusion.RRF)`.
4. Возврат топ-N точек с payload для RAG (ретрайвер).

### 6. Что реализовать в коде

- **`ai/vector/vector_store.py` — класс `VectorStore`:**
  - Инициализация: клиент Qdrant, коллекция, `EmbedModel` (dense), размер dense-вектора, опционально URL/настройки Qdrant.
  - Инициализация sparse: экземпляр fastembed `SparseTextEmbedding` (модель по умолчанию SPLADE).
  - **Создание коллекции:** если коллекции нет — создать с `dense` и `sparse` (named vectors).
  - **Добавление документов:** `add_documents(texts, payloads)` — эмбеддинг dense + sparse, `upsert` точек с обоими векторами.
  - **Поиск:**  
    - `hybrid_search(query_text, limit, ...)` — эмбеддинг запроса в dense и sparse, два prefetch, RRF, возврат списка документов/рекордов.  
    - Опционально: `dense_only_search` для только семантического поиска.
- **Конфиг:** размер dense-вектора (из настроек или параметр), URL Qdrant (например в `config` или переменные окружения).
- **Зависимости:** в `requirements.txt` добавить `fastembed`.

### 7. Важные моменты

- **Размер dense:** должен совпадать с размером выхода `EmbedModel` (Qwen/OpenAI). Либо передавать в конструктор, либо один раз получить через `embed_query(".")` и `len()`.
- **Limit в prefetch:** по документации Qdrant prefetch должен возвращать не меньше `limit + offset` основного запроса, иначе возможны пустые результаты.
- **Один и тот же словарь для sparse:** и для индексации, и для запросов используется одна и та же SPLADE-модель, чтобы indices/values были согласованы.

### 8. Ссылки

- [Hybrid and Multi-Stage Queries — Qdrant](https://qdrant.tech/documentation/concepts/hybrid-queries/)
- [Vectors (named, dense, sparse) — Qdrant](https://qdrant.tech/documentation/concepts/vectors/)
- [SPLADE with FastEmbed](https://qdrant.github.io/fastembed/examples/SPLADE_with_FastEmbed/)
- [Query API (query_points) — Qdrant](https://api.qdrant.tech/api-reference/search/query-points)
