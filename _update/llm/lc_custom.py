from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents.factory import c


# Настройка подключения к вашему API
llm = ChatOpenAI(
    model="Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf",
    openai_api_key="sk-111111111111111111111111",
    base_url="http://192.168.1.52:5000/v1",
    temperature=0.7,
    max_tokens=2048,
)

# Пример использования
def chat_with_model(prompt):
    try:
        # Создание сообщения
        message = HumanMessage(content=prompt)

        # Отправка запроса (используем invoke вместо вызова объекта)
        response = llm.invoke([message])

        return response.content

    except Exception as e:
        return f"Ошибка: {str(e)}"

# Альтернативный способ с использованием промптов
def chat_with_prompt_template():
    # Создание шаблона промпта
    prompt_template = ChatPromptTemplate.from_messages([
        SystemMessage(content="Ты полезный ассистент"),
        HumanMessage(content="{input}")
    ])

    # Формирование цепочки
    chain = prompt_template | llm

    # Выполнение запроса
    result = chain.invoke({"input": "Привет! Расскажи о себе"})

    return result.content

# Примеры использования
if __name__ == "__main__":
    # Простой чат
    print("=== Простой чат ===")
    response = chat_with_model("Расскажи о программировании на Python")
    print(response)

    # С использованием шаблона
    print("\n=== С шаблоном ===")
    try:
        response2 = chat_with_prompt_template()
        print(response2)
    except Exception as e:
        print(f"Ошибка в шаблоне: {e}")