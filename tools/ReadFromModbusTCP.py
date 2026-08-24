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

# Путь к файлу конфигурации (рядом со скриптом)
CONFIG_PATH = Path(__file__).parent / "config.yaml"


# Функция загрузки конфигурации из YAML-файла
def load_config(path):
    # Открытие и чтение YAML-файла
    with open(path, "r", encoding="utf-8") as f:
        # Парсинг YAML и возвращение словаря
        return yaml.safe_load(f)


# Функция опроса всех устройств и сохранения данных в БД
def read_devices(config):
    # Открытие соединения с базой данных DuckDB (путь из конфига)
    con = duckdb.connect(config["db_path"])

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
            # Чтение Holding Register'ов с устройства
            result = client.read_holding_registers(
                address=dev["registers"][0],  # Адрес начального регистра
                count=len(dev["registers"]),   # Количество регистров для чтения
                device_id=dev["device_id"],    # ID устройства Modbus
            )

            # Проверка на ошибку чтения
            if result.isError():
                # Если ошибка — вывод сообщения и переход к следующему устройству
                print(f"[{dev['host']}] Read error: {result}")
                continue

            # Перебор прочитанных значений и запись каждого в БД
            for i, reg in enumerate(dev["registers"]):
                # Вставка записи в таблицу Data_from_Modbus
                con.execute(
                    "INSERT INTO Data_from_Modbus (device_id, register, value) VALUES (?, ?, ?)",
                    [dev["device_id"], reg, float(result.registers[i])],  # Параметры запроса
                )

            # Сообщение об успешном чтении всех регистров
            print(f"[{dev['host']}] OK - {len(dev['registers'])} registers read")

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
    # Загрузка конфигурации из YAML-файла
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
