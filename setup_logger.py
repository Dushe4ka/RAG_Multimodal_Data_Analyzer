import logging
import sys
from pathlib import Path


def setup_logger(name: str, log_file: str | Path = "app.log", level=logging.INFO):
    """
    Создаёт и возвращает настроенный логгер.
    Автоматически создаёт папку logs/, если её нет.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)s | %(levelname)-8s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Создаём папку logs/, если её нет
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)  # Создаёт папку, если не существует

    # Полный путь к файлу лога
    file_path = log_dir / log_file

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(file_path, mode="a", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger