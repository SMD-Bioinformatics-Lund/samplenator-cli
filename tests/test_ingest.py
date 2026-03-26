"""Tests for samplenator_cli ingest functions and CLI dry-run output."""

import json
import os
from unittest.mock import patch

import pytest
from click.testing import CliRunner

import samplenator_cli.config as cfg
from samplenator_cli.cli import main
from samplenator_cli.ingest import (
    build_mongo_update,
    parse_file,
    resolve_aliases,
    validate_record,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "system")
FIXED_ISO = "2026-01-01T00:00:00.000000"
FIXED_NOW = FIXED_ISO + "Z"


def _build(record, config=cfg):
    """Call build_mongo_update with a frozen timestamp."""
    with patch("samplenator_cli.ingest.datetime") as mock_dt:
        mock_dt.utcnow.return_value.isoformat.return_value = FIXED_ISO
        return build_mongo_update(record, config)


# ---------------------------------------------------------------------------
# parse_file — CSV fixtures
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,expected_rows", [
    ("clarity.csv", 3),
    ("demux.csv", 2),
    ("bjorn.csv", 1),
    ("pipeline.csv", 3),
    ("cdm.csv", 2),
    ("frontend.csv", 7),
])
def test_parse_file_csv_row_counts(filename, expected_rows):
    rows = parse_file(os.path.join(FIXTURES, filename))
    assert len(rows) == expected_rows


def test_parse_file_csv_field_values():
    rows = parse_file(os.path.join(FIXTURES, "bjorn.csv"))
    assert rows[0]["sample_id"] == "TEST-SAMPLE-001"
    assert rows[0]["system"] == "bjorn"
    assert rows[0]["status"] == "ok"
    assert rows[0]["clarity_lims_id"] == "CLAR-TEST-001"


def test_parse_file_unsupported_extension(tmp_path):
    bad = tmp_path / "data.json"
    bad.write_text("{}")
    with pytest.raises(ValueError, match="Unsupported file extension"):
        parse_file(str(bad))


# ---------------------------------------------------------------------------
# resolve_aliases
# ---------------------------------------------------------------------------

def test_resolve_aliases_maps_aliases():
    rows = [{"sampleid": "S1", "tool": "bjorn", "msg": "ok", "state": "ok"}]
    result = resolve_aliases(rows, cfg.FIELD_ALIASES)
    assert result[0]["sample_id"] == "S1"
    assert result[0]["system"] == "bjorn"
    assert result[0]["message"] == "ok"
    assert result[0]["status"] == "ok"


def test_resolve_aliases_passthrough_canonical():
    rows = [{"sample_id": "S1", "system": "bjorn", "message": "ok", "status": "ok"}]
    result = resolve_aliases(rows, cfg.FIELD_ALIASES)
    assert result[0] == rows[0]


# ---------------------------------------------------------------------------
# validate_record
# ---------------------------------------------------------------------------

def test_validate_record_valid():
    record = {"sample_id": "S1", "system": "bjorn", "message": "ok", "status": "ok"}
    assert validate_record(record, cfg.REQUIRED_FIELDS, cfg.VALID_STATUSES, cfg.KNOWN_SYSTEMS) == []


def test_validate_record_missing_required_field():
    record = {"sample_id": "S1", "system": "bjorn", "status": "ok"}
    errors = validate_record(record, cfg.REQUIRED_FIELDS, cfg.VALID_STATUSES)
    assert any("message" in e for e in errors)


def test_validate_record_invalid_status():
    record = {"sample_id": "S1", "system": "bjorn", "message": "ok", "status": "invalid"}
    errors = validate_record(record, cfg.REQUIRED_FIELDS, cfg.VALID_STATUSES)
    assert any("invalid status" in e for e in errors)


def test_validate_record_unknown_system():
    record = {"sample_id": "S1", "system": "nope", "message": "ok", "status": "ok"}
    errors = validate_record(record, cfg.REQUIRED_FIELDS, cfg.VALID_STATUSES, cfg.KNOWN_SYSTEMS)
    assert any("unknown system" in e for e in errors)


def test_validate_record_all_valid_statuses():
    for status in cfg.VALID_STATUSES:
        record = {"sample_id": "S1", "system": "bjorn", "message": "ok", "status": status}
        assert validate_record(record, cfg.REQUIRED_FIELDS, cfg.VALID_STATUSES) == []


# ---------------------------------------------------------------------------
# build_mongo_update — top-level structure
# ---------------------------------------------------------------------------

def test_build_update_top_level_keys():
    record = {"sample_id": "S1", "system": "cdm", "message": "Uploaded to CDM", "status": "ok"}
    update = _build(record)
    assert set(update.keys()) == {"$setOnInsert", "$set", "$push"}


def test_build_update_set_on_insert():
    record = {"sample_id": "S1", "system": "cdm", "message": "Uploaded to CDM", "status": "ok"}
    update = _build(record)
    assert update["$setOnInsert"] == {"timestamps.created_at": FIXED_NOW}


def test_build_update_timeline_entry():
    record = {"sample_id": "S1", "system": "pipeline", "message": "Pipeline started", "status": "started"}
    entry = _build(record)["$push"]["timeline"]
    assert entry["system"] == "pipeline"
    assert entry["name"] == "Pipeline started"
    assert entry["status"] == "started:true;completed:false"
    assert entry["checkpoint"] is None


# ---------------------------------------------------------------------------
# build_mongo_update — non-checkpoint (flat) systems
# ---------------------------------------------------------------------------

def test_build_update_ok_status():
    record = {"sample_id": "S1", "system": "cdm", "message": "Uploaded to CDM", "status": "ok"}
    s = _build(record)["$set"]
    assert s["systems.cdm.status"] == "started:true;completed:true"
    assert s["systems.cdm.message"] == "Uploaded to CDM"
    assert s["systems.cdm.url"] == "https://mtlucmds1.lund.skane.se/cdm/"
    assert s["summary.queue_status"] == "completed"
    assert s["systems.cdm.ended_at"] == FIXED_NOW


def test_build_update_started_status():
    record = {"sample_id": "S1", "system": "cdm", "message": "Uploading to CDM", "status": "started"}
    s = _build(record)["$set"]
    assert s["systems.cdm.started_at"] == FIXED_NOW
    assert s["systems.cdm.ended_at"] is None
    assert s["summary.queue_status"] == "in_progress"


def test_build_update_running_status():
    record = {"sample_id": "S1", "system": "pipeline", "message": "Running", "status": "running"}
    s = _build(record)["$set"]
    assert s["systems.pipeline.started_at"] == FIXED_NOW
    assert s["systems.pipeline.ended_at"] is None
    assert s["summary.queue_status"] == "in_progress"


def test_build_update_failed_status():
    record = {"sample_id": "S1", "system": "pipeline", "message": "Pipeline failed", "status": "failed"}
    s = _build(record)["$set"]
    assert s["summary.queue_status"] == "failed"
    assert s["systems.pipeline.ended_at"] == FIXED_NOW


def test_build_update_fail_status():
    record = {"sample_id": "S1", "system": "pipeline", "message": "Pipeline failed", "status": "fail"}
    s = _build(record)["$set"]
    assert s["summary.queue_status"] == "failed"


def test_build_update_url_interpolation():
    record = {"sample_id": "ABC-123", "system": "bjorn", "message": "ok", "status": "ok", "assay": "WGS"}
    s = _build(record)["$set"]
    assert s["systems.bjorn.url"] == "https://mtlucmds1.lund.skane.se/bjorn/sample/WGS/ABC-123"


def test_build_update_url_fallback_to_base_when_placeholder_missing():
    # scout URL requires {owner}; without it, falls back to scheme://host/scout
    record = {
        "sample_id": "S1", "system": "frontend", "message": "Loaded into Scout",
        "status": "ok", "checkpoint": "scout",
    }
    s = _build(record)["$set"]
    assert s["systems.frontend.checkpoints.scout.url"] == "https://mtcmdpgm01.lund.skane.se/scout"


def test_build_update_url_resolves_with_owner():
    record = {
        "sample_id": "S1", "system": "frontend", "message": "Loaded into Scout",
        "status": "ok", "checkpoint": "scout", "owner": "test-group",
    }
    s = _build(record)["$set"]
    assert s["systems.frontend.checkpoints.scout.url"] == "https://mtcmdpgm01.lund.skane.se/test-group/S1"


def test_build_update_gens_url_resolves_with_case_id():
    record = {
        "sample_id": "S1", "system": "frontend", "message": "Loaded into Gens",
        "status": "ok", "checkpoint": "gens", "case_id": "CASE-001",
    }
    s = _build(record)["$set"]
    url = s["systems.frontend.checkpoints.gens.url"]
    assert "CASE-001" in url
    assert "S1" in url


def test_build_update_gens_url_fallback_without_case_id():
    record = {
        "sample_id": "S1", "system": "frontend", "message": "Loaded into Gens",
        "status": "ok", "checkpoint": "gens",
    }
    s = _build(record)["$set"]
    assert s["systems.frontend.checkpoints.gens.url"] == "https://mtcmdpgm01.lund.skane.se/gens"


def test_build_update_ids_set():
    record = {
        "sample_id": "S1", "system": "bjorn", "message": "ok", "status": "ok",
        "clarity_lims_id": "CLAR-001", "sequencing_run_id": "RUN-001",
    }
    s = _build(record)["$set"]
    assert s["systems.bjorn.ids"] == {"clarity_lims_id": "CLAR-001", "sequencing_run_id": "RUN-001"}


# ---------------------------------------------------------------------------
# build_mongo_update — checkpoint systems
# ---------------------------------------------------------------------------

def test_build_update_frontend_checkpoint():
    record = {
        "sample_id": "S1", "system": "frontend", "message": "Loaded into Coyote",
        "status": "ok", "checkpoint": "coyote",
    }
    s = _build(record)["$set"]
    assert s["systems.frontend.checkpoints.coyote.status"] == "started:true;completed:true"
    assert s["systems.frontend.checkpoints.coyote.message"] == "Loaded into Coyote"
    assert "S1" in s["systems.frontend.checkpoints.coyote.url"]
    assert s["systems.frontend.last_seen_at"] == FIXED_NOW
    assert s["systems.frontend.checkpoints.coyote.ended_at"] == FIXED_NOW


def test_build_update_clarity_checkpoint_started():
    record = {
        "sample_id": "S1", "system": "clarity", "message": "Registered in Clarity",
        "status": "started", "checkpoint": "registered", "clarity_lims_id": "CLAR-001",
    }
    s = _build(record)["$set"]
    assert "systems.clarity.checkpoints.registered.status" in s
    assert s["systems.clarity.checkpoints.registered.ids"] == {"clarity_lims_id": "CLAR-001"}
    assert s["systems.clarity.checkpoints.registered.started_at"] == FIXED_NOW
    assert s["systems.clarity.checkpoints.registered.ended_at"] is None


def test_build_update_checkpoint_timeline_entry():
    record = {
        "sample_id": "S1", "system": "frontend", "message": "Loaded into Coyote",
        "status": "ok", "checkpoint": "coyote",
    }
    entry = _build(record)["$push"]["timeline"]
    assert entry["checkpoint"] == "coyote"
    assert entry["system"] == "frontend"


# ---------------------------------------------------------------------------
# CLI dry-run — end-to-end MongoDB update format
# ---------------------------------------------------------------------------

def test_cli_dry_run_bjorn():
    runner = CliRunner()
    result = runner.invoke(main, ["upload", "-i", os.path.join(FIXTURES, "bjorn.csv"), "--dry-run"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "updates" in data
    assert len(data["updates"]) == 1
    update = data["updates"][0]
    assert set(update.keys()) == {"$setOnInsert", "$set", "$push"}
    assert "systems.bjorn.status" in update["$set"]
    assert "timeline" in update["$push"]


def test_cli_dry_run_clarity_uses_checkpoints():
    runner = CliRunner()
    result = runner.invoke(main, ["upload", "-i", os.path.join(FIXTURES, "clarity.csv"), "--dry-run"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data["updates"]) == 3
    for update in data["updates"]:
        checkpoint_keys = [k for k in update["$set"] if ".checkpoints." in k]
        assert checkpoint_keys, f"Expected checkpoint keys in $set, got: {list(update['$set'].keys())}"


def test_cli_dry_run_pipeline_has_failed_update():
    runner = CliRunner()
    result = runner.invoke(main, ["upload", "-i", os.path.join(FIXTURES, "pipeline.csv"), "--dry-run"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data["updates"]) == 3
    failed = [u for u in data["updates"] if u["$set"].get("summary.queue_status") == "failed"]
    assert len(failed) == 1


def test_cli_dry_run_frontend_all_checkpoints():
    runner = CliRunner()
    result = runner.invoke(main, ["upload", "-i", os.path.join(FIXTURES, "frontend.csv"), "--dry-run"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data["updates"]) == 7
    checkpoints = set()
    for update in data["updates"]:
        for key in update["$set"]:
            if ".checkpoints." in key:
                checkpoints.add(key.split(".checkpoints.")[1].split(".")[0])
    assert checkpoints == {"scout", "coyote", "bonsai", "breaxpress", "eyrie", "cll_genie", "gens"}


def test_cli_dry_run_cdm():
    runner = CliRunner()
    result = runner.invoke(main, ["upload", "-i", os.path.join(FIXTURES, "cdm.csv"), "--dry-run"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data["updates"]) == 2
    statuses = [u["$set"]["summary.queue_status"] for u in data["updates"]]
    assert statuses == ["in_progress", "completed"]


def test_cli_dry_run_unsupported_format(tmp_path):
    bad = tmp_path / "data.json"
    bad.write_text("{}")
    runner = CliRunner()
    result = runner.invoke(main, ["upload", "-i", str(bad), "--dry-run"])
    assert result.exit_code != 0
