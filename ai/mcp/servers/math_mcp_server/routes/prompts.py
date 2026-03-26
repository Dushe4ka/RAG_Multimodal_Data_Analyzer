# routes/prompts.py
from fastmcp import FastMCP


def setup_math_prompts(server: FastMCP):
    """Настройка математических промптов."""

    @server.prompt
    def explain_solution(problem: str, solution: str, level: str = "intermediate") -> str:
        """Промпт для объяснения математического решения."""

        level_instructions = {
            "beginner": "Объясни очень простыми словами, как будто учишь школьника",
            "intermediate": "Дай подробное объяснение с промежуточными шагами",
            "advanced": "Включи математическое обоснование и альтернативные методы решения"
        }

        instruction = level_instructions.get(level, level_instructions["intermediate"])

        return f"""
Ты математический преподаватель. {instruction}.

Задача: {problem}
Решение: {solution}

Твоя задача:
1. Объясни каждый шаг решения
2. Укажи какие математические правила применялись
3. Покажи почему именно так решается задача
4. Дай советы для решения похожих задач

Используй ясный язык и приводи примеры где это уместно.
"""

    @server.prompt
    def create_practice_problems(topic: str, difficulty: str = "medium", count: int = 5) -> str:
        """Промпт для создания практических задач."""

        difficulty_descriptions = {
            "easy": "простые задачи для начинающих",
            "medium": "задачи среднего уровня сложности",
            "hard": "сложные задачи для продвинутых учеников"
        }

        diff_desc = difficulty_descriptions.get(difficulty, "задачи среднего уровня")

        return f"""
                Создай {count} {diff_desc} по теме "{topic}".
                
                Требования:
                1. Каждая задача должна иметь четкое условие
                2. Укажи правильный ответ для каждой задачи
                3. Задачи должны быть разнообразными
                4. Приведи краткое решение для каждой
                
                Формат:
                Задача 1: [условие]
                Ответ: [правильный ответ]
                Решение: [краткие шаги]
                
                Тема: {topic}
                Сложность: {difficulty}
                Количество: {count}
                """
