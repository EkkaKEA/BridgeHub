# Импорт библиотеки для работы с базой данных DuckDB
import duckdb
# Импорт модуля для работы с путями файловой системы
from pathlib import Path
# Импорт библиотеки для регулярных выражений (парсинг .DB файлов)
import re

# Путь к базе данных DuckDB (в корне проекта)
DB_PATH = Path(__file__).parent / "bridgehub.duckdb"


# Функция инициализации таблицы S7TagMap
def init_db(con):
    # Получение списка существующих таблиц
    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    # Если таблицы S7TagMap нет — создаём её
    if "S7TagMap" not in tables:
        con.execute("""
            CREATE TABLE S7TagMap (
                id INTEGER PRIMARY KEY,
                tag_name VARCHAR NOT NULL,
                db_number INTEGER,
                byte_offset INTEGER,
                bit_offset INTEGER,
                data_type VARCHAR,
                size INTEGER,
                area VARCHAR,
                array_start INTEGER,
                array_end INTEGER,
                description VARCHAR,
                device VARCHAR,
                default_value VARCHAR
            )
        """)
        print("Created table S7TagMap")


# Функция парсинга .DB файла TIA Portal
def parse_db_file(file_path):
    # Открытие и чтение .DB файла
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Список для хранения распарсенных тегов
    tags = []
    # Текущий уровень вложенности (для STRUCT)
    indent_level = 0
    # Текущий путь к структуре (для вложенных структур)
    struct_path = []

    # Регулярное выражение для определения номера DB блока из заголовка
    db_match = re.search(r"DATA_BLOCK\s+[\"']?(\w+)[\"']?", content)
    # Если не найден заголовок DATA_BLOCK — вернуть пустой список
    if not db_match:
        return tags

    # Имя DB блока (может быть числом или строкой)
    db_name = db_match.group(1)
    # Если имя — число, используем его как номер DB
    try:
        db_number = int(db_name)
    except ValueError:
        db_number = 0

    # Регулярное выражение для парсинга переменных
    # Формат: Имя : Тип := Значение; // Описание
    var_pattern = re.compile(
        r"^\s*(\w+)"                          # Имя переменной
        r"(?:\[(\d+)\.\.(\d+)\])?"            # Опциональный массив [start..end]
        r"\s*:\s*(\w+)"                       # Тип данных
        r"(?:\s*:=\s*([^;]+?))?"              # Опциональное значение := value
        r"\s*;"                               # Точка с запятой
        r"(?:\s*//\s*(.+?))?"                 # Опциональный комментарий
        r"\s*$",                              # Конец строки
        re.MULTILINE
    )

    # Регулярное выражение для определения начала/конца STRUCT
    struct_start = re.compile(r"^\s*STRUCT\s*$", re.MULTILINE)
    struct_end = re.compile(r"^\s*END_STRUCT\s*$", re.MULTILINE)

    # Регулярное выражение для парсинга указателей (P#DBx.DBXoffset BIT size)
    pointer_pattern = re.compile(
        r"P#DB(\d+)\.DBX(\d+)\.(\d+)\s+(BYTE|WORD|DWORD|REAL|INT)\s+(\d+)",
        re.IGNORECASE
    )

    # Разбиение.content на строки
    lines = content.split("\n")

    # Текущий контекст (текст между STRUCT и END_STRUCT)
    in_struct = False
    # Текущий уровень вложенности структуры
    struct_depth = 0

    # Перебор всех строк
    for line in lines:
        # Проверка на начало структуры
        if struct_start.search(line):
            struct_depth += 1
            in_struct = True
            continue

        # Проверка на конец структуры
        if struct_end.search(line):
            struct_depth -= 1
            if struct_depth == 0:
                in_struct = False
            continue

        # Парсинг переменных (только внутри STRUCT)
        if in_struct or struct_depth > 0:
            var_match = var_pattern.search(line)
            if var_match:
                # Извлечение компонентов переменной
                var_name = var_match.group(1)
                array_start = int(var_match.group(2)) if var_match.group(2) else None
                array_end = int(var_match.group(3)) if var_match.group(3) else None
                data_type = var_match.group(4)
                default_value = var_match.group(5).strip() if var_match.group(5) else None
                description = var_match.group(6).strip() if var_match.group(6) else None

                # Определение размера данных по типу
                type_sizes = {
                    "BOOL": 1,
                    "BYTE": 1,
                    "WORD": 2,
                    "DWORD": 4,
                    "INT": 2,
                    "DINT": 4,
                    "REAL": 4,
                    "LREAL": 8,
                    "TIME": 4,
                    "DATE": 2,
                    "TOD": 4,
                    "STRING": 256,
                }
                size = type_sizes.get(data_type.upper(), 1)

                # Если массив — умножаем размер на количество элементов
                if array_start is not None and array_end is not None:
                    array_count = array_end - array_start + 1
                    size = size * array_count
                else:
                    array_count = None

                # Добавление тега в список
                tags.append({
                    "tag_name": var_name,
                    "db_number": db_number,
                    "byte_offset": None,  # Будет вычислен при импорте
                    "bit_offset": None,
                    "data_type": data_type,
                    "size": size,
                    "area": "DB",
                    "array_start": array_start,
                    "array_end": array_end,
                    "description": description,
                    "device": None,
                    "default_value": default_value,
                })

    # Если переменные найдены вне STRUCT — парсим их тоже
    if not tags:
        for line in lines:
            var_match = var_pattern.search(line)
            if var_match:
                var_name = var_match.group(1)
                array_start = int(var_match.group(2)) if var_match.group(2) else None
                array_end = int(var_match.group(3)) if var_match.group(3) else None
                data_type = var_match.group(4)
                default_value = var_match.group(5).strip() if var_match.group(5) else None
                description = var_match.group(6).strip() if var_match.group(6) else None

                type_sizes = {
                    "BOOL": 1,
                    "BYTE": 1,
                    "WORD": 2,
                    "DWORD": 4,
                    "INT": 2,
                    "DINT": 4,
                    "REAL": 4,
                    "LREAL": 8,
                    "TIME": 4,
                    "DATE": 2,
                    "TOD": 4,
                    "STRING": 256,
                }
                size = type_sizes.get(data_type.upper(), 1)

                if array_start is not None and array_end is not None:
                    array_count = array_end - array_start + 1
                    size = size * array_count
                else:
                    array_count = None

                tags.append({
                    "tag_name": var_name,
                    "db_number": db_number,
                    "byte_offset": None,
                    "bit_offset": None,
                    "data_type": data_type,
                    "size": size,
                    "area": "DB",
                    "array_start": array_start,
                    "array_end": array_end,
                    "description": description,
                    "device": None,
                    "default_value": default_value,
                })

    return tags


# Функция вычисления смещений (byte_offset) для тегов в DB
def calculate_offsets(tags):
    # Текущее смещение в байтах
    current_offset = 0
    # Перебор всех тегов
    for tag in tags:
        # Установка текущего смещения
        tag["byte_offset"] = current_offset
        # Если тип BOOL — вычисляем bit_offset
        if tag["data_type"].upper() == "BOOL":
            tag["bit_offset"] = current_offset % 8
            # Для BOOL не увеличиваем смещение на 1 байт
            # (несколько BOOL могут быть в одном байте)
        else:
            tag["bit_offset"] = None
            # Увеличение смещения на размер данных
            current_offset += tag["size"]
    return tags


# Функция импорта S7 тегов из .DB файла в БД
def import_s7_tags(db_file_path, device_name=None):
    # Парсинг .DB файла
    tags = parse_db_file(db_file_path)

    # Если теги не найдены — вывод сообщения
    if not tags:
        print(f"No tags found in {db_file_path}")
        return

    # Вычисление смещений для тегов
    tags = calculate_offsets(tags)

    # Открытие соединения с базой данных DuckDB
    con = duckdb.connect(str(DB_PATH))
    # Инициализация таблицы (создание если не существует)
    init_db(con)

    # Получение максимального id для автоинкремента
    max_id = con.execute("SELECT COALESCE(MAX(id), 0) FROM S7TagMap").fetchone()[0]
    # Счетчик для автоинкремента ID
    tag_id = max_id + 1

    # Вставка каждого тега в таблицу S7TagMap
    for tag in tags:
        con.execute("""
            INSERT INTO S7TagMap (id, tag_name, db_number, byte_offset, bit_offset, data_type, size, area, array_start, array_end, description, device, default_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            tag_id,
            tag["tag_name"],
            tag["db_number"],
            tag["byte_offset"],
            tag["bit_offset"],
            tag["data_type"],
            tag["size"],
            tag["area"],
            tag["array_start"],
            tag["array_end"],
            tag["description"],
            device_name,
            tag["default_value"],
        ])
        tag_id += 1

    # Подсчет количества импортированных тегов
    count = len(tags)
    # Закрытие соединения с базой данных
    con.close()
    # Вывод результата
    print(f"Imported {count} S7 tags from {db_file_path}")


# Точка входа — выполнение только при прямом запуске скрипта
if __name__ == "__main__":
    # Импорт модуля для работы с аргументами командной строки
    import sys
    # Проверка наличия аргумента с путём к .DB файлу
    if len(sys.argv) < 2:
        print("Usage: python import_s7_tags.py <path_to.DB> [device_name]")
        sys.exit(1)
    # Получение опционального имени устройства
    device = sys.argv[2] if len(sys.argv) > 2 else None
    # Запуск импорта тегов из указанного .DB файла
    import_s7_tags(sys.argv[1], device)
