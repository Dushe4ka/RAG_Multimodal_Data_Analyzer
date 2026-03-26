# routes/statistics.py
import statistics
from typing import List
from fastmcp import FastMCP

def setup_statistics_routes(server: FastMCP):
    """Настройка статистических функций."""

    @server.tool
    def analyze_dataset(numbers: List[float]) -> dict:
        """Полный статистический анализ набора данных."""
        if not numbers:
            return {"error": "Пустой набор данных"}

        n = len(numbers)

        return {
            "dataset": numbers,
            "count": n,
            "sum": sum(numbers),
            "mean": statistics.mean(numbers),
            "median": statistics.median(numbers),
            "mode": statistics.mode(numbers) if len(set(numbers)) < n else "Нет моды",
            "range": max(numbers) - min(numbers),
            "min": min(numbers),
            "max": max(numbers),
            "variance": statistics.variance(numbers) if n > 1 else 0,
            "std_deviation": statistics.stdev(numbers) if n > 1 else 0,
            "quartiles": {
                "q1": statistics.quantiles(numbers, n=4)[0] if n >= 4 else None,
                "q2": statistics.median(numbers),
                "q3": statistics.quantiles(numbers, n=4)[2] if n >= 4 else None
            }
        }

    @server.tool
    def correlation_coefficient(x_values: List[float], y_values: List[float]) -> dict:
        """Вычислить коэффициент корреляции Пирсона между двумя наборами данных."""
        if len(x_values) != len(y_values):
            return {"error": "Наборы данных должны быть одинакового размера"}

        if len(x_values) < 2:
            return {"error": "Нужно минимум 2 точки данных"}

        try:
            correlation = statistics.correlation(x_values, y_values)

            # Интерпретация силы корреляции
            abs_corr = abs(correlation)
            if abs_corr >= 0.8:
                strength = "очень сильная"
            elif abs_corr >= 0.6:
                strength = "сильная"
            elif abs_corr >= 0.4:
                strength = "умеренная"
            elif abs_corr >= 0.2:
                strength = "слабая"
            else:
                strength = "очень слабая"

            direction = "положительная" if correlation > 0 else "отрицательная"

            return {
                "x_values": x_values,
                "y_values": y_values,
                "correlation_coefficient": correlation,
                "interpretation": {
                    "strength": strength,
                    "direction": direction,
                    "description": f"{strength} {direction} корреляция"
                }
            }
        except Exception as e:
            return {"error": f"Ошибка вычисления: {str(e)}"}