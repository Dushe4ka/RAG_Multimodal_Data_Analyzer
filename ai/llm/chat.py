"""
Чат с LLM с опциональной персистентной памятью в MongoDB.
Соответствует документации LangChain: ChatOpenAI, BaseChatMessageHistory.
"""
from typing import AsyncGenerator, List, Literal, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_community.chat_message_histories import MongoDBChatMessageHistory

from setup_logger import setup_logger
from config import settings, settings_llm

logger = setup_logger("llm_chat", log_file="llms.log")

# Опционально: для провайдера DeepSeek (раскомментировать при установке langchain-deepseek)
# from langchain_deepseek import ChatDeepSeek

SYSTEM_PROMPT = """Ты — внутренний менеджер компании Amvera Cloud.
Отвечаешь по делу без лишних вступлений.
Свой ответ, в первую очередь, ориентируй на переданный контекст.
Если информации недостаточно — пробуй получить ответы из своей базы знаний."""


class ChatWithAI:
    """
    Класс для взаимодействия с LLM (LangChain ChatOpenAI и др.).
    Поддерживает потоковый вывод и персистентную историю диалога в MongoDB.
    """

    def __init__(
        self,
        provider: Literal["deepseek", "local"] = "local",
        model: str = settings_llm.QWEN_THINK,
        api_url: str = settings_llm.QWEN_THINK_URL,
        api_key: str = settings.LLM_API_KEY,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        memory_on: bool = False,
        session_id: Optional[str] = None,
        mongodb_url: Optional[str] = None,
    ):
        """
        Args:
            provider: Провайдер LLM ("local" или "deepseek").
            model: Имя модели.
            api_url: Base URL API.
            api_key: API ключ.
            temperature: Температура генерации.
            max_tokens: Максимум токенов в ответе.
            memory_on: Включить сохранение истории в MongoDB.
            session_id: Идентификатор сессии чата (обязателен при memory_on).
                        Например: "user_id:chat_id" — чтобы при входе в чат подгружать историю.
            mongodb_url: URL MongoDB для истории (по умолчанию MONGODB_URL_DEV).
        """
        self.provider = provider
        self.model = model
        self.api_url = api_url
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.memory_on = memory_on
        self.session_id = session_id
        self._mongodb_url = mongodb_url or settings.MONGODB_URL_DEV

        if self.memory_on and not self.session_id:
            raise ValueError("При memory_on=True необходимо передать session_id (например user_id:chat_id).")

        # Память: MongoDBChatMessageHistory сохраняет историю в MongoDB
        if self.memory_on and self.session_id:
            self.memory: Optional[MongoDBChatMessageHistory] = MongoDBChatMessageHistory(
                connection_string=self._mongodb_url,
                session_id=self.session_id,
                database_name="chat_history",
                collection_name="message_store",
            )
            logger.info("🧠 Память включена, история сохраняется в MongoDB.")
        else:
            self.memory = None
            logger.info("🧠 Память выключена.")

        # Инициализация LLM по документации LangChain
        common_kwargs = dict(
            api_key=self.api_key,
            model=self.model,
            base_url=self.api_url,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            max_retries=3,
        )
        if provider == "local":
            logger.info(f"🔧 Инициализация Local-модели: {self.model}")
            self.llm = ChatOpenAI(**common_kwargs)
        elif provider == "deepseek":
            try:
                from langchain_deepseek import ChatDeepSeek  # type: ignore[import-untyped]
                logger.info(f"🔧 Инициализация DeepSeek: {self.model}")
                self.llm = ChatDeepSeek(**common_kwargs)
            except ImportError:
                logger.warning("langchain-deepseek не установлен, используется ChatOpenAI с base_url.")
                self.llm = ChatOpenAI(**common_kwargs)
        else:
            raise ValueError(f"Неподдерживаемый провайдер: {provider}")

        logger.info(f"✅ Модель {provider} успешно инициализирована")

    def _build_messages(self, formatted_context: str, query: str) -> List[BaseMessage]:
        """Собирает список сообщений: system + (история из БД) + текущий запрос."""
        system_message = SystemMessage(content=SYSTEM_PROMPT)
        human_content = f"Вопрос: {query}\nКонтекст: {formatted_context}. Ответ форматируй в markdown!"
        human_message = HumanMessage(content=human_content)

        if self.memory is not None:
            history = self.memory.messages
            return [system_message, *history, human_message]
        return [system_message, human_message]

    async def stream_response(
        self,
        formatted_context: str,
        query: str,
    ) -> AsyncGenerator[str, None]:
        """
        Потоковый ответ с сохранением реплик в MongoDB при включённой памяти.
        """
        try:
            messages = self._build_messages(formatted_context, query)
            human_content = messages[-1].content if messages else ""
            human_message = HumanMessage(content=human_content)

            if self.memory is not None:
                self.memory.add_message(human_message)

            logger.info(f"🔄 Стриминг ответа для запроса: «{query[:50]}...»")

            full_content: List[str] = []
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    full_content.append(chunk.content)
                    yield chunk.content

            if self.memory is not None and full_content:
                self.memory.add_message(AIMessage(content="".join(full_content)))

            logger.info("✅ Стриминг ответа завершён")

        except Exception as e:
            logger.error(f"❌ Ошибка при стриминге: {e}")
            yield f"Произошла ошибка при обработке запроса: {str(e)}"

    def generate_text(self, formatted_context: str, query: str) -> str:
        """
        Синхронная генерация полного ответа с сохранением в MongoDB при memory_on.
        """
        try:
            messages = self._build_messages(formatted_context, query)
            human_content = messages[-1].content if messages else ""
            human_message = HumanMessage(content=human_content)

            if self.memory is not None:
                self.memory.add_message(human_message)

            response = self.llm.invoke(messages)
            content = response.content if hasattr(response, "content") else str(response)

            if self.memory is not None:
                self.memory.add_message(AIMessage(content=content))

            logger.info("✅ Ответ сгенерирован")
            return content

        except Exception as e:
            logger.error(f"❌ Ошибка при генерации: {e}")
            return f"Произошла ошибка при обработке запроса: {str(e)}"

    def get_history(self) -> List[BaseMessage]:
        """
        Возвращает историю диалога для текущей сессии (из MongoDB).
        Используйте в API при открытии чата, чтобы отдать фронту все сообщения.
        """
        if self.memory is None:
            return []
        return self.memory.messages

    def clear_history(self) -> None:
        """Очищает историю текущей сессии в MongoDB."""
        if self.memory is not None:
            self.memory.clear()
            logger.info("История сессии очищена.")
