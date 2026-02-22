# ---------------------------------------------------------------------------
# Systems
# ---------------------------------------------------------------------------
# These are the lab systems / software tools that push sample status records
# into theSamplenator via the ingest endpoint.  The `system` field in every
# ingest record should be one of these names (or a recognised alias below).
#
# Workflow order mirrors the lab processing pipeline:
#   clarity  →  demux  →  bjorn  →  pipeline  →  cdm  →  frontend
# ---------------------------------------------------------------------------

KNOWN_SYSTEMS = [
    # ---- clarity ------------------------------------------------------------
    # Sample registration and LIMS tracking (Clarity LIMSv6).
    # Pushes when a sample is registered, lab processing starts, or the
    # sample is sent to sequencing.
    # Only sequencing samples are ingested — ddPCR and similar are excluded.
    "clarity",

    # ---- demux --------------------------------------------------------------
    # Demultiplexing step.
    # Pushes when demultiplexing has started and when it completes.
    "demux",

    # ---- bjorn --------------------------------------------------------------
    # Sequencing output tracking.
    # Pushes when data is available in Bjorn.
    # Requires: sample_id + assay + clarity_lims_id or sequencing_run_id.
    "bjorn",

    # ---- pipeline -----------------------------------------------------------
    # Bioinformatics analysis pipeline (Nextflow / Snakemake).
    # Pushes when the pipeline starts and when it finishes.
    # Time-in-queue is calculated by the UI — not pushed.
    "pipeline",

    # ---- cdm ----------------------------------------------------------------
    # CDM processing step.
    # Pushes when CDM processing is done for the sample.
    "cdm",

    # ---- frontend -----------------------------------------------------------
    # Loading into downstream analysis interfaces.
    # Pushes when a sample is loaded into Scout, Coyote, Bonsai, or Breaxpress
    # (depending on assay).
    "frontend",
]

# Systems whose sub-section uses a checkpoints map rather than flat fields
CHECKPOINT_SYSTEMS = {"clarity", "frontend"}

# ---------------------------------------------------------------------------
# Field aliases
# ---------------------------------------------------------------------------
# Canonical field → list of accepted aliases (case-insensitive).
# Override at runtime with:  samplenator-cli upload file.csv --config my_config.py
# ---------------------------------------------------------------------------

FIELD_ALIASES = {
    "sample_id":          ["sampleid", "sample", "sample-id"],
    "system":             ["entity", "software", "tool", "source"],
    "message":            ["msg", "description", "notes", "note"],
    "status":             ["state", "result", "outcome"],
    "clarity_lims_id":    ["clarity", "clar_id", "clarityid"],
    "sequencing_run_id":  ["run_id", "seq_run", "sequencing_run", "runid"],
    "assay":              ["assay_type", "test", "panel"],
    "group_id":           ["group", "batch", "batch_id", "batchid"],
    "lab_id":             [],
    "sample_type":        ["type"],
    "checkpoint":         ["step", "phase"],
    "url":                [],
}

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

KNOWN_FIELDS = {
    "sample_id", "system", "message", "status",
    "clarity_lims_id", "sequencing_run_id", "assay", "group_id",
    "lab_id", "sample_type", "checkpoint", "url",
}
REQUIRED_FIELDS = {"sample_id", "system", "message", "status"}
VALID_STATUSES  = {"started", "running", "ok", "completed", "fail", "failed"}

# ---------------------------------------------------------------------------
# Status map — flat status → MongoDB compound string
# ---------------------------------------------------------------------------

STATUS_MAP = {
    "started":   "started:true;completed:false",
    "running":   "started:true;completed:false",
    "ok":        "started:true;completed:true",
    "completed": "started:true;completed:true",
    "fail":      "started:true;completed:false",
    "failed":    "started:true;completed:false",
}

# ---------------------------------------------------------------------------
# MongoDB config
# ---------------------------------------------------------------------------

MONGO_URI        = "mongodb://localhost:27017"
MONGO_DB         = "bjorn"
MONGO_COLLECTION = "sample_tracking"
