# Импорт библиотеки для работы с базой данных DuckDB
import duckdb
# Импорт модуля для работы с путями файловой системы
from pathlib import Path
# Импорт библиотеки для чтения Excel файлов
import openpyxl


# Путь к базе данных DuckDB (в корне проекта)
DB_PATH = Path(__file__).parent / "bridgehub.duckdb"

# Путь к файлу Excel с картой тегов MQTT
EXCEL_PATH = Path(__file__).parent / "КартаMQTT.xlsx"


# Функция инициализации таблицы MQTTTagMap
def init_db(con):
    # Получение списка существующих таблиц
    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    # Если таблицы MQTTTagMap нет — создаём её
    if "MQTTTagMap" not in tables:
        con.execute("""
            CREATE TABLE MQTTTagMap (
                id INTEGER PRIMARY KEY,
                tag_name VARCHAR NOT NULL,
                topic VARCHAR NOT NULL,
                json_path VARCHAR,
                data_type VARCHAR,
                unit VARCHAR,
                description VARCHAR,
                access_mode VARCHAR,
                broker_id VARCHAR,
                group_name VARCHAR,
                scaling VARCHAR,
                alarm VARCHAR,
                notes VARCHAR,
                payload_format VARCHAR DEFAULT 'json'
            )
        """)
        print("Created table MQTTTagMap")


# Функция чтения данных из Excel листа по индексу
def read_sheet(wb, sheet_index):
    ws = wb.worksheets[sheet_index]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    return ws.title, rows


# Функция импорта MQTT тегов из Excel в БД
def import_mqtt_tags():
    # Открытие Excel файла
    wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)

    # Количество листов в книге
    sheet_count = len(wb.worksheets)
    print(f"Sheets found: {sheet_count}")

    # Открытие соединения с базой данных DuckDB
    con = duckdb.connect(str(DB_PATH))

    # Инициализация таблицы MQTTTagMap
    init_db(con)

    # Очистка таблицы MQTTTagMap перед импортом новых данных
    con.execute("DELETE FROM MQTTTagMap")

    # Счетчик для автоинкремента ID
    tag_id = 1

    # Импорт данных из каждого листа по индексу
    for i in range(sheet_count):
        sheet_name, rows = read_sheet(wb, i)
        print(f"  [{i}] {sheet_name}: {len(rows)} rows")

        # Вставка данных в таблицу MQTTTagMap
        for row in rows:
            # Проверка, что строка не пустая (имя тега обязательно)
            if row[0] is not None:
                # Вставка записи в таблицу MQTTTagMap с автоинкрементом ID
                con.execute("""
                    INSERT INTO MQTTTagMap (id, tag_name, topic, json_path, data_type, unit, description, access_mode, broker_id, group_name, scaling, alarm, notes, payload_format)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    tag_id,            # id (автоинкремент)
                    row[0],            # tag_name (Tag Name)
                    row[1],            # topic (MQTT Topic)
                    row[2],            # json_path (JSON Path для извлечения значения)
                    row[3],            # data_type (Data Type)
                    row[4],            # unit (Unit)
                    row[5],            # description (Description)
                    row[6],            # access_mode (Read/Write)
                    row[7],            # broker_id (Broker ID)
                    row[8],            # group_name (Group)
                    row[9],            # scaling (Scaling)
                    row[10],           # alarm (Alarm)
                    row[11],           # notes (Notes)
                    row[12] if row[12] else "json",  # payload_format (json/csv/raw)
                ])
                # Увеличение счетчика ID
                tag_id += 1

    # Закрытие Excel файла
    wb.close()

    # Подсчет количества импортированных тегов
    count = con.execute("SELECT COUNT(*) FROM MQTTTagMap").fetchone()[0]

    # Закрытие соединения с базой данных
    con.close()

    # Вывод результата
    print(f"Imported {count} MQTT tags from {EXCEL_PATH}")


# Точка входа — выполнение только при прямом запуске скрипта
if __name__ == "__main__":
    import_mqtt_tags()
