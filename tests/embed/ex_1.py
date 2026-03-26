from ai.vector.embed_model import get_embed_model

emb = get_embed_model(provider="openai")
print(emb.embed_documents(["Hello, world!"]))
