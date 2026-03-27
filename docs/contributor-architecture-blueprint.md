# Contributor Architecture Blueprint

## Intent

`archility` is the portfolio utility repo for architecture-aware repository maintenance. The initial implementation is intentionally small: inspect repo structure, identify expected architecture artifacts, and report missing baseline items in a deterministic way.

## Current Components

### CLI Layer

- `src/archility/cli.py` owns argument parsing and output formatting.
- `src/archility/__main__.py` keeps `python -m archility` aligned with the console script entry point.
- The current public command is `archility audit`.
- Text output is optimized for direct terminal use; JSON output is optimized for cross-repo automation and CI integration.

### Audit Layer

- `src/archility/audit.py` owns artifact detection and recommendation generation.
- `docs/diagrams/archility-audit-flow.puml` provides a lightweight flow view of the current audit path.
- The audit model checks for:
  - `AGENTS.md`
  - `LESSONSLEARNED.md`
  - `docs/contributor-architecture-blueprint.md`
  - workflow presence under `.github/workflows/`
  - diagram presence under `docs/`
- Repositories are treated as code-like when they contain common package or source markers such as `pyproject.toml`, `src/`, `tests/`, `scripts/`, or `services/`.

## Design Constraints

- Runtime dependencies should remain minimal.
- Audit behavior should be explicit and explainable.
- The tool should support repo-local usage first and portfolio-wide automation second.
- Future generation or scaffolding features should remain additive and reviewable.

## Likely Next Extensions

- blueprint-template scaffolding for new repos
- architecture drift checks that compare docs against current repo layout
- portfolio-root batch reports that summarize architecture coverage across all repos
- optional diagram inventory or staleness checks for repos with `docs/diagrams/`
