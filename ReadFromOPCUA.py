# Импорт модуля для работы со временем (задержки между опросами)
import time
# Импорт библиотеки для работы с базой данных DuckDB
import duckdb
# Импорт OPC UA клиента из библиотеки opcua
from opcua import Client
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
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# Функция загрузки OPC UA тегов из БД
def load_opcua_tags(con):
    result = con.execute(
        "SELECT id, tag_name, opc_node_id, data_type FROM OPCUATagMap"
    ).fetchall()
    return [{"id": row[0], "tag_name": row[1], "opc_node_id": row[2], "data_type": row[3]} for row in result]


# Функция преобразования значения OPC UA в Python-тип
def convert_value(value, data_type):
    if value is None:
        return None
    type_map = {
        "Boolean": bool,
        "Int16": int,
        "Int32": int,
        "Int64": int,
        "UInt16": int,
        "UInt32": int,
        "UInt64": int,
        "Float": float,
        "Double": float,
        "String": str,
    }
    converter = type_map.get(data_type)
    if converter:
        return converter(value)
    return value


# Функция инициализации таблицы OPCUAData
def init_db(con):
    # Проверка существования таблицы OPCUAData
    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    if "OPCUAData" not in tables:
        con.execute("""
            CREATE TABLE OPCUAData (
                id INTEGER PRIMARY KEY,
                tag_id INTEGER,
                value DOUBLE,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Created table OPCUAData")


# Функция чтения данных с OPC UA устройства
def read_device(client, device_config, tags, con):
    success_count = 0
    error_count = 0

    for tag in tags:
        try:
            node = client.get_node(tag["opc_node_id"])
            raw_value = node.get_value()
            value = convert_value(raw_value, tag["data_type"])

            con.execute(
                "INSERT INTO OPCUAData (tag_id, value) VALUES (?, ?)",
                [tag["id"], value],
            )
            success_count += 1

        except Exception as e:
            print(f"[{device_config['url']}] Tag {tag['tag_name']} read error: {e}")
            error_count += 1

    print(f"[{device_config['url']}] OK - {success_count} tags read, {error_count} errors")


# Функция опроса всех OPC UA устройств
def read_devices(config):
    con = duckdb.connect(str(DB_PATH))

    # Инициализация таблицы OPCUAData
    init_db(con)

    # Загрузка OPC UA тегов из БД
    tags = load_opcua_tags(con)

    if not tags:
        print("No OPCUA tags found in OPCUATagMap")
        con.close()
        return

    # Перебор всех OPC UA устройств из конфигурации
    for dev in config.get("opcua_devices", []):
        client = Client(url=dev["url"], timeout=dev.get("timeout", 10))

        try:
            # Подключение к OPC UA серверу
            client.connect()
            print(f"[{dev['url']}] Connected")

            # Чтение данных с устройства
            read_device(client, dev, tags, con)

        except Exception as e:
            print(f"[{dev['url']}] Connection failed: {e}")

        finally:
            try:
                client.disconnect()
            except Exception:
                pass

    con.close()


# Точка входа — выполнение только при прямом запуске скрипта
if __name__ == "__main__":
    config = load_config(CONFIG_PATH)
    poll_interval = config.get("poll_interval", 5)
    print(f"OPC UA polling every {poll_interval}s. Ctrl+C to stop.")
    while True:
        read_devices(config)
        time.sleep(poll_interval)
