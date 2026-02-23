import csv
from datetime import datetime

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


def validate_record(record: dict, required_fields: set, valid_statuses: set, known_systems=None) -> list[str]:
    errors = []
    for field in required_fields:
        if field not in record or record[field] is None or str(record[field]).strip() == "":
            errors.append(f"missing required field: {field!r}")

    if "status" in record and record["status"] is not None:
        status_val = str(record["status"]).strip().lower()
        if status_val not in valid_statuses:
            errors.append(
                f"invalid status {record['status']!r}: must be one of {sorted(valid_statuses)}"
            )

    if known_systems is not None and "system" in record and record["system"] is not None:
        system_val = str(record["system"]).strip().lower()
        if system_val not in known_systems:
            errors.append(
                f"unknown system {record['system']!r}: must be one of {known_systems}"
            )

    return errors


def build_mongo_update(record: dict, cfg) -> dict:
    now = datetime.utcnow().isoformat() + "Z"
    system = record["system"].lower()
    status_raw = record["status"].lower()
    status_compound = cfg.STATUS_MAP.get(status_raw, status_raw)

    # IDs dict for the system section
    ids = {}
    if record.get("clarity_lims_id"):
        ids["clarity_lims_id"] = record["clarity_lims_id"]
    if record.get("sequencing_run_id"):
        ids["sequencing_run_id"] = record["sequencing_run_id"]

    # Determine queue_status for summary
    if status_raw in ("ok", "completed"):
        queue_status = "completed"
    elif status_raw in ("fail", "failed"):
        queue_status = "failed"
    else:
        queue_status = "in_progress"

    # Base $set fields
    set_fields = {
        "sample_id": record["sample_id"],
        "summary.current_step": record["message"],
        "summary.queue_status": queue_status,
        "summary.current_step_started_at": now,
        "timestamps.updated_at": now,
        "timestamps.last_event_at": now,
    }
    # Optional top-level sample fields
    for field in ("group_id", "assay", "lab_id", "sample_type"):
        if record.get(field):
            set_fields[field] = record[field]

    # Resolve URL from config masks
    url_masks = getattr(cfg, "SYSTEM_URL_MASKS", {})
    mask = url_masks.get(system)
    if isinstance(mask, dict):
        mask = mask.get(record.get("checkpoint", "default"))
    resolved_url = mask.format(sample_id=record["sample_id"]) if mask else None

    # System-specific fields
    if system in cfg.CHECKPOINT_SYSTEMS:
        checkpoint = record.get("checkpoint", "default")
        prefix = f"systems.{system}.checkpoints.{checkpoint}"
        set_fields.update({
            f"{prefix}.status": status_compound,
            f"{prefix}.message": record["message"],
            f"systems.{system}.last_seen_at": now,
        })
        if resolved_url:
            set_fields[f"{prefix}.url"] = resolved_url
        if ids:
            set_fields[f"{prefix}.ids"] = ids
        if status_raw in ("started", "running"):
            set_fields[f"{prefix}.started_at"] = now
            set_fields[f"{prefix}.ended_at"] = None
        elif status_raw in ("ok", "completed", "fail", "failed"):
            set_fields[f"{prefix}.ended_at"] = now
    else:
        prefix = f"systems.{system}"
        set_fields.update({
            f"{prefix}.status": status_compound,
            f"{prefix}.last_seen_at": now,
            f"{prefix}.message": record["message"],
        })
        if resolved_url:
            set_fields[f"{prefix}.url"] = resolved_url
        if ids:
            set_fields[f"{prefix}.ids"] = ids
        if status_raw in ("started", "running"):
            set_fields[f"{prefix}.started_at"] = now
            set_fields[f"{prefix}.ended_at"] = None
        elif status_raw in ("ok", "completed", "fail", "failed"):
            set_fields[f"{prefix}.ended_at"] = now

    # Timeline entry
    timeline_entry = {
        "name": record["message"],
        "system": system,
        "checkpoint": record.get("checkpoint"),
        "status": status_compound,
        "started_at": now,
        "ended_at": None,
        "message": record["message"],
    }

    return {
        "$setOnInsert": {"timestamps.created_at": now},
        "$set": set_fields,
        "$push": {"timeline": timeline_entry},
    }
