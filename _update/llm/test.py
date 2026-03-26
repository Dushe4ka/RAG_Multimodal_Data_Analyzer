from _update.llm.agent import llm
from langchain.agents import create_agent 
from _update.tools.custom_tools import tools

agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt="Ты полезный ИИ ассистент, твоя задача помогать пользователю. RULES: 1) Ответ давай не в MARKDOWN"
)

# Вызов через .invoke() (не .run())
response = agent.invoke({
    "messages": [
        {"role": "user", "content": "Какая погода в Темрюке?"}
    ]
})

# Извлекаем текст ответа
ai_message = response["messages"][-1]
print(ai_message.content)

