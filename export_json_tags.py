# Импорт библиотеки для работы с базой данных DuckDB
import duckdb
# Импорт библиотеки для работы с JSON-файлами
import json
# Импорт модуля для работы с путями файловой системы
from pathlib import Path
# Импорт модуля для работы со временем
from datetime import datetime

# Путь к базе данных DuckDB (в корне проекта)
DB_PATH = Path(__file__).parent / "bridgehub.duckdb"


# Функция экспорта тегов из таблицы JsonData в JSON-файл
def export_json_tags(output_path, device_id_filter=None):
    # Открытие соединения с базой данных DuckDB (только чтение)
    con = duckdb.connect(str(DB_PATH), read_only=True)

    # Формирование запроса для выборки данных
    query = "SELECT device_id, tag_id, tag_name, value, quality, units, data_type, value_timestamp, batch_timestamp FROM JsonData"
    # Список параметров для запроса
    params = []
    # Если указан фильтр по device_id — добавляем условие WHERE
    if device_id_filter:
        query += " WHERE device_id = ?"
        params.append(device_id_filter)
    # Сортировка по времени пакета и id тега
    query += " ORDER BY batch_timestamp, tag_id"

    # Выполнение запроса и получение всех строк
    rows = con.execute(query, params).fetchall()
    # Закрытие соединения с базой данных
    con.close()

    # Группировка тегов по (device_id, batch_timestamp)
    grouped = {}
    # Перебор всех полученных строк
    for row in rows:
        # Распаковка кортежа строки
        dev_id, tag_id, tag_name, value, quality, units, data_type, value_ts, batch_ts = row
        # Ключ группы — кортеж (device_id, batch_timestamp)
        key = (dev_id, batch_ts)
        # Если группы ещё нет — создаём пустой список
        if key not in grouped:
            grouped[key] = []
        # Добавление тега в группу
        grouped[key].append({
            "id": tag_id,
            "name": tag_name,
            "value": value,
            "quality": quality,
            "units": units,
            "data_type": data_type,
            "timestamp": str(value_ts) if value_ts else None,
        })

    # Формирование итогового массива пакетов
    result = []
    # Перебор всех групп
    for (dev_id, batch_ts), tags in grouped.items():
        # Добавление пакета с метаданными и массивом тегов
        result.append({
            "device_id": dev_id,
            "timestamp_batch": str(batch_ts) if batch_ts else None,
            "tags": tags,
        })

    # Запись результата в JSON-файл
    with open(output_path, "w", encoding="utf-8") as f:
        # Если пакет один — записываем объект, иначе — массив
        json.dump(result if len(result) != 1 else result[0], f, ensure_ascii=False, indent=2)

    # Подсчет общего количества экспортированных тегов
    total_tags = sum(len(g) for g in grouped.values())
    # Вывод результата
    print(f"Exported {total_tags} tags ({len(grouped)} batches) to {output_path}")


# Точка входа — выполнение только при прямом запуске скрипта
if __name__ == "__main__":
    # Импорт модуля для работы с аргументами командной строки
    import sys
    # Проверка наличия аргумента с путём к выходному JSON-файлу
    if len(sys.argv) < 2:
        print("Usage: python export_json_tags.py <output.json> [device_id]")
        sys.exit(1)
    # Получение опционального фильтра по device_id
    device_filter = sys.argv[2] if len(sys.argv) > 2 else None
    # Запуск экспорта тегов в указанный JSON-файл
    export_json_tags(sys.argv[1], device_filter)
