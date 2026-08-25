# Импорт модуля для работы со временем (задержки между опросами)
import time
# Импорт библиотеки для работы с базой данных DuckDB
import duckdb
# Импорт клиента Modbus TCP из библиотеки pymodbus
from pymodbus.client import ModbusTcpClient
# Импорт библиотеки для чтения YAML-конфигурации
import yaml
# Импорт модуля для работы с путями файловой системы
from pathlib import Path
# Импорт модуля для группировки данных
from collections import defaultdict

# Путь к базе данных DuckDB (в корне проекта)
DB_PATH = Path(__file__).parent / "bridgehub.duckdb"

# Путь к файлу конфигурации Modbus (рядом со скриптом)
CONFIG_PATH = Path(__file__).parent / "config.yaml"


# Функция загрузки конфигурации из YAML-файла
def load_config(path):
    # Открытие и чтение YAML-файла
    with open(path, "r", encoding="utf-8") as f:
        # Парсинг YAML и возвращение словаря
        return yaml.safe_load(f)


# Функция загрузки карты тегов из БД
def load_tag_map(con):
    # Чтение всех тегов из таблицы ModbusTagMap
    result = con.execute("SELECT id, tag_name, segment, modbus_address FROM ModbusTagMap").fetchall()
    # Возвращаем список словарей с данными тегов
    return [{"id": row[0], "tag_name": row[1], "segment": row[2], "modbus_address": row[3]} for row in result]


# Функция группировки тегов по сегменту (Input/Holding Registers)
def group_tags_by_segment(tags):
    # Словарь для группировки: сегмент -> список адресов
    grouped = defaultdict(list)
    # Перебор всех тегов
    for tag in tags:
        # Добавление тега в соответствующую группу
        grouped[tag["segment"]].append(tag)
    # Возвращаем словарь сгруппированных тегов
    return grouped


# Функция опроса одного устройства
def read_device(client, device_config, tags_by_segment, con):
    # Перебор всех сегментов (Input Registers, Holding Registers)
    for segment, tags in tags_by_segment.items():
        # Определение типа чтения в зависимости от сегмента
        if segment == "Input Registers":
            # Чтение Input Registers (только чтение)
            read_func = client.read_input_registers
        elif segment == "Holding Registers":
            # Чтение Holding Registers (чтение/запись)
            read_func = client.read_holding_registers
        else:
            # Неизвестный сегмент — пропуск
            print(f"Unknown segment: {segment}")
            continue

        # Сортировка тегов по адресу регистров
        sorted_tags = sorted(tags, key=lambda x: x["modbus_address"])

        # Получение начального адреса и количества регистров
        start_address = sorted_tags[0]["modbus_address"]
        end_address = sorted_tags[-1]["modbus_address"]
        count = end_address - start_address + 1

        # Чтение регистров с устройства
        result = read_func(
            address=start_address,  # Адрес начального регистра
            count=count,            # Количество регистров для чтения
            device_id=device_config["device_id"],  # ID устройства Modbus
        )

        # Проверка на ошибку чтения
        if result.isError():
            # Если ошибка — вывод сообщения
            print(f"[{device_config['host']}] {segment} read error: {result}")
            continue

        # Перебор прочитанных тегов и запись каждого в БД
        for tag in sorted_tags:
            # Вычисление индекса значения в массиве результатов
            index = tag["modbus_address"] - start_address
            # Проверка, что индекс в допустимых пределах
            if 0 <= index < len(result.registers):
                # Вставка записи в таблицу ModbusData с привязкой к tag_id
                con.execute(
                    "INSERT INTO ModbusData (tag_id, value) VALUES (?, ?)",
                    [tag["id"], float(result.registers[index])],  # Параметры запроса
                )

        # Сообщение об успешном чтении сегмента
        print(f"[{device_config['host']}] OK - {segment}: {len(tags)} tags read")


# Функция опроса всех устройств и сохранения данных в БД
def read_devices(config):
    # Открытие соединения с базой данных DuckDB
    con = duckdb.connect(str(DB_PATH))

    # Загрузка карты тегов из БД
    tag_map = load_tag_map(con)

    # Группировка тегов по сегменту
    tags_by_segment = group_tags_by_segment(tag_map)

    # Перебор всех устройств из конфигурации
    for dev in config["devices"]:
        # Создание Modbus TCP клиента с указанным адресом и портом
        client = ModbusTcpClient(dev["host"], port=dev["port"])

        # Попытка подключения к устройству
        if not client.connect():
            # Если подключение не удалось — вывод сообщения и переход к следующему устройству
            print(f"[{dev['host']}] Connection failed")
            continue

        try:
            # Опрос устройства и запись данных в БД
            read_device(client, dev, tags_by_segment, con)

        # Обработка любых исключений (ошибки сети, таймауты и т.д.)
        except Exception as e:
            # Вывод текста ошибки
            print(f"[{dev['host']}] Exception: {e}")

        # Гарантированное закрытие соединения с устройством
        finally:
            client.close()

    # Закрытие соединения с базой данных
    con.close()


# Точка входа — выполнение только при прямом запуске скрипта
if __name__ == "__main__":
    # Загрузка конфигурации Modbus из YAML-файла
    config = load_config(CONFIG_PATH)
    # Получение интервала опроса из конфигурации
    poll_interval = config["poll_interval"]
    # Сообщение о начале работы
    print(f"Polling every {poll_interval}s. Ctrl+C to stop.")
    # Бесконечный цикл опроса
    while True:
        # Вызов функции чтения данных со всех устройств
        read_devices(config)
        # Задержка перед следующим опросом
        time.sleep(poll_interval)
