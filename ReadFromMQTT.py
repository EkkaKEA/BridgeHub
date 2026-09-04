# Импорт библиотеки для работы с базой данных DuckDB
import duckdb
# Импорт клиента MQTT из библиотеки paho-mqtt
import paho.mqtt.client as mqtt
# Импорт библиотеки для чтения YAML-конфигурации
import yaml
# Импорт модуля для работы с путями файловой системы
from pathlib import Path
# Импорт модуля для работы со временем
import time
# Импорт модуля для парсинга JSON
import json

# Путь к базе данных DuckDB (в корне проекта)
DB_PATH = Path(__file__).parent / "bridgehub.duckdb"

# Путь к файлу конфигурации (рядом со скриптом)
CONFIG_PATH = Path(__file__).parent / "config.yaml"


# Функция загрузки конфигурации из YAML-файла
def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# Функция инициализации таблицы MQTTData
def init_db(con):
    # Получение списка существующих таблиц
    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    # Если таблицы MQTTData нет — создаём её
    if "MQTTData" not in tables:
        con.execute("""
            CREATE TABLE MQTTData (
                id INTEGER PRIMARY KEY,
                tag_id INTEGER,
                value DOUBLE,
                raw_value VARCHAR,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Created table MQTTData")


# Функция загрузки MQTT тегов из БД
def load_mqtt_tags(con):
    result = con.execute(
        "SELECT id, tag_name, topic, json_path, data_type, payload_format FROM MQTTTagMap"
    ).fetchall()
    return [
        {
            "id": row[0],
            "tag_name": row[1],
            "topic": row[2],
            "json_path": row[3],
            "data_type": row[4],
            "payload_format": row[5],
        }
        for row in result
    ]


# Функция извлечения значения из JSON по пути (например, "data.temperature" или "$.temperature")
def extract_json_value(payload, json_path):
    if not json_path:
        return payload
    # Удаление ведущего "$." или "$"
    path = json_path
    if path.startswith("$."):
        path = path[2:]
    elif path.startswith("$"):
        path = path[1:]
    # Разбивка пути на части
    keys = path.split(".")
    current = payload
    for key in keys:
        if not key:
            continue
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


# Функция извлечения значения из CSV строки
def extract_csv_value(payload, json_path):
    if not json_path:
        return payload
    # json_path содержит индекс столбца (0-based)
    try:
        index = int(json_path)
        parts = str(payload).split(",")
        if 0 <= index < len(parts):
            return parts[index].strip()
    except (ValueError, IndexError):
        pass
    return None


# Функция преобразования значения в число
def convert_to_number(value, data_type):
    if value is None:
        return None
    try:
        if data_type in ("Boolean", "bool"):
            return 1.0 if bool(value) else 0.0
        elif data_type in ("Int16", "Int32", "Int64", "UInt16", "UInt32", "UInt64", "int", "integer"):
            return float(int(value))
        elif data_type in ("Float", "Double", "float", "double", "real"):
            return float(value)
        elif data_type in ("String", "string", "str"):
            # Попытка преобразовать строку в число
            return float(value)
    except (ValueError, TypeError):
        return None
    return None


# Класс обработчика MQTT сообщений
class MQTTHandler:
    def __init__(self, con, tags_by_topic):
        self.con = con
        self.tags_by_topic = tags_by_topic
        # Получение максимального id для автоинкремента
        max_id = self.con.execute("SELECT COALESCE(MAX(id), 0) FROM MQTTData").fetchone()[0]
        self.counter = max_id + 1

    # Callback при получении сообщения
    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload_raw = msg.payload.decode("utf-8")

        # Парсинг payload
        payload = None
        payload_format = None
        for tag in self.tags_by_topic.get(topic, []):
            payload_format = tag.get("payload_format", "json")
            break

        if payload_format and payload_format.lower() == "json":
            try:
                payload = json.loads(payload_raw)
            except json.JSONDecodeError:
                payload = None
        else:
            payload = payload_raw

        # Обработка тегов для данного топика
        for tag in self.tags_by_topic.get(topic, []):
            value = None
            raw_value = payload_raw

            # Извлечение значения в зависимости от формата
            if payload_format and payload_format.lower() == "json" and isinstance(payload, dict):
                value = extract_json_value(payload, tag.get("json_path"))
            elif payload_format and payload_format.lower() == "csv":
                value = extract_csv_value(payload, tag.get("json_path"))
            else:
                value = payload

            # Преобразование значения в число
            numeric_value = convert_to_number(value, tag.get("data_type"))

            # Вставка записи в таблицу MQTTData
            self.con.execute(
                "INSERT INTO MQTTData (id, tag_id, value, raw_value) VALUES (?, ?, ?, ?)",
                [self.counter, tag["id"], numeric_value, raw_value],
            )
            self.counter += 1

    # Callback при подключении к брокеру
    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            print(f"Connected to MQTT broker")
            # Подписка на все уникальные топики
            topics = list(self.tags_by_topic.keys())
            for topic in topics:
                client.subscribe(topic)
                print(f"  Subscribed to: {topic}")
        else:
            print(f"Connection failed with code {reason_code}")


# Функция запуска MQTT клиента
def start_mqtt(config):
    con = duckdb.connect(str(DB_PATH))

    # Инициализация таблицы MQTTData
    init_db(con)

    # Загрузка MQTT тегов из БД
    tags = load_mqtt_tags(con)

    if not tags:
        print("No MQTT tags found in MQTTTagMap")
        con.close()
        return

    # Группировка тегов по топику
    tags_by_topic = {}
    for tag in tags:
        topic = tag["topic"]
        if topic not in tags_by_topic:
            tags_by_topic[topic] = []
        tags_by_topic[topic].append(tag)

    print(f"Loaded {len(tags)} MQTT tags for {len(tags_by_topic)} topics")

    # Перебор всех MQTT брокеров из конфигурации
    for broker in config.get("mqtt_brokers", []):
        # Создание обработчика сообщений
        handler = MQTTHandler(con, tags_by_topic)

        # Создание MQTT клиента
        client_id = broker.get("client_id", "bridgehub_mqtt")
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)

        # Установка логина/пароля (если указаны)
        username = broker.get("username")
        password = broker.get("password")
        if username:
            client.username_pw_set(username, password)

        # Привязка callback-функций
        client.on_connect = handler.on_connect
        client.on_message = handler.on_message

        try:
            # Подключение к MQTT брокеру
            host = broker["host"]
            port = broker.get("port", 1883)
            keepalive = broker.get("keepalive", 60)
            client.connect(host, port, keepalive)

            print(f"[{host}:{port}] MQTT client started")

            # Запуск обработки сообщений в фоновом потоке
            client.loop_start()

        except Exception as e:
            print(f"[{broker.get('host', '?')}] Connection failed: {e}")
            con.close()
            return

    # Бесконечный цикл (работает пока не будет прерван Ctrl+C)
    print("MQTT listener running. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping MQTT client...")
        client.loop_stop()
        client.disconnect()

    # Закрытие соединения с базой данных
    con.close()


# Точка входа — выполнение только при прямом запуске скрипта
if __name__ == "__main__":
    # Загрузка конфигурации из YAML-файла
    config = load_config(CONFIG_PATH)
    # Запуск MQTT клиента
    start_mqtt(config)
