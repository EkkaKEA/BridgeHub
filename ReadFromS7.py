# Импорт модуля для работы со временем (задержки между опросами)
import time
# Импорт библиотеки для работы с базой данных DuckDB
import duckdb
# Импорт клиента S7CommPlus для S7-1200/1500
from s7commplus import Client
# Импорт утилит для конвертации данных
from s7.util import get_bool, get_int, get_real, get_dword, get_byte
# Импорт библиотеки для чтения YAML-конфигурации
import yaml
# Импорт модуля для работы с путями файловой системы
from pathlib import Path

# Путь к базе данных DuckDB (в корне проекта)
DB_PATH = Path(__file__).parent / "bridgehub.duckdb"

# Путь к файлу конфигурации (рядом со скриптом)
CONFIG_PATH = Path(__file__).parent / "config.yaml"


# Функция загрузки конфигурации из YAML-файла
def load_config(path):
    # Открытие и чтение YAML-файла
    with open(path, "r", encoding="utf-8") as f:
        # Парсинг YAML и возвращение словаря
        return yaml.safe_load(f)


# Функция инициализации таблицы S7Data
def init_db(con):
    # Проверка существования таблицы S7Data
    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    if "S7Data" not in tables:
        con.execute("""
            CREATE TABLE S7Data (
                id INTEGER PRIMARY KEY,
                tag_id INTEGER NOT NULL,
                value DOUBLE,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Created table S7Data")


# Функция загрузки карты тегов S7 из БД
def load_s7_tag_map(con, device_name=None):
    # Формирование запроса в зависимости от фильтра по устройству
    if device_name:
        result = con.execute(
            "SELECT id, tag_name, db_number, byte_offset, bit_offset, data_type, size FROM S7TagMap WHERE device = ?",
            [device_name]
        ).fetchall()
    else:
        result = con.execute(
            "SELECT id, tag_name, db_number, byte_offset, bit_offset, data_type, size FROM S7TagMap"
        ).fetchall()
    # Возвращаем список словарей с данными тегов
    return [{"id": row[0], "tag_name": row[1], "db_number": row[2], "byte_offset": row[3], "bit_offset": row[4], "data_type": row[5], "size": row[6]} for row in result]


# Функция конвертации прочитанных байтов в значение по типу данных
def convert_value(data, data_type, byte_offset=0, bit_offset=0):
    # Конвертация в зависимости от типа данных
    if data_type.upper() == "BOOL":
        # Чтение булева значения из бита
        return get_bool(data, byte_offset, bit_offset)
    elif data_type.upper() == "BYTE":
        # Чтение байта
        return get_byte(data, byte_offset)
    elif data_type.upper() == "INT":
        # Чтение 16-битного целого (знакового)
        return get_int(data, byte_offset)
    elif data_type.upper() == "DINT":
        # Чтение 32-битного целого (знакового)
        return get_dword(data, byte_offset)
    elif data_type.upper() == "REAL":
        # Чтение 32-битного числа с плавающей запятой
        return get_real(data, byte_offset)
    elif data_type.upper() == "WORD":
        # Чтение 16-битного беззнакового
        return get_word(data, byte_offset)
    elif data_type.upper() == "DWORD":
        # Чтение 32-битного беззнакового
        return get_dword(data, byte_offset)
    else:
        # Неизвестный тип — возвращаем как есть
        return data


# Функция группировки тегов по DB номеру для оптимизации чтения
def group_tags_by_db(tags):
    # Словарь для группировки: db_number -> список тегов
    grouped = {}
    # Перебор всех тегов
    for tag in tags:
        # Получение номера DB
        db_num = tag["db_number"]
        # Если группы ещё нет — создаём пустой список
        if db_num not in grouped:
            grouped[db_num] = []
        # Добавление тега в соответствующую группу
        grouped[db_num].append(tag)
    # Возвращаем словарь сгруппированных тегов
    return grouped


# Функция чтения данных из одного DB блока
def read_db(client, db_number, tags, con):
    # Если тегов нет — пропуск
    if not tags:
        return

    # Сортировка тегов по смещению для корректного чтения
    sorted_tags = sorted(tags, key=lambda x: x["byte_offset"] or 0)

    # Определение минимального и максимального смещения
    min_offset = sorted_tags[0]["byte_offset"] or 0
    max_tag = sorted_tags[-1]
    max_offset = (max_tag["byte_offset"] or 0) + max_tag["size"]

    # Общий размер для чтения из DB
    total_size = max_offset - min_offset

    # Чтение данных из DB блока
    try:
        data = client.db_read(db_number, min_offset, total_size)
    except Exception as e:
        print(f"Error reading DB{db_number}: {e}")
        return

    # Перебор всех тегов в группе и извлечение значений
    for tag in tags:
        try:
            # Вычисление относительного смещения в прочитанном буфере
            rel_offset = (tag["byte_offset"] or 0) - min_offset
            # Конвертация данных по типу
            value = convert_value(data, tag["data_type"], rel_offset, tag["bit_offset"] or 0)
            # Вставка значения в таблицу S7Data
            con.execute(
                "INSERT INTO S7Data (tag_id, value) VALUES (?, ?)",
                [tag["id"], float(value) if value is not None else None]
            )
        except Exception as e:
            print(f"Error reading tag {tag['tag_name']}: {e}")

    # Сообщение об успешном чтении DB
    print(f"  DB{db_number}: {len(tags)} tags read")


# Функция опроса одного S7 устройства
def read_device(device_config, tags, con):
    # Получение параметров подключения
    host = device_config["host"]
    rack = device_config.get("rack", 0)
    slot = device_config.get("slot", 1)
    use_tls = device_config.get("use_tls", False)

    # Создание S7CommPlus клиента
    client = Client()

    # Попытка подключения к устройству
    try:
        # Подключение с учётом TLS
        if use_tls:
            client.connect(
                host,
                use_tls=True,
                tls_cert=device_config.get("tls_cert"),
                tls_key=device_config.get("tls_key"),
                tls_ca=device_config.get("tls_ca"),
                password=device_config.get("password"),
            )
        else:
            client.connect(host, rack, slot)
        print(f"[{host}] Connected")
    except Exception as e:
        print(f"[{host}] Connection failed: {e}")
        return

    try:
        # Группировка тегов по DB номеру
        tags_by_db = group_tags_by_db(tags)
        # Перебор всех DB блоков
        for db_number, db_tags in tags_by_db.items():
            # Чтение данных из DB
            read_db(client, db_number, db_tags, con)
    except Exception as e:
        print(f"[{host}] Exception: {e}")
    finally:
        # Гарантированное отключение от устройства
        try:
            client.disconnect()
        except Exception:
            pass


# Функция опроса всех S7 устройств
def read_devices(config):
    # Открытие соединения с базой данных DuckDB
    con = duckdb.connect(str(DB_PATH))
    # Инициализация таблицы S7Data
    init_db(con)

    # Получение списка S7 устройств из конфигурации
    s7_devices = config.get("s7_devices", [])

    # Если S7 устройств нет — вывод сообщения и выход
    if not s7_devices:
        print("No S7 devices found in config.yaml")
        con.close()
        return

    # Перебор всех S7 устройств
    for dev in s7_devices:
        # Загрузка карты тегов для данного устройства
        tags = load_s7_tag_map(con, dev.get("name"))
        # Если тегов нет — пропуск устройства
        if not tags:
            print(f"[{dev['host']}] No tags found, skipping")
            continue
        # Опрос устройства
        read_device(dev, tags, con)

    # Закрытие соединения с базой данных
    con.close()


# Точка входа — выполнение только при прямом запуске скрипта
if __name__ == "__main__":
    # Загрузка конфигурации из YAML-файла
    config = load_config(CONFIG_PATH)
    # Получение интервала опроса из конфигурации
    poll_interval = config.get("poll_interval", 5)
    # Сообщение о начале работы
    print(f"S7 polling every {poll_interval}s. Ctrl+C to stop.")
    # Бесконечный цикл опроса
    while True:
        # Вызов функции чтения данных со всех устройств
        read_devices(config)
        # Задержка перед следующим опросом
        time.sleep(poll_interval)
