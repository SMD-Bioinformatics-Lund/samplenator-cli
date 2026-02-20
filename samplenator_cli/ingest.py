import csv

import yaml


def parse_file(path: str) -> list[dict]:
    lower = path.lower()
    if lower.endswith(".csv"):
        return _read_delimited(path, delimiter=",")
    elif lower.endswith(".tsv"):
        return _read_delimited(path, delimiter="\t")
    elif lower.endswith(".yaml") or lower.endswith(".yml"):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, list):
            return [dict(row) for row in data]
        raise ValueError(f"YAML file must contain a list of records, got {type(data).__name__}")
    else:
        raise ValueError(f"Unsupported file extension: {path!r}. Use .csv, .tsv, .yaml, or .yml")


def _read_delimited(path: str, delimiter: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        return [dict(row) for row in reader]


def resolve_aliases(rows: list[dict], aliases: dict) -> list[dict]:
    # Build reverse map: alias_lower → canonical
    reverse = {}
    for canonical, alias_list in aliases.items():
        for alias in alias_list:
            reverse[alias.lower()] = canonical

    resolved = []
    for row in rows:
        new_row = {}
        for key, value in row.items():
            canonical = reverse.get(key.lower(), key)
            new_row[canonical] = value
        resolved.append(new_row)
    return resolved


def validate_record(record: dict, required_fields: set, valid_statuses: set) -> list[str]:
    errors = []
    for field in required_fields:
        if field not in record or record[field] is None or str(record[field]).strip() == "":
            errors.append(f"missing required field: {field!r}")

    if "status" in record and record["status"] is not None:
        status_val = str(record["status"]).strip().lower()
        if status_val not in valid_statuses:
            errors.append(f"invalid status {record['status']!r}: must be 'ok' or 'fail'")

    return errors


def build_payload(records: list[dict], known_fields: set) -> list[dict]:
    clean = []
    for record in records:
        row = {}
        for field in known_fields:
            if field in record and record[field] is not None and str(record[field]).strip() != "":
                row[field] = str(record[field]).strip()
        if "status" in row:
            row["status"] = row["status"].lower()
        clean.append(row)
    return clean
