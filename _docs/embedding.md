
Примеры использования модуля `ai/vector/embed_model.py`:

---

## 1. Класс `EmbedModel` (один провайдер — qwen или openai)

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
```

---

## 2. Фабрика `get_embed_model`

```python
from ai.vector.embed_model import get_embed_model

# Получить реализацию Embeddings без обёртки EmbedModel
emb = get_embed_model("qwen")
emb = get_embed_model("openai")

# С параметрами
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

# Один вектор (поиск, запрос пользователя)
query_vec = emb.embed_query("как настроить RAG?")

# Векторы для списка документов (индексация)
texts = ["Документ 1...", "Документ 2...", "Документ 3..."]
doc_vecs = emb.embed_documents(texts)
# doc_vecs[i] — вектор для texts[i]
```

---

## 4. В связке с LangChain (например, ретривер)

```python
from langchain_community.vectorstores import Qdrant
from ai.vector.embed_model import EmbedModel

emb = EmbedModel(provider="openai")  # или provider="qwen"

# Пример: векторное хранилище на своих документах
# vectorstore = Qdrant.from_documents(documents=docs, embedding=emb)
# retriever = vectorstore.as_retriever(k=5)
# retriever.invoke("ваш вопрос")
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

## 6. Краткая шпаргалка

| Задача              | Вариант |
|---------------------|--------|
| Один провайдер, один интерфейс | `EmbedModel(provider="qwen")` или `"openai"` |
| Нужен именно `Embeddings`     | `get_embed_model("qwen")` / `get_embed_model("openai")` |
| Только локальный Qwen          | `QwenEmbeddings(api_url=..., model_name=...)` |
| Вектор для запроса             | `emb.embed_query("текст")` → `List[float]` |
| Векторы для документов         | `emb.embed_documents(["a", "b"])` → `List[List[float]]` |
| Смена модели (qwen)            | `emb.set_model("...")`, `emb.get_model()` |

Импорт из корня проекта: `from ai.vector.embed_model import EmbedModel, get_embed_model, QwenEmbeddings`.