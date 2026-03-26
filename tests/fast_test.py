from _update.llm.custom_llm import CustomLLM
import os
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY=os.getenv("DEEPSEEK_API_KEY")
OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")

llm = CustomLLM(
    provider="OpenAI",
    model="gpt-4",
    api_key=OPENAI_API_KEY,
    temperature=0.7,
    max_tokens=1024,
)

# Прямой вызов модели
response = llm.invoke("Привет! Кратко расскажи про Python.")
print(response.content)