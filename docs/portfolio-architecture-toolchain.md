# Portfolio Architecture Toolchain

`archility` now owns the shared architecture-diagram workflow across the portfolio. Feature repos should consume this toolchain instead of carrying their own PlantUML/draw.io bootstrap copies.

## Authoring Paths

- Programmatic path
  - `archility generate` creates the baseline architecture assets strictly from repository structure and code markers.
  - This path is deterministic and intended for repeatable scaffolding.
- Agentic path
  - An AI agent inspects the repository, understands the implementation in depth, and writes a unique architecture from that understanding.
  - This path is non-deterministic and is intended to replace or expand the starter with richer repo-specific detail.
- Both paths should keep the shared artifact locations stable under `docs/contributor-architecture-blueprint.md` and `docs/diagrams/`.

## Current Convention

- Keep the starter architecture layout stable across repos:
  - `docs/contributor-architecture-blueprint.md`
  - `docs/diagrams/repo-architecture.puml`
  - `docs/diagrams/repo-architecture.drawio`
- Keep editable diagram sources under `docs/diagrams/`.
- Use PlantUML source files such as `.puml` or `.plantuml` when text-first diagrams are a good fit.
- Use Draw.io source files such as `.drawio` when manual layout or template reuse is more useful.
- Allow `archility render` to derive supplemental deterministic sidecars under `docs/diagrams/` when matching source signals exist:
  - Python: `pydeps` SVG import graphs and `pyreverse` PlantUML UML diagrams
  - Shell: managed PlantUML shell-flow diagrams
  - SQL/schema: managed PlantUML database-schema diagrams
  - Tooling entrypoints: managed PlantUML tooling-integration diagrams
- Check in rendered `.png` and/or `.svg` artifacts next to the source diagrams so contributors can review them without opening the source tool.
- The generated `repo-architecture.puml` starter diagrams use PlantUML's Smetana layout so they can render cleanly without a local Graphviz install.
- Keep Graphviz available through the shared `archility` bootstrap because richer or older PlantUML diagrams may still depend on `dot`.
- When SVG-to-PNG conversion needs to be scripted, Inkscape is an accepted local tool in the current portfolio.

## Portfolio References

- `./util-repos/nordility`
  - Uses paired PlantUML and Draw.io architecture sources under `docs/diagrams/`.
  - Keeps checked-in `.png` and `.svg` renders alongside those sources.
  - Documents the local regeneration command in `docs/contributor-architecture-blueprint.md`.
- `./personal-finance`
  - Documents both PlantUML and Draw.io architecture files in `README.md`.
  - Uses the same repo-architecture starter filenames now standardized across the portfolio.
  - Remains a key reference repo for the current architecture artifact layout and render outputs.
- `./drawio-templates`
  - Acts as the reusable Draw.io template source for architecture-diagram starting points and previews.

## Reference Commands

PlantUML render flow:

```bash
plantuml -tpng -tsvg docs/diagrams/repo-architecture.puml
```

Python import/UML sidecar flow:

```bash
pyreverse --output puml --output-directory docs/diagrams --project repo-name --source-roots src src/your_package
pydeps --no-config --noshow --max-bacon 0 -T svg -o docs/diagrams/python-import-deps-src-your_package.svg src/your_package
```

Inkscape-backed SVG to PNG export flow:

```bash
inkscape docs/diagrams/repo-architecture.drawio.svg --export-type=png --export-filename=docs/diagrams/repo-architecture.drawio.png
```

## How Archility Uses This

- `archility/setup.sh` is the shared local bootstrap for PlantUML, Draw.io, `pydeps`, `pyreverse`, Graphviz-backed PlantUML support, and related system prerequisites.
- `archility generate <repo>` creates the standard starter blueprint and repo-architecture source files when they are missing.
- `archility render <repo>` is the shared render entry point for target repositories regardless of whether the source diagrams were programmatically generated or agent-authored.
- On repos with supported source signals, `archility render <repo>` also derives deterministic supplemental sidecars for Python package/module structure, shell-script flow, SQL/schema structure, and tooling integrations.
- `archility audit` detects source diagram formats such as `.puml`, `.plantuml`, and `.drawio`.
- It also reports render artifacts such as `.png` and `.svg`.
- Toolchain detection is inferred from source files plus contributor-facing hints in files like `README.md`, `AGENTS.md`, `setup.sh`, and `docs/contributor-architecture-blueprint.md`.
- Current toolchain names surfaced by the audit include `plantuml`, `drawio`, `pydeps`, `pyreverse`, `inkscape`, and `mermaid`.
