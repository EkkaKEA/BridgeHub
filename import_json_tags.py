# Импорт библиотеки для работы с базой данных DuckDB
import duckdb
# Импорт библиотеки для работы с JSON-файлами
import json
# Импорт модуля для работы с путями файловой системы
from pathlib import Path

# Путь к базе данных DuckDB (в корне проекта)
DB_PATH = Path(__file__).parent / "bridgehub.duckdb"


# Функция инициализации таблицы JsonData
def init_db(con):
    # Получение списка существующих таблиц
    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    # Если таблицы JsonData нет — создаём её
    if "JsonData" not in tables:
        con.execute("""
            CREATE TABLE JsonData (
                id INTEGER PRIMARY KEY,
                device_id VARCHAR,
                tag_id VARCHAR NOT NULL,
                tag_name VARCHAR,
                value DOUBLE,
                quality VARCHAR,
                units VARCHAR,
                data_type VARCHAR,
                value_timestamp TIMESTAMP,
                batch_timestamp TIMESTAMP,
                linked_tag_id INTEGER
            )
        """)
        print("Created table JsonData")


# Функция поиска связанного тега в ModbusTagMap/OPCUATagMap по имени
def find_linked_tag(con, tag_id):
    # Поиск тега в обеих таблицах определений
    result = con.execute(
        "SELECT id FROM ModbusTagMap WHERE tag_name = ? UNION ALL "
        "SELECT id FROM OPCUATagMap WHERE tag_name = ?",
        [tag_id, tag_id]
    ).fetchone()
    # Возвращаем id найденного тега или None
    return result[0] if result else None


# Функция импорта тегов из JSON-файла в таблицу JsonData
def import_json_tags(json_path):
    # Открытие и чтение JSON-файла
    with open(json_path, "r", encoding="utf-8") as f:
        # Парсинг JSON в словарь
        data = json.load(f)

    # Извлечение метаданных пакета из верхнего уровня JSON
    device_id = data.get("device_id")
    batch_timestamp = data.get("timestamp_batch")
    # Получение массива тегов
    tags = data.get("tags", [])

    # Открытие соединения с базой данных DuckDB
    con = duckdb.connect(str(DB_PATH))
    # Инициализация таблицы (создание если не существует)
    init_db(con)

    # Получение максимального id для автоинкремента
    max_id = con.execute("SELECT COALESCE(MAX(id), 0) FROM JsonData").fetchone()[0]
    # Счетчик для автоинкремента ID
    tag_id_counter = max_id + 1

    # Счетчик импортированных тегов
    imported = 0
    # Перебор всех тегов из JSON-массива
    for tag in tags:
        # Извлечение id тега (обязательное поле)
        raw_id = tag.get("id")
        # Пропуск тегов без id
        if raw_id is None:
            continue

        # Извлечение имени тега (опциональное поле)
        tag_name = tag.get("name")
        # Поиск связанного тега в таблицах определений
        linked_tag_id = find_linked_tag(con, tag_name or raw_id)

        # Вставка записи в таблицу JsonData
        con.execute("""
            INSERT INTO JsonData (id, device_id, tag_id, tag_name, value, quality, units, data_type, value_timestamp, batch_timestamp, linked_tag_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            tag_id_counter,          # id (автоинкремент)
            device_id,               # device_id (идентификатор устройства)
            str(raw_id),             # tag_id (идентификатор тега)
            tag_name,                # tag_name (человекочитаемое имя)
            tag.get("value"),        # value (значение тега)
            tag.get("quality"),      # quality (качество: Good/Bad/Uncertain)
            tag.get("units"),        # units (единицы измерения)
            tag.get("data_type"),    # data_type (тип данных)
            tag.get("timestamp"),    # value_timestamp (время значения)
            batch_timestamp,         # batch_timestamp (время пакета)
            linked_tag_id,           # linked_tag_id (ссылка на TagMap)
        ])
        # Увеличение счетчика ID
        tag_id_counter += 1
        # Увеличение счетчика импортированных тегов
        imported += 1

    # Закрытие соединения с базой данных
    con.close()
    # Вывод результата
    print(f"Imported {imported} tags from {json_path}")


# Точка входа — выполнение только при прямом запуске скрипта
if __name__ == "__main__":
    # Импорт модуля для работы с аргументами командной строки
    import sys
    # Проверка наличия аргумента с путём к JSON-файлу
    if len(sys.argv) < 2:
        print("Usage: python import_json_tags.py <path_to_json>")
        sys.exit(1)
    # Запуск импорта тегов из указанного JSON-файла
    import_json_tags(sys.argv[1])
