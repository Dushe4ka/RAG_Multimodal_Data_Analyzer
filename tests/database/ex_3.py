from pymongo import MongoClient
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def connect_to_mongo():
    try:
        # Подключение к MongoDB
        client = MongoClient('mongodb://admin:Ujk,ebytw12357985@192.168.0.82:27017/')

        # Проверка соединения
        client.admin.command('ping')
        logging.info("Успешное подключение к MongoDB")

        return client

    except Exception as e:
        logging.error(f"Ошибка подключения к MongoDB: {e}")
        return None

def test_database_operations(client):
    try:
        # Выбор базы данных и коллекции
        db = client.test_db
        collection = db.test_collection

        # Вставка документа
        document = {
            "name": "Тестовый документ",
            "value": 42,
            "tags": ["тест", "пример"]
        }

        result = collection.insert_one(document)
        logging.info(f"Вставлен документ с ID: {result.inserted_id}")

        # Поиск документа
        found_document = collection.find_one({"_id": result.inserted_id})
        logging.info(f"Найден документ: {found_document}")

        # Обновление документа
        update_result = collection.update_one(
            {"_id": result.inserted_id},
            {"$set": {"updated": True}}
        )
        logging.info(f"Обновлено документов: {update_result.modified_count}")

        # Поиск всех документов
        all_documents = list(collection.find())
        logging.info(f"Все документы: {all_documents}")

        # Удаление документа
        delete_result = collection.delete_one({"_id": result.inserted_id})
        logging.info(f"Удалено документов: {delete_result.deleted_count}")

    except Exception as e:
        logging.error(f"Ошибка при работе с базой данных: {e}")

def main():
    logging.info("Запуск теста подключения к MongoDB...")

    # Подключение к MongoDB
    client = connect_to_mongo()

    if client:
        try:
            # Тестирование операций с БД
            test_database_operations(client)

            # Закрытие соединения
            client.close()
            logging.info("Соединение с MongoDB закрыто")

        except Exception as e:
            logging.error(f"Ошибка в основном цикле: {e}")
            client.close()

if __name__ == "__main__":
    main()