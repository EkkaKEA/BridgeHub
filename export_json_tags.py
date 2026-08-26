import duckdb
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "bridgehub.duckdb"


def export_json_tags(output_path, device_id_filter=None):
    con = duckdb.connect(str(DB_PATH), read_only=True)

    query = "SELECT device_id, tag_id, tag_name, value, quality, units, data_type, value_timestamp, batch_timestamp FROM JsonData"
    params = []
    if device_id_filter:
        query += " WHERE device_id = ?"
        params.append(device_id_filter)
    query += " ORDER BY batch_timestamp, tag_id"

    rows = con.execute(query, params).fetchall()
    con.close()

    grouped = {}
    for row in rows:
        dev_id, tag_id, tag_name, value, quality, units, data_type, value_ts, batch_ts = row
        key = (dev_id, batch_ts)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append({
            "id": tag_id,
            "name": tag_name,
            "value": value,
            "quality": quality,
            "units": units,
            "data_type": data_type,
            "timestamp": str(value_ts) if value_ts else None,
        })

    result = []
    for (dev_id, batch_ts), tags in grouped.items():
        result.append({
            "device_id": dev_id,
            "timestamp_batch": str(batch_ts) if batch_ts else None,
            "tags": tags,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result if len(result) != 1 else result[0], f, ensure_ascii=False, indent=2)

    total_tags = sum(len(g) for g in grouped.values())
    print(f"Exported {total_tags} tags ({len(grouped)} batches) to {output_path}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python export_json_tags.py <output.json> [device_id]")
        sys.exit(1)
    device_filter = sys.argv[2] if len(sys.argv) > 2 else None
    export_json_tags(sys.argv[1], device_filter)
