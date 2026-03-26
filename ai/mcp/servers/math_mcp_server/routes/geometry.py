# routes/geometry.py
import math
from fastmcp import FastMCP

def setup_geometry_routes(server: FastMCP):
    """Настройка геометрических функций."""

    @server.tool
    def circle_properties(radius: float) -> dict:
        """Вычислить свойства окружности по радиусу."""
        if radius <= 0:
            return {"error": "Радиус должен быть положительным числом"}

        return {
            "radius": radius,
            "diameter": 2 * radius,
            "circumference": 2 * math.pi * radius,
            "area": math.pi * radius**2,
            "formulas": {
                "circumference": "2πr",
                "area": "πr²"
            }
        }

    @server.tool
    def triangle_area(base: float, height: float) -> dict:
        """Вычислить площадь треугольника."""
        if base <= 0 or height <= 0:
            return {"error": "Основание и высота должны быть положительными"}

        area = 0.5 * base * height
        return {
            "base": base,
            "height": height,
            "area": area,
            "formula": "½ × основание × высота"
        }

    @server.tool
    def distance_between_points(x1: float, y1: float, x2: float, y2: float) -> dict:
        """Вычислить расстояние между двумя точками."""
        distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

        return {
            "point1": {"x": x1, "y": y1},
            "point2": {"x": x2, "y": y2},
            "distance": distance,
            "formula": "√[(x₂-x₁)² + (y₂-y₁)²]"
        }