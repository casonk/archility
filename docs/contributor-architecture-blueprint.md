# Contributor Architecture Blueprint

## Intent

`archility` is the portfolio utility repo for architecture-aware repository maintenance. It owns both the shared diagram-tool bootstrap flow and the cross-repo render/audit entry points, and it defines the split between deterministic starter generation and non-deterministic agent-authored architecture.

The portfolio diagram toolchain conventions that inform this repo live in `docs/portfolio-architecture-toolchain.md`.

## Current Architecture Flow

1. A portfolio maintainer or AI agent invokes `archility` through `src/archility/cli.py` or `python -m archility`.
2. The CLI dispatches into one of three lifecycle layers:
   - `src/archility/audit.py` for inspection and recommendation generation
   - `src/archility/generate.py` for deterministic starter scaffolding
   - `src/archility/render.py` for diagram export orchestration
3. The deterministic path writes or preserves the standard architecture sources in a target repo:
   - `docs/contributor-architecture-blueprint.md`
   - `docs/diagrams/repo-architecture.puml`
   - `docs/diagrams/repo-architecture.drawio`
4. The agentic path can then replace or extend those sources after a full repository inspection, while keeping the standard file locations stable.
5. The render layer consumes those sources, along with the wrappers prepared by `setup.sh`, and produces the checked-in SVG and PNG artifacts that downstream repos carry.
6. Tests and CI validate the audit, generate, and render behavior so `archility` remains the shared orchestration home for architecture work across the portfolio.

## Current Components

### CLI Layer

- `src/archility/cli.py` owns argument parsing and output formatting.
- `src/archility/__main__.py` keeps `python -m archility` aligned with the console script entry point.
- The current public commands are `archility audit`, `archility generate`, and `archility render`.
- Text output is optimized for direct terminal use; JSON output is optimized for cross-repo automation and CI integration.
- This layer is intentionally thin: it should orchestrate the lifecycle stages, not duplicate audit, generate, or render logic.

### Audit Layer

- `src/archility/audit.py` owns artifact detection and recommendation generation.
- `docs/diagrams/archility-audit-flow.puml` provides a lightweight flow view of the current audit path.
- `docs/portfolio-architecture-toolchain.md` captures the current portfolio references for PlantUML, Draw.io, Inkscape, and Draw.io template reuse.
- The audit layer is the inspection boundary for both authoring paths because it tells maintainers what architecture assets, toolchains, and baseline gaps already exist in a target repository.
- The audit model checks for:
  - `AGENTS.md`
  - `LESSONSLEARNED.md`
  - `docs/contributor-architecture-blueprint.md`
  - workflow presence under `.github/workflows/`
  - diagram presence under `docs/`
  - source-vs-render diagram counts
  - diagram formats such as `.puml`, `.drawio`, `.png`, and `.svg`
  - documented toolchain hints from files such as `README.md`, `AGENTS.md`, `setup.sh`, and `docs/contributor-architecture-blueprint.md`
- Repositories are treated as code-like when they contain common package or source markers such as `pyproject.toml`, `src/`, `tests/`, `scripts/`, or `services/`.

### Generate Layer

- `src/archility/generate.py` owns the portfolio-standard starter layout generation path.
- The generator creates missing files without overwriting richer repo-specific architecture docs that already exist.
- This is the programmatic path: it derives the starter strictly from repository structure and code markers, so it should remain deterministic.
- This layer should be treated as scaffolding, not as the final architecture truth for repositories with non-trivial workflows.
- The current starter layout is:
  - `docs/contributor-architecture-blueprint.md`
  - `docs/diagrams/repo-architecture.puml`
  - `docs/diagrams/repo-architecture.drawio`
- Generated starter PlantUML diagrams use `!pragma layout smetana` so they do not depend on Graphviz just to produce the baseline repo-architecture view.
- Generated starter content derives focus roots from common source markers first, then falls back to top-level repo directories for docs-first repositories.

### Agentic Authoring Path

- The agentic path starts after a full repository inspection, not from fixed folder heuristics alone.
- In that path, an AI agent is expected to understand the actual runtime flow, integration points, boundaries, and contributor handoff concerns before rewriting or extending the starter artifacts.
- The agentic path is intentionally non-deterministic: two strong inspections may produce different but valid architectures.
- Even when the content becomes highly repo-specific, the standard file locations under `docs/` should remain stable so render/audit orchestration stays shared.
- For richer repos, this path is the one expected to produce the real architecture diagrams that explain how code and workflows actually behave.

### Render Layer

- `src/archility/render.py` builds deterministic render steps for PlantUML and Draw.io source files under a target repo’s `docs/diagrams/`.
- `setup.sh` owns the shared local binary/bootstrap flow for:
  - PlantUML jar + wrapper under `tools/bin/plantuml`
  - Draw.io desktop AppImage extraction + wrapper under `tools/bin/drawio`
  - Graphviz support for PlantUML diagrams that rely on `dot`
  - system-package guidance for Java and Inkscape
- `archility render <repo>` is the shared orchestration entry point that other repos should lean on instead of carrying their own diagram-tool bootstrap scripts.
- Render behavior should remain neutral to authoring mode: it should work the same way for deterministic starter diagrams and agent-authored diagrams.
- The render layer is the boundary where repo-authored sources become portfolio-standard `.svg` and `.png` artifacts.

### Validation And Reference Layer

- `tests/test_audit.py`, `tests/test_generate.py`, and `tests/test_render.py` cover the three main lifecycle stages directly.
- `.github/workflows/ci.yml` is the hosted verification surface for the repo.
- `README.md`, this blueprint, `docs/portfolio-architecture-toolchain.md`, and `docs/diagrams/archility-audit-flow.puml` are the contributor-facing reference set that explain how the lifecycle is meant to be used.
- These reference docs should stay aligned with the CLI contract and with the behavior that target repos rely on.

## Design Constraints

- Runtime dependencies should remain minimal.
- Audit behavior should be explicit and explainable.
- The tool should support repo-local usage first and portfolio-wide automation second.
- The tool should reflect the actual portfolio diagram workflow instead of inventing a separate abstraction for architecture docs.
- Shared architecture-toolchain ownership should stay centralized here rather than being copied into application or analysis repos.
- Starter-layout generation should stay additive and reviewable rather than overwriting hand-maintained architecture docs.
- The split between deterministic programmatic scaffolding and non-deterministic agentic authoring should stay explicit in both the CLI contract and the docs.
- The architecture docs for this repo should explain the lifecycle and target-repo outputs, not collapse back into a vague `src/` plus `tests/` summary.

## Likely Next Extensions

- architecture drift checks that compare docs against current repo layout
- portfolio-root batch reports that summarize architecture coverage across all repos
- optional diagram inventory or staleness checks for repos with `docs/diagrams/`
- richer render orchestration that can target multiple repos from a single portfolio run
- optional refresh modes that can safely update generated starter files while preserving repo-authored detail
- agent-facing prompt or checklist templates that help the non-deterministic authoring path produce higher-quality repo-specific architectures
