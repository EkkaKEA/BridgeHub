# Импорт библиотеки для работы с базой данных DuckDB
import duckdb
# Импорт модуля для работы с путями файловой системы
from pathlib import Path
# Импорт библиотеки для чтения Excel файлов
import openpyxl


# Путь к базе данных DuckDB (в корне проекта)
DB_PATH = Path(__file__).parent / "bridgehub.duckdb"

# Путь к файлу Excel с картой тегов Modbus
EXCEL_PATH = Path(__file__).parent / "КартаMB.xlsx"

# Названия листов для импорта
SHEETS = ["DI_Status", "DI_Config"]


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


# Функция импорта Modbus тегов из Excel в БД
def import_modbus_tags():
    # Открытие соединения с базой данных DuckDB
    con = duckdb.connect(str(DB_PATH))

    # Очистка таблицы ModbusTagMap перед импортом новых данных
    con.execute("DELETE FROM ModbusTagMap")

    # Счетчик для автоинкремента ID
    tag_id = 1

    # Импорт данных из каждого листа
    for sheet_name in SHEETS:
        # Чтение данных из листа
        rows = read_sheet(sheet_name)
        # Вставка данных в таблицу ModbusTagMap
        for row in rows:
            # Проверка, что строка не пустая
            if row[0] is not None:
                # Вставка записи в таблицу ModbusTagMap с автоинкрементом ID
                con.execute("""
                    INSERT INTO ModbusTagMap (id, tag_name, data_type, binding, segment, modbus_address, unit, description, access_mode, device, group_name, scaling, alarm, notes, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    tag_id,           # id (автоинкремент)
                    row[1],           # tag_name (Tag Name)
                    row[2],           # data_type (Data Type)
                    row[3],           # binding (привязка)
                    row[4],           # segment (Segment)
                    int(row[5]) if row[5] is not None else None,  # modbus_address (Modbus Address)
                    row[6],           # unit (Unit)
                    row[7],           # description (Description)
                    row[8],           # access_mode (Read/Write)
                    row[9],           # device (Device)
                    row[10],          # group_name (Group)
                    row[11],          # scaling (Scaling)
                    row[12],          # alarm (Alarm)
                    row[13],          # notes (Notes)
                    sheet_name,       # source (источник данных)
                ])
                # Увеличение счетчика ID
                tag_id += 1

    # Подсчет количества импортированных тегов
    count = con.execute("SELECT COUNT(*) FROM ModbusTagMap").fetchone()[0]

    # Закрытие соединения с базой данных
    con.close()

    # Вывод результата
    print(f"Imported {count} Modbus tags from {EXCEL_PATH}")


# Точка входа — выполнение только при прямом запуске скрипта
if __name__ == "__main__":
    import_modbus_tags()
