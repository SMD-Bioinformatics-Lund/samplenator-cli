import click
import importlib.util
import json
import sys

import samplenator_cli.config as default_config
from samplenator_cli.ingest import parse_file, resolve_aliases, validate_record, build_mongo_update


def load_config(config_path):
    if config_path is None:
        return default_config
    spec = importlib.util.spec_from_file_location("_user_config", config_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@click.group()
def main():
    """CLI for theSamplenator — ingest sample status records into MongoDB."""


@main.command()
@click.option("-i", "--input", "input_file", required=True, type=click.Path(exists=True),
              help="Input file (.csv, .tsv, .yaml, .yml)")
@click.option("--mongo-uri", envvar="SAMPLENATOR_MONGO_URI", default=None,
              help="MongoDB URI (env: SAMPLENATOR_MONGO_URI)")
@click.option("--mongo-db", envvar="SAMPLENATOR_MONGO_DB", default=None,
              help="MongoDB database name (env: SAMPLENATOR_MONGO_DB)")
@click.option("--mongo-collection", envvar="SAMPLENATOR_MONGO_COLLECTION", default=None,
              help="MongoDB collection name (env: SAMPLENATOR_MONGO_COLLECTION)")
@click.option("--dry-run", is_flag=True, help="Print JSON, skip insert")
@click.option("--config", "config_path", default=None, type=click.Path(),
              help="Path to an alternate config.py")
def upload(input_file, mongo_uri, mongo_db, mongo_collection, dry_run, config_path):
    """Upload records from a file into MongoDB."""
    cfg = load_config(config_path)

    mongo_uri = mongo_uri or cfg.MONGO_URI
    mongo_db = mongo_db or cfg.MONGO_DB
    mongo_collection = mongo_collection or cfg.MONGO_COLLECTION

    try:
        raw_rows = parse_file(input_file)
    except (ValueError, FileNotFoundError) as e:
        click.echo(f"Error reading file: {e}", err=True)
        sys.exit(1)

    rows = resolve_aliases(raw_rows, cfg.FIELD_ALIASES)

    all_errors = []
    for i, record in enumerate(rows, start=1):
        for err in validate_record(record, cfg.REQUIRED_FIELDS, cfg.VALID_STATUSES, cfg.KNOWN_SYSTEMS):
            all_errors.append(f"Row {i}: {err}")

    if all_errors:
        for msg in all_errors:
            click.echo(msg, err=True)
        sys.exit(1)

    # Normalise records: strip whitespace, lowercase status/system, drop unknown fields
    payload_records = []
    for record in rows:
        row = {}
        for field in cfg.KNOWN_FIELDS:
            if field in record and record[field] is not None and str(record[field]).strip() != "":
                row[field] = str(record[field]).strip()
        if "status" in row:
            row["status"] = row["status"].lower()
        if "system" in row:
            row["system"] = row["system"].lower()
        payload_records.append(row)

    if dry_run:
        updates = [build_mongo_update(r, cfg) for r in payload_records]
        click.echo(json.dumps({"updates": updates}, indent=2))
        sys.exit(0)

    from pymongo import MongoClient
    client = MongoClient(mongo_uri)
    collection = client[mongo_db][mongo_collection]

    upserted = inserted = 0
    for record in payload_records:
        update = build_mongo_update(record, cfg)
        result = collection.update_one(
            {"sample_id": record["sample_id"]},
            update,
            upsert=True,
        )
        if result.upserted_id:
            upserted += 1
        else:
            inserted += 1  # actually "updated"

    click.echo(f"Done — {upserted} created, {inserted} updated in {mongo_db}.{mongo_collection}")


if __name__ == "__main__":
    main()
