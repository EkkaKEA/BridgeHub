# BridgeHub

Мост между промышленными протоколами (Modbus TCP, OPC UA, S7) и системами верхнего уровня (SCADA, historians). Сбор данных с устройств, хранение в DuckDB, импорт/экспорт через JSON.

## Структура проекта

```
BridgeHub/
├── config.yaml                 # Конфигурация подключений
├── bridgehub.duckdb            # База данных DuckDB
│
├── import_modbus_tags.py       # Импорт определений тегов Modbus из Excel
├── import_opcua_tags.py        # Импорт определений тегов OPC UA из Excel
├── import_s7_tags.py           # Импорт определений тегов S7 из .DB файлов
├── ReadFromModbusTCP.py        # Опрос Modbus TCP устройств
├── ReadFromOPCUA.py            # Опрос OPC UA серверов
├── ReadFromS7.py               # Опрос S7-1200/1500 (S7CommPlus)
│
├── import_json_tags.py         # Импорт runtime-данных из JSON
├── export_json_tags.py         # Экспорт runtime-данных в JSON
├── Server01_Tags.json          # Пример JSON-файла с данными
│
├── КартаMB.xlsx                # Карта тегов Modbus (исходник)
├── КартаOPCUA.xlsx             # Карта тегов OPC UA (исходник)
│
├── install_duckdb.cmd          # Установка DuckDB CLI
├── open_db.cmd                 # Открытие БД в консоли
│
└── tools/
    ├── viewer.py               # Веб-просмотрщик таблиц (Streamlit)
    └── open_viewer.cmd         # Запуск просмотрщика
```

## Установка

### 1. Установка DuckDB

Запустите `install_duckdb.cmd` — скрипт скачает DuckDB CLI v1.1.3 в папку `bin/`.

### 2. Установка Python-зависимостей

```bash
pip install duckdb openpyxl pymodbus opcua pyyaml streamlit python-snap7
```

## Конфигурация

Файл `config.yaml`:

```yaml
# Интервал опроса устройств (секунды)
poll_interval: 5

# Modbus TCP устройства
devices:
  - host: "192.168.1.1"
    port: 502
    device_id: 1

# OPC UA серверы
opcua_devices:
  - url: "opc.tcp://192.168.1.10:4840"
    timeout: 10

# S7-1200/1500 устройства (S7CommPlus)
s7_devices:
  - host: "192.168.1.20"
    rack: 0
    slot: 1
    name: "PLC_01"
    use_tls: false
```

## Схема базы данных

### Таблицы определений тегов

| Таблица | Назначение | Ключевые поля |
|---------|-----------|---------------|
| `ModbusTagMap` | Определения Modbus тегов | tag_name, segment, modbus_address |
| `OPCUATagMap` | Определения OPC UA тегов | tag_name, opc_node_id |
| `S7TagMap` | Определения S7 тегов | tag_name, db_number, byte_offset, data_type |
| `TagMap` | Объединённая таблица (legacy) | все поля |

### Таблицы данных

| Таблица | Назначение | Связь |
|---------|-----------|-------|
| `ModbusData` | Runtime-данные Modbus | tag_id → ModbusTagMap.id |
| `OPCUAData` | Runtime-данные OPC UA | tag_id → OPCUATagMap.id |
| `S7Data` | Runtime-данные S7 | tag_id → S7TagMap.id |
| `JsonData` | Runtime-данные из JSON | linked_tag_id → ModbusTagMap/OPCUATagMap (опционально) |

## Использование

### Импорт определений тегов

```bash
python import_modbus_tags.py    # Импорт из КартаMB.xlsx
python import_opcua_tags.py     # Импорт из КартаOPCUA.xlsx
python import_s7_tags.py DB1.DB # Импорт из .DB файла TIA Portal
```

### Опрос устройств

```bash
python ReadFromModbusTCP.py     # Опрос Modbus TCP
python ReadFromOPCUA.py         # Опрос OPC UA
python ReadFromS7.py            # Опрос S7-1200/1500 (S7CommPlus)
```

### Импорт/экспорт runtime-данных (JSON)

```bash
python import_json_tags.py Server01_Tags.json   # Импорт данных из JSON
python export_json_tags.py output.json           # Экспорт данных в JSON
python export_json_tags.py output.json SCADA_01  # Экспорт с фильтром по device_id
```

### Просмотр данных

```bash
tools\open_viewer.cmd           # Запуск веб-просмотрщика (Streamlit)
open_db.cmd                     # Открытие БД в консоли DuckDB
```

## Формат JSON-файла

Файл содержит runtime-данные (значения тегов):

```json
{
  "device_id": "SCADA_Server_01",
  "timestamp_batch": "2026-08-26T14:35:12.000+03:00",
  "tags": [
    {
      "id": "TIC-101.PV",
      "name": "Давление в реакторе R-101",
      "value": 2.45,
      "quality": "Good",
      "units": "МПа",
      "data_type": "float",
      "timestamp": "2026-08-26T14:35:12.123+03:00"
    }
  ]
}
```

### Поля верхнего уровня

| Поле | Тип | Описание |
|------|-----|----------|
| `device_id` | string | Идентификатор источника данных |
| `timestamp_batch` | string | Время формирования пакета (ISO 8601) |
| `tags` | array | Массив тегов |

### Поля тега

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `id` | string | да | Идентификатор тега |
| `name` | string | нет | Человекочитаемое имя |
| `value` | any | нет | Значение тега |
| `quality` | string | нет | Качество (Good/Bad/Uncertain) |
| `units` | string | нет | Единицы измерения |
| `data_type` | string | нет | Тип данных (float/int/bool/string) |
| `timestamp` | string | нет | Время значения (ISO 8601) |

## S7-1200/1500 (S7CommPlus)

### Поддерживаемые типы данных

| Тип | Размер | Описание |
|-----|--------|----------|
| `BOOL` | 1 бит | Логическое значение |
| `BYTE` | 1 байт | Беззнаковый байт |
| `WORD` | 2 байта | Беззнаковое 16-битное |
| `DWORD` | 4 байта | Беззнаковое 32-битное |
| `INT` | 2 байта | Знаковое 16-битное |
| `DINT` | 4 байта | Знаковое 32-битное |
| `REAL` | 4 байта | Число с плавающей запятой |
| `STRING` | 256 байт | Строка |

### Импорт тегов из TIA Portal

1. Экспортируйте DB блок из TIA Portal в формат .DB
2. Запустите импорт:

```bash
python import_s7_tags.py DB1.DB PLC_01
```

### Формат .DB файла

```
DATA_BLOCK "DB_TagExample"
{ S7_Optimized_Access := 'FALSE' }
VERSION : 0.1
  STRUCT
    Temperature : Real;        // Температура
    Pressure : Int;            // Давление
    MotorOn : Bool;            // Статус мотора
    Setpoint : Real := 100.0;  // Уставка
  END_STRUCT
END_DATA_BLOCK
```

### Конфигурация PLC

```yaml
s7_devices:
  - host: "192.168.1.20"
    rack: 0
    slot: 1
    name: "PLC_01"
    use_tls: false  # Для S7-1500 FW 2.x+ с TLS: true
```
