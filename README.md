# samplenator-cli

Ingest CLI for theSamplenator. Reads sample status records from CSV, TSV, or YAML files and writes them directly to MongoDB using upsert — multiple records for the same `sample_id` merge into one document, with each system writing only to its own sub-section (`systems.<name>`).

---

## Install

```bash
pip install -e tools/samplenator-cli
```

Or from within this directory:

```bash
pip install -e .
```

---

## Usage

```
samplenator-cli upload -i <file> [--mongo-uri URI] [--mongo-db DB] [--mongo-collection COL] [--dry-run] [--config PATH]
```

| Argument | Description |
|---|---|
| `-i` / `--input` | Input file — `.csv`, `.tsv`, `.yaml`, or `.yml` |
| `--mongo-uri` | MongoDB URI (env: `SAMPLENATOR_MONGO_URI`, default: `mongodb://localhost:27017`) |
| `--mongo-db` | MongoDB database name (env: `SAMPLENATOR_MONGO_DB`, default: `bjorn`) |
| `--mongo-collection` | MongoDB collection name (env: `SAMPLENATOR_MONGO_COLLECTION`, default: `sample_tracking`) |
| `--dry-run` | Parse and validate only — prints JSON update documents, does not write to MongoDB |
| `--config` | Path to an alternate `config.py` for custom field aliases |

### Env var resolution order (per argument)

1. Explicit CLI flag
2. Environment variable (`SAMPLENATOR_MONGO_URI`, `SAMPLENATOR_MONGO_DB`, `SAMPLENATOR_MONGO_COLLECTION`)
3. Config default (`cfg.MONGO_URI`, etc.)

### Examples

```bash
# Dry run to verify field mapping before inserting
samplenator-cli upload -i export.csv --dry-run

# Upsert a YAML batch to the default local MongoDB
samplenator-cli upload -i batch.yaml

# Insert to a specific database/collection
samplenator-cli upload -i results.tsv --mongo-uri mongodb://localhost:27017 --mongo-db bjorn --mongo-collection sample_tracking

# Via environment variables
SAMPLENATOR_MONGO_URI=mongodb://localhost:27017 samplenator-cli upload -i samples.yaml

# Custom alias config for a non-standard LIMS export
samplenator-cli upload -i lims_export.csv --config /path/to/my_config.py
```

---

## Input formats

**CSV** (`.csv`):

```csv
sample_id,system,msg,state,clarityid,run_id,panel,batch_id
SAMPLE-001,bjorn,Demux complete,ok,CLAR-1001,RUN-2026-001,WGS,LB-2026-0301
```

**TSV** (`.tsv`) — same columns, tab-delimited.

**YAML** (`.yaml` / `.yml`):

```yaml
- sample_id: SAMPLE-001
  system: bjorn
  message: Demux complete
  status: ok
  clarity_lims_id: CLAR-1001
  sequencing_run_id: RUN-2026-001
  assay: WGS
  group_id: LB-2026-0301
```

With a checkpoint system (clarity or frontend):

```yaml
- sample_id: SAMPLE-001
  system: frontend
  message: Loaded into Scout
  status: ok
  checkpoint: scout
  url: https://scout.example.com/cases/SAMPLE-001
```

---

## Field reference

| Field | Required | Valid values | Notes |
|---|---|---|---|
| `sample_id` | yes | any string | Primary identifier |
| `system` | yes | see [Systems](#systems) | Reporting system (lowercase) |
| `message` | yes | any string | Human-readable status note |
| `status` | yes | `started`, `running`, `ok`, `completed`, `fail`, `failed` | Normalised to lowercase |
| `clarity_lims_id` | no | any string | Clarity LIMS ID |
| `sequencing_run_id` | no | any string | Sequencing run ID |
| `assay` | no | any string | Assay / panel name |
| `group_id` | no | any string | Batch or lab batch ID |
| `lab_id` | no | any string | Lab identifier (separate from sample_id) |
| `sample_type` | no | any string | Sample type |
| `checkpoint` | no | any string | Step or phase (required for granular clarity/frontend tracking) |
| `url` | no | any string | URL to the sample in an analysis interface |

### Field alias mapping

Non-standard column names are automatically mapped to canonical field names (defined in `samplenator_cli/config.py`):

| Canonical field | Accepted aliases |
|---|---|
| `sample_id` | `sampleid`, `sample`, `sample-id` |
| `system` | `entity`, `software`, `tool`, `source` |
| `message` | `msg`, `description`, `notes`, `note` |
| `status` | `state`, `result`, `outcome` |
| `clarity_lims_id` | `clarity`, `clar_id`, `clarityid` |
| `sequencing_run_id` | `run_id`, `seq_run`, `sequencing_run`, `runid` |
| `assay` | `assay_type`, `test`, `panel` |
| `group_id` | `group`, `batch`, `batch_id`, `batchid` |
| `sample_type` | `type` |
| `checkpoint` | `step`, `phase` |

Provide `--config path/to/config.py` to use your own mappings. Use `samplenator_cli/config.py` as a template.

---

## Systems

These are the lab systems that push sample status updates into theSamplenator. The `system` field in every ingest record must identify which system is reporting (lowercase).

### clarity

**Role:** Sample registration and LIMS tracking (Clarity LIMSv6).

Pushes status when:
- A sample is registered in Clarity
- Lab processing has started
- The sample has been sent to sequencing

> Only sequencing samples are ingested. ddPCR and similar assay types are excluded.

Uses **checkpoints** — supply `checkpoint` (e.g. `registered`, `lab_processing`, `sent_to_sequencing`) for granular tracking. Defaults to `default` if omitted.

**Typical messages:** `"Registered in Clarity"`, `"Lab processing started"`, `"Sent to sequencing"`

---

### demux

**Role:** Demultiplexing step.

Pushes status when:
- Demultiplexing has started
- Demultiplexing is complete

**Typical messages:** `"Demux started"`, `"Demux complete"`

---

### bjorn

**Role:** Sequencing output tracking.

Pushes status when data is available in Bjorn.

**Required fields:** `sample_id`, `assay`, and at least one of `clarity_lims_id` / `sequencing_run_id`.

**Typical messages:** `"Data available in Bjorn"`

---

### pipeline

**Role:** Bioinformatics analysis pipeline (Nextflow / Snakemake).

Pushes status when:
- The pipeline has started for the sample
- The pipeline has finished

> Time-in-queue is calculated by the UI from timestamps — it is not pushed.

**Typical messages:** `"Pipeline started"`, `"Pipeline completed"`

---

### cdm

**Role:** CDM processing step.

Pushes status when CDM processing is done for the sample.

**Typical messages:** `"CDM complete"`

---

### frontend

**Role:** Loading into downstream analysis interfaces.

Pushes status when a sample is loaded into an analysis interface.

Uses **checkpoints** — supply `checkpoint` with the interface name (e.g. `scout`, `coyote`, `bonsai`, `breaxpress`). Defaults to `default` if omitted.

Analysis interfaces: **Scout**, **Coyote**, **Bonsai**, or **Breaxpress** — depending on assay.

**Typical messages:** `"Loaded into Scout"`, `"Loaded into Coyote"`

---

## MongoDB behaviour

Each record is written as a single `update_one(..., upsert=True)` call keyed on `sample_id`:

- **New sample:** a document is created with `timestamps.created_at` set once.
- **Existing sample:** only the fields for the reporting system (`systems.<name>`) are updated — other systems' data is untouched.
- **Timeline:** every ingest appends an entry to the `timeline` array, preserving full history.
- **Checkpoint systems** (`clarity`, `frontend`): data is nested under `systems.<name>.checkpoints.<checkpoint>`, allowing multiple checkpoints per system per sample.

---

## Docker

Build from the **repo root**:

```bash
docker build -t samplenator-cli .
```

Run the CLI inside the container (mount the directory containing your input file):

```bash
# Dry run
docker run --rm -v /path/to/data:/data samplenator-cli \
  upload -i /data/samples.csv --dry-run

# Insert into MongoDB
docker run --rm -v /path/to/data:/data samplenator-cli \
  upload -i /data/samples.csv \
  --mongo-uri mongodb://host.docker.internal:27017
```

---

## Package structure

```
samplenator-cli/
├── Dockerfile
├── pyproject.toml             # Package metadata + samplenator-cli entry point
└── samplenator_cli/
    ├── __init__.py
    ├── __version__.py
    ├── cli.py                 # CLI entry point (subcommands: upload)
    ├── config.py              # KNOWN_SYSTEMS, FIELD_ALIASES, MONGO_URI/DB/COLLECTION
    └── ingest.py              # parse_file, resolve_aliases, validate_record, build_mongo_update
```
