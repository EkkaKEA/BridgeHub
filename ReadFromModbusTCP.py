# Импорт модуля для работы со временем (задержки между опросами)
import time
# Импорт библиотеки для работы с базой данных DuckDB
import duckdb
# Импорт клиента Modbus TCP из библиотеки pymodbus
from pymodbus.client import ModbusTcpClient

# Путь к файлу базы данных DuckDB
DB_PATH = "bridgehub.duckdb"

# Список опрашиваемых Modbus-устройств
devices = [
    # host — IP-адрес устройства, port — TCP-порт (502 по умолчанию),
    # device_id — ID устройства в сети Modbus, registers — список адресов регистров
    {"host": "192.168.1.1", "port": 502, "device_id": 1, "registers": [0, 1, 2, 3]},
]

# Интервал опроса устройств в секундах
poll_interval = 5


# Функция опроса всех устройств и сохранения данных в БД
def read_devices():
    # Открытие соединения с базой данных DuckDB
    con = duckdb.connect(DB_PATH)

    # Перебор всех устройств из списка
    for dev in devices:
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
    # Сообщение о начале работы
    print(f"Polling every {poll_interval}s. Ctrl+C to stop.")
    # Бесконечный цикл опроса
    while True:
        # Вызов функции чтения данных со всех устройств
        read_devices()
        # Задержка перед следующим опросом
        time.sleep(poll_interval)
