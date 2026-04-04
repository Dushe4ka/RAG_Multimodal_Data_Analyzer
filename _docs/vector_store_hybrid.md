# Векторное хранилище и гибридный поиск (Qdrant)

## Цель

Использовать Qdrant для RAG с **гибридным поиском**: объединение dense-векторов (семантика), опционально sparse (лексика) и опционально **ColBERT multivector** (late interaction, MaxSim) через **RRF**.

## Компоненты

### 1. Dense-векторы

- **Модуль:** `ai/vector/embed_model.py`
- **Классы:** `EmbedModel`, `QwenEmbeddings`, `OpenAIEmbeddings`, `BGEM3Embeddings`
- **Роль:** плотное представление текста (косинусное сходство в Qdrant).
- **Имя вектора в коллекции:** `dense`

### 2. Sparse-векторы (два режима)

| `sparse_backend` | Источник | Примечание |
|------------------|----------|------------|
| `fastembed` (по умолчанию) | **SPLADE** (`SparseTextEmbedding`) | Не смешивать dense от BGE-M3 с этим sparse: для BGE-M3 задайте `bgem3`. |
| `bgem3` | **BGE-M3** `lexical_weights` → `SparseVector` | Тот же `EmbedModel(provider="bge_m3")`, что и для dense. |

- **Имя вектора:** `sparse`
- **Формат Qdrant:** `SparseVector(indices=..., values=...)`

### 3. ColBERT (опционально)

- Только с **BGE-M3** (`use_colbert=True` в `VectorStore`).
- **Имя вектора:** `colbert`
- Конфигурация: `VectorParams` с `multivector_config=MultiVectorConfig(comparator=MAX_SIM)`, `hnsw_config` с `m=0` (рекомендация Qdrant для multivector).
- Запрос и документы кодируются одной моделью; запрос — multivector из `encode_batch(..., return_colbert=True)`.

### 4. Схема коллекции

Зависит от флагов:

- Всегда: `dense` (dense).
- Если `use_sparse`: `sparse` в `sparse_vectors_config`.
- Если `use_colbert`: второй именованный dense-вектор `colbert` с multivector (не путать с sparse).

**Миграция:** схема задаётся при создании коллекции. Если коллекция уже создана без ColBERT, нельзя просто включить `use_colbert=True` под тем же именем — используйте **новое имя коллекции** или пересоздайте коллекцию.

### 5. Гибридный поиск и RRF

`VectorStore.search(..., mode="hybrid")`:

- Строится один или несколько **prefetch** (dense; при `use_sparse` — sparse; при `use_colbert` — colbert).
- Если prefetch один (только dense), выполняется обычный nearest по `dense`.
- Иначе: `query_points(..., prefetch=[...], query=FusionQuery(fusion=RRF))`.

Ссылки:

- [Hybrid / Query API — Qdrant](https://qdrant.tech/documentation/guides/text-search)
- [Multivector / late interaction — Qdrant](https://qdrant.tech/documentation/tutorials-search-engineering/using-multivector-representations/)
- [FlagEmbedding / BGE-M3](https://github.com/FlagOpen/FlagEmbedding)

### 6. Класс `VectorStore` (`ai/vector/vector_store.py`)

Основные параметры конструктора:

- `embed_model` — `EmbedModel` (qwen / openai / bge_m3).
- `use_sparse` — хранить и участвовать в поиске sparse.
- `sparse_backend` — `"fastembed"` | `"bgem3"`.
- `use_colbert` — multivector ColBERT (только с BGE-M3).

Ограничения (валидация в коде):

- При эмбеддере BGE-M3 и `use_sparse=True` нужен `sparse_backend="bgem3"`.
- `use_colbert=True` требует `EmbedModel(provider="bge_m3")`.
- При `use_sparse=True` и `use_colbert=True` — `sparse_backend="bgem3"`.

### 7. Индексация и поиск (поток данных)

**Индексация (`add_documents`):**

- Режим qwen/openai + SPLADE: dense через `embed_documents`, sparse через fastembed (как раньше).
- Режим BGE-M3: один вызов `encode_batch` на батч (dense + при необходимости lexical + colbert), затем upsert.

**Поиск:**

- Запрос → те же эмбеддеры, что при индексации.
- `mode="dense"` — только ветка `dense`.

### 8. Пример BGE-M3

```python
from ai.vector.embed_model import EmbedModel
from ai.vector.vector_store import VectorStore
from config import settings

store = VectorStore(
    collection_name="my_bge_m3",
    embed_model=EmbedModel(provider="bge_m3"),
    qdrant_url=settings.QDRANT_URL,
    use_sparse=True,
    sparse_backend="bgem3",
    use_colbert=False,  # True — отдельная схема, новая коллекция
)
store.add_documents(texts=["..."], payloads=[{}])
hits = store.search("запрос", mode="hybrid", limit=5)
```

Скрипт-пример: `python3 -m tests.embed.ex_6_bge_m3_qdrant`.

### 9. RAG-агент и .env

При `DENSE_MODEL_PROVIDER=bge_m3` агент поднимает `EmbedModel(provider="bge_m3")` и `VectorStore` с `sparse_backend="bgem3"` (если `USE_SPARSE`), плюс `VECTOR_USE_COLBERT` из настроек.

### 10. Ссылки (доп.)

- [Vectors (named, dense, sparse) — Qdrant](https://qdrant.tech/documentation/concepts/vectors/)
- [SPLADE with FastEmbed](https://qdrant.github.io/fastembed/examples/SPLADE_with_FastEmbed/)
