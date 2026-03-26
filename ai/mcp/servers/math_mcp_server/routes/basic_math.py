import math
from datetime import datetime
from fastmcp import FastMCP


def setup_basic_math_routes(server: FastMCP):
    """Настройка базовых математических операций."""

    @server.tool
    def calculate_basic(expression: str) -> dict:
        """Вычислить базовое математическое выражение."""
        try:
            # Безопасное вычисление только математических выражений
            allowed_names = {
                k: v for k, v in math.__dict__.items()
                if not k.startswith("__")
            }
            allowed_names.update({"abs": abs, "round": round, "pow": pow})

            result = eval(expression, {"__builtins__": {}}, allowed_names)
            return {
                "expression": expression,
                "result": result,
                "type": type(result).__name__,
                "calculated_at": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "expression": expression,
                "error": str(e),
                "calculated_at": datetime.now().isoformat()
            }

    @server.tool
    def solve_quadratic(a: float, b: float, c: float) -> dict:
        """Решить квадратное уравнение ax² + bx + c = 0."""
        discriminant = b**2 - 4*a*c

        if discriminant > 0:
            x1 = (-b + math.sqrt(discriminant)) / (2*a)
            x2 = (-b - math.sqrt(discriminant)) / (2*a)
            return {
                "equation": f"{a}x² + {b}x + {c} = 0",
                "discriminant": discriminant,
                "roots": [x1, x2],
                "type": "two_real_roots"
            }
        elif discriminant == 0:
            x = -b / (2*a)
            return {
                "equation": f"{a}x² + {b}x + {c} = 0",
                "discriminant": discriminant,
                "roots": [x],
                "type": "one_real_root"
            }
        else:
            real_part = -b / (2*a)
            imaginary_part = math.sqrt(abs(discriminant)) / (2*a)
            return {
                "equation": f"{a}x² + {b}x + {c} = 0",
                "discriminant": discriminant,
                "roots": [
                    f"{real_part} + {imaginary_part}i",
                    f"{real_part} - {imaginary_part}i"
                ],
                "type": "complex_roots"
            }

    @server.tool
    def factorial(n: int) -> dict:
        """Вычислить факториал числа."""
        if n < 0:
            return {"error": "Факториал не определен для отрицательных чисел"}

        result = math.factorial(n)
        return {
            "number": n,
            "factorial": result,
            "formula": f"{n}!",
            "steps": " × ".join(str(i) for i in range(1, n + 1)) if n > 0 else "1"
        }
    