# capsule/ — Code Ocean / Zenodo capsule layout (task 053)

This directory arranges the repository in the layout compute-capsule
services (Code Ocean) and archives (Zenodo) expect:

- `metadata.yml` — capsule metadata (title, authors, license
  placeholder, description, keywords).
- `code/` — pointer to the source: the capsule's code is the
  repository root (`src/agentorch`, `governance/`, `tests/`); see
  `code/README.md` and the top-level `README.md`.
- `environment/` — pointer to the pinned environment: top-level
  `Dockerfile` and `environment/requirements.lock`; see
  `environment/README.md`.
- Run script — the capsule entrypoint is the top-level `run.sh`
  (equivalent to Code Ocean's `code/run`); `demo.sh` is the quick
  smoke entrypoint.

## Publishing is a HUMAN step

Publishing this capsule (creating the Code Ocean capsule, uploading to
Zenodo, minting a DOI, inserting the resulting URL/DOI into the
manuscript and `CITATION.cff`) is **explicitly left to the human
author** per project policy (`CLAUDE.md`, "Forbidden autonomous
actions"). The repository is public at
https://github.com/shikher20goel/multi-agent-genai-orchestration-patterns;
the archived-artifact DOI is minted at the tagged GitHub release via
Zenodo and is recorded in the manuscript's Data Availability statement
once live.
