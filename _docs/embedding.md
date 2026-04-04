
Примеры использования модуля `ai/vector/embed_model.py`:

---

## 1. Класс `EmbedModel` (провайдеры: qwen, openai, bge_m3)

```python
from ai.vector.embed_model import EmbedModel

# Локальный Qwen (дефолтные localhost:8082 и модель)
emb = EmbedModel(provider="qwen")
vec = emb.embed_query("Привет, мир!")
print(len(vec))  # размерность вектора

# Qwen с другим хостом и моделью
emb = EmbedModel(
    provider="qwen",
    api_url="http://192.168.0.104:8082",
    model_name="/Qwen3-Embedding-0.6B-f16.gguf",
)
docs_vec = emb.embed_documents(["Текст 1", "Текст 2"])

# Облачный OpenAI (берёт OPENAI_API_KEY из config)
emb = EmbedModel(provider="openai")
vec = emb.embed_query("Поисковый запрос")

# OpenAI с другой моделью
emb = EmbedModel(provider="openai", openai_model="text-embedding-3-large")
vec = emb.embed_query("Ещё один запрос")

# Смена модели (для qwen)
emb = EmbedModel(provider="qwen", api_url="http://localhost:8082")
emb.set_model("/другая-модель.gguf")
print(emb.get_model())

# Локальный BGE-M3 (FlagEmbedding + PyTorch; dense 1024, до 8192 токенов)
emb = EmbedModel(provider="bge_m3")
emb = EmbedModel(
    provider="bge_m3",
    model_name="BAAI/bge-m3",
    use_fp16=True,
    bge_m3_batch_size=8,
    bge_m3_max_length=2048,
)
# Для BGE-M3 отдельные инструкции к запросу не добавляют (в отличие от ряда моделей BGE v1.5).
m3 = emb.get_bgem3()  # BGEM3Embeddings или None
if m3:
    out = m3.encode_batch(
        ["текст 1", "текст 2"],
        return_sparse=True,
        return_colbert=True,
    )
    # out["dense_vecs"], out["lexical_weights"], out["colbert_vecs"]
```

---

## 2. Фабрика `get_embed_model`

```python
from ai.vector.embed_model import get_embed_model

emb = get_embed_model("qwen")
emb = get_embed_model("openai")
emb = get_embed_model("bge_m3", model_name="BAAI/bge-m3", use_fp16=True)

emb = get_embed_model(
    "qwen",
    api_url="http://192.168.0.104:8082",
    model_name="/my-model.gguf",
)
emb = get_embed_model("openai", openai_model="text-embedding-3-small")
```

---

## 3. Один запрос и пачка документов

```python
from ai.vector.embed_model import EmbedModel

emb = EmbedModel(provider="qwen")

query_vec = emb.embed_query("как настроить RAG?")

texts = ["Документ 1...", "Документ 2...", "Документ 3..."]
doc_vecs = emb.embed_documents(texts)
```

---

## 4. В связке с LangChain (например, ретривер)

```python
from langchain_community.vectorstores import Qdrant
from ai.vector.embed_model import EmbedModel

emb = EmbedModel(provider="openai")  # или provider="qwen" / "bge_m3"
```

---

## 5. Напрямую `QwenEmbeddings` (без выбора провайдера)

```python
from ai.vector.embed_model import QwenEmbeddings

emb = QwenEmbeddings(
    api_url="http://192.168.0.104:8082",
    model_name="/Qwen3-Embedding-0.6B-f16.gguf",
)
vec = emb.embed_query("Тест")
emb.set_model("/другая.gguf")
print(emb.get_model())
```

---

## 6. `BGEM3Embeddings` и Qdrant

- **Dense:** `embed_documents` / `embed_query` — как у любого LangChain `Embeddings`.
- **Sparse (лексика):** словари `lexical_weights` из `encode_batch(..., return_sparse=True)`; в Qdrant переводятся в `SparseVector` (см. `lexical_weights_to_sparse_parts` в `embed_model.py` и `VectorStore` с `sparse_backend="bgem3"`).
- **ColBERT:** `encode_batch(..., return_colbert=True)` → `colbert_vecs`; каждый документ — последовательность векторов токенов; для Qdrant используется именованный multivector с MaxSim (см. `_docs/vector_store_hybrid.md`).

Зависимости: `pip install FlagEmbedding` (потянет **PyTorch** — тяжёлая установка).

Ссылки: [FlagOpen/FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding), модель [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3).

---

## 7. Конфигурация (.env) для RAG-агента

- `DENSE_MODEL_PROVIDER=bge_m3` — локальный BGE-M3.
- `BGE_M3_MODEL` (по умолчанию `BAAI/bge-m3`), `BGE_M3_USE_FP16` (по умолчанию `true`).
- `VECTOR_USE_COLBERT=true` — включить ColBERT в Qdrant (нужна новая коллекция под эту схему).

---

## 8. Краткая шпаргалка

| Задача              | Вариант |
|---------------------|--------|
| Один провайдер      | `EmbedModel(provider="qwen")` / `"openai"` / `"bge_m3"` |
| Нужен именно `Embeddings` | `get_embed_model("qwen")` / … |
| Только локальный Qwen | `QwenEmbeddings(...)` |
| BGE-M3 sparse/ColBERT для Qdrant | `VectorStore(..., sparse_backend="bgem3", use_colbert=...)` + `EmbedModel(provider="bge_m3")` |
| Вектор для запроса   | `emb.embed_query("текст")` → `List[float]` |
| Векторы для документов | `emb.embed_documents(["a", "b"])` → `List[List[float]]` |
| Смена модели (qwen/bge_m3) | `emb.set_model("...")`, `emb.get_model()` |

Импорт из корня проекта: `from ai.vector.embed_model import EmbedModel, get_embed_model, QwenEmbeddings, BGEM3Embeddings, lexical_weights_to_sparse_parts`.
