# archility

Architecture toolchain bootstrap, render orchestration, inventory, deterministic starter scaffolding, Python code-introspection diagram generation, and agentic architecture-authoring support for portfolio repositories.

`archility` is the shared utility repo for architecture-aware maintenance across the portfolio. It owns the shared bootstrap path for PlantUML, Draw.io, Graphviz-backed PlantUML rendering, and related rendering flows, in addition to the audit CLI for architecture artifacts and documentation coverage.

The shared portfolio standards live in `./util-repos/traction-control` from the portfolio root. This repo is the implementation home for architecture-oriented tooling that supports those standards.

## Current Scope

- Bootstrap the shared local architecture toolchain in one place instead of duplicating binary download logic in feature repos.
- Render PlantUML and Draw.io architecture artifacts for target repositories through a shared entry point.
- Derive supplemental Python import and UML diagrams with `pydeps` and `pyreverse` when a target repo exposes Python package or module roots.
- Support richer Graphviz-backed PlantUML diagrams in addition to the Smetana-based starter baseline.
- Audit one or more repositories for architecture-adjacent baseline files.
- Generate the standard deterministic architecture starter layout used across the portfolio:
  - `docs/contributor-architecture-blueprint.md`
  - `docs/diagrams/repo-architecture.puml`
  - `docs/diagrams/repo-architecture.drawio`
- Group taxonomy-heavy archive repos by stable subject prefixes when a flat "first few folders" starter would hide important structure.
- Provide the shared home for agent-authored repository architecture once an AI agent has fully inspected and understood a repo.
- Detect whether a repo looks code-focused and should likely carry a contributor architecture blueprint.
- Report missing architecture docs, workflow coverage, diagram source/render coverage, and detected architecture toolchains in either text or JSON form.
- Provide a small, dependency-free base that can grow into richer drift checks and broader portfolio orchestration.

## Portfolio Toolchain References

`archility` now tracks the architecture toolchain conventions already used elsewhere in the portfolio:

- `./util-repos/nordility`: paired PlantUML and Draw.io architecture sources with checked-in PNG/SVG renders
- `./personal-finance`: rich consumer example of paired PlantUML and Draw.io repo-architecture sources plus contributor-facing architecture detail
- `./drawio-templates`: reusable Draw.io templates for architecture and other diagram families

See `docs/portfolio-architecture-toolchain.md` for the concrete conventions and commands.

## Architecture Authoring Paths

`archility` supports two architecture-authoring paths.

1. Programmatic path

- `archility generate` creates the starter architecture strictly from repository code and layout markers.
- This path is deterministic and is meant for baseline scaffolding, refreshable starter docs, and repeatable portfolio-wide rollouts.
- For Python repos, `archility render` can also derive deterministic `pydeps` and `pyreverse` sidecar diagrams from the detected top-level Python package or module targets.

2. Agentic path

- An AI agent inspects the repository end-to-end, understands the real execution flow and boundaries, and then writes a unique architecture from that understanding.
- This path is intentionally non-deterministic. It should preserve the standard file locations, but the authored content can diverge substantially from the starter.

Use the programmatic path for consistency and the agentic path for depth.

## Repository Architecture

`archility` itself is organized around an architecture-maintenance lifecycle rather than a generic package layout.

- Public entry surface: `src/archility/cli.py` and `src/archility/__main__.py` expose `audit`, `generate`, and `render`.
- Inspection path: `src/archility/audit.py` inventories architecture assets, workflow coverage, source roots, and documented toolchain hints, then emits text or JSON reports.
- Deterministic scaffolding path: `src/archility/generate.py` derives starter blueprints and diagram sources strictly from repository structure.
- Agentic authoring path: a repository-specific AI inspection rewrites those standard files with richer architecture once the repo is actually understood.
- Render path: `src/archility/render.py` turns PlantUML and Draw.io sources into checked-in SVG and PNG artifacts for target repos, and can also derive `pydeps` SVG import graphs plus `pyreverse` PlantUML sources/renders for Python repos.
- Shared bootstrap path: `setup.sh` provisions the local wrappers under `tools/bin/` for PlantUML, Draw.io, `pydeps`, `pyreverse`, and optional Graphviz-backed PlantUML rendering.
- Validation path: `tests/test_audit.py`, `tests/test_generate.py`, `tests/test_render.py`, and `.github/workflows/ci.yml` keep the lifecycle behavior aligned.

The paired `docs/diagrams/repo-architecture.{puml,drawio}` files describe this lifecycle from the perspective of a portfolio maintainer invoking `archility` against target repositories.

## Install

```bash
python3 -m pip install -e .
bash setup.sh
```

Or run directly from the repo root:

```bash
PYTHONPATH=src python3 -m archility --help
```

## CLI Usage

Audit the current repository:

```bash
archility audit .
```

Generate the standard architecture starter files for another repository:

```bash
archility generate ../../personal-finance
```

Render architecture diagrams for another repository after bootstrapping the shared toolchain:

```bash
archility render ../../personal-finance
```

Render is shared infrastructure for both paths. The source diagrams may come from deterministic scaffolding or from a deeper agent-authored architecture pass. For Python repos, the same render pass also derives supplemental `pydeps` and `pyreverse` diagrams from detected package or module roots.

Audit multiple repositories and emit JSON:

```bash
archility audit ../auto-pass ../nordility --json
```

Example text output fields:

- whether the target looks code-focused
- whether `AGENTS.md` and `LESSONSLEARNED.md` exist
- whether `docs/contributor-architecture-blueprint.md` exists
- whether the standard `docs/diagrams/repo-architecture.{puml,drawio}` starter files were generated or already existed
- whether Python repos are documenting `pydeps` and `pyreverse` in the shared diagram toolchain hints
- how many workflow, diagram-source, and render-artifact files were found
- which diagram formats were detected
- which architecture toolchains were detected, including PlantUML, Draw.io, `pydeps`, `pyreverse`, and Inkscape hints where present
- which shared render commands `archility` will execute during a dry-run render plan
- recommended next actions

The generated starter PlantUML diagrams use Smetana, so they do not depend on a local Graphviz install. `archility` still treats Graphviz as a supported part of the shared toolchain because richer custom PlantUML diagrams may rely on `dot`.

The `pydeps` and `pyreverse` outputs are supplemental deterministic introspection diagrams. They help explain Python package and module structure, but they do not replace the repo-authored `docs/contributor-architecture-blueprint.md` or the paired `repo-architecture` sources.

For Draw.io diagrams, prefer plain identifier text inside diagram labels when checked-in PNG exports matter. Backticks can render inconsistently in draw.io's direct PNG export path even when the SVG looks acceptable.

## Tests

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Contributing

See `CONTRIBUTING.md`.

## License

MIT
