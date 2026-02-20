# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------
# These are the lab systems / software tools that push sample status records
# into theSamplenator via the ingest endpoint.  The `entity` field in every
# ingest record should be one of these names (or a recognised alias below).
#
# Workflow order mirrors the lab processing pipeline:
#   Clarity  →  Bjorn  →  Pipeline  →  Middleman  (→  BLISKO, future)
# ---------------------------------------------------------------------------

KNOWN_ENTITIES = [
    # ---- Clarity ------------------------------------------------------------
    # Sample registration and LIMS tracking (Clarity LIMSv6).
    # Pushes when a sample is registered, lab processing starts, or the
    # sample is sent to sequencing.
    # Only sequencing samples are ingested — ddPCR and similar are excluded.
    "Clarity",

    # ---- Bjorn --------------------------------------------------------------
    # Sequencing output and demultiplexing.
    # Pushes when demux has started and when data is available in Bjorn.
    # Requires: sample_id + assay + clarity_id or sequencing_run_id.
    "Bjorn",

    # ---- Pipeline -----------------------------------------------------------
    # Bioinformatics analysis pipeline (Nextflow / Snakemake).
    # Pushes when the pipeline starts and when it finishes.
    # Time-in-queue is calculated by the UI — not pushed.
    "Pipeline",

    # ---- Middleman ----------------------------------------------------------
    # CDM step and loading into downstream analysis interfaces.
    # Pushes when CDM is done and when a sample is loaded into
    # Scout, Coyote, Bonsai, or Breaxpress (depending on assay).
    "Middleman",

    # ---- BLISKO (future / bonus) -------------------------------------------
    # RS-LIMS integration. When a sample appears in BLISKO it may be
    # propagated here. Integration pending investigation.
    "BLISKO",
]

# ---------------------------------------------------------------------------
# Field aliases
# ---------------------------------------------------------------------------
# Canonical field → list of accepted aliases (case-insensitive).
# Override at runtime with:  samplenator-ingest file.csv --config my_config.py
# ---------------------------------------------------------------------------

FIELD_ALIASES = {
    "sample_id":          ["lab_id", "sampleid", "sample", "sample-id"],
    "entity":             ["system", "software", "tool", "source"],
    "message":            ["msg", "description", "notes", "note"],
    "status":             ["state", "result", "outcome"],
    "clarity_lims_id":    ["clarity", "clar_id", "clarityid"],
    "sequencing_run_id":  ["run_id", "seq_run", "sequencing_run", "runid"],
    "assay":              ["assay_type", "test", "panel"],
    "group_id":           ["group", "batch", "batch_id", "batchid"],
}

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

KNOWN_FIELDS = {
    "sample_id", "entity", "message", "status",
    "clarity_lims_id", "sequencing_run_id", "assay", "group_id",
}
REQUIRED_FIELDS = {"sample_id", "entity", "message", "status"}
VALID_STATUSES = {"ok", "fail"}

# ---------------------------------------------------------------------------
# MongoDB config
# ---------------------------------------------------------------------------

MONGO_URI        = "mongodb://localhost:27017"
MONGO_DB         = "bjorn"
MONGO_COLLECTION = "sample_tracking"
