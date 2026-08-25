# Импорт библиотеки для работы с базой данных DuckDB
import duckdb
# Импорт модуля для работы с путями файловой системы
from pathlib import Path
# Импорт библиотеки для чтения Excel файлов
import openpyxl


# Путь к базе данных DuckDB (в корне проекта)
DB_PATH = Path(__file__).parent / "bridgehub.duckdb"

# Путь к файлу Excel с картой тегов OPC UA
EXCEL_PATH = Path(__file__).parent / "КартаOPCUA.xlsx"

# Названия листов для импорта
SHEETS = ["OPC_Tags"]


# Функция чтения данных из Excel листа
def read_sheet(sheet_name):
    # Открытие Excel файла
    wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
    # Получение листа по имени
    ws = wb[sheet_name]
    # Чтение всех строк (пропускаем заголовок)
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    # Закрытие Excel файла
    wb.close()
    # Возвращаем данные
    return rows


# Функция импорта OPC UA тегов из Excel в БД
def import_opcua_tags():
    # Открытие соединения с базой данных DuckDB
    con = duckdb.connect(str(DB_PATH))

    # Очистка таблицы OPCUATagMap перед импортом новых данных
    con.execute("DELETE FROM OPCUATagMap")

    # Счетчик для автоинкремента ID
    tag_id = 1

    # Импорт данных из каждого листа
    for sheet_name in SHEETS:
        # Чтение данных из листа
        rows = read_sheet(sheet_name)
        # Вставка данных в таблицу OPCUATagMap
        for row in rows:
            # Проверка, что строка не пустая
            if row[0] is not None:
                # Вставка записи в таблицу OPCUATagMap с автоинкрементом ID
                con.execute("""
                    INSERT INTO OPCUATagMap (id, tag_name, data_type, opc_node_id, unit, description, access_mode, server_url, group_name, scaling, alarm, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    tag_id,           # id (автоинкремент)
                    row[1],           # tag_name (Tag Name)
                    row[2],           # data_type (Data Type)
                    row[3],           # opc_node_id (OPC Node ID)
                    row[4],           # unit (Unit)
                    row[5],           # description (Description)
                    row[6],           # access_mode (Read/Write)
                    row[7],           # server_url (Server URL)
                    row[8],           # group_name (Group)
                    row[9],           # scaling (Scaling)
                    row[10],          # alarm (Alarm)
                    row[11],          # notes (Notes)
                ])
                # Увеличение счетчика ID
                tag_id += 1

    # Подсчет количества импортированных OPC UA тегов
    count = con.execute("SELECT COUNT(*) FROM OPCUATagMap").fetchone()[0]

    # Закрытие соединения с базой данных
    con.close()

    # Вывод результата
    print(f"Imported {count} OPC UA tags from {EXCEL_PATH}")


# Точка входа — выполнение только при прямом запуске скрипта
if __name__ == "__main__":
    import_opcua_tags()
