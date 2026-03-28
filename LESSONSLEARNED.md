# LESSONSLEARNED.md

Tracked durable lessons for `archility`.
Unlike `CHATHISTORY.md`, this file should keep only reusable lessons that should change how future sessions work in this repo.

## How To Use

- Read this file after `AGENTS.md` and before `CHATHISTORY.md` when resuming work.
- Add lessons that generalize beyond a single session.
- Keep entries concise and action-oriented.
- Do not use this file for transient status updates or full session logs.

## Lessons

- If the repo documents `python -m archility` as a supported invocation path, keep `src/archility/__main__.py` in place so the module and console-script entry points stay aligned.
- The current portfolio architecture-diagram convention is PlantUML and/or Draw.io source files plus checked-in PNG/SVG renders, with Inkscape showing up in bootstrap scripts when SVG-to-PNG export needs to be scripted.
- Shared architecture toolchain downloads and wrappers should live in `archility`, not in feature repos that only consume the rendered diagram outputs.
- Cross-repo architecture automation is easier to keep deterministic when every repo uses the same starter filenames: `docs/contributor-architecture-blueprint.md` plus `docs/diagrams/repo-architecture.{puml,drawio}`.
- The generated `repo-architecture.puml` starter diagrams should use PlantUML's Smetana layout so the portfolio baseline does not depend on a machine-local Graphviz install just to render the starter view.
- Keep the two authoring paths explicit: `archility generate` is the deterministic programmatic starter path, while agent-authored repo architecture should come from full repository inspection and remain intentionally non-deterministic.
- Even with Smetana as the starter default, `archility` should continue to support Graphviz-backed PlantUML diagrams because richer repo-specific diagrams may still depend on `dot`.
- Draw.io PNG exports can render backticked identifiers oddly even when the corresponding SVG looks acceptable, so prefer plain identifier text in diagram labels when checked-in PNG artifacts matter.
- The shared draw.io wrapper should pass `--no-sandbox` so headless exports remain usable in sandboxed or CI-like environments.
- Docs-first archive repos with many coded top-level directories, such as course archives, should be grouped by stable prefixes like `CSC/` or `MTH/` instead of truncating the architecture starter to the first few directories.
- Architecture-tooling repos like `archility` should be diagrammed around the lifecycle they orchestrate: inspect, scaffold, agent-author, render, and validate, plus the shared toolchain boundary and target-repo outputs.
- Python sidecar diagrams should stay explicitly supplemental to the repo-authored architecture, be generated through `archility render`, normalize `pyreverse` outputs to stable filenames, and pass `--no-config` to `pydeps` so user or repo config does not silently change the deterministic output contract.
- Render-source discovery should ignore repo-specific transient `pyreverse` filenames like `classes_<repo>.puml` and `packages_<repo>.puml`, otherwise a partial failed run can cause those temporary files to be re-rendered as if they were primary checked-in diagrams on later passes.
- `pyreverse` can emit a package-level `.puml` for multi-module repos even when the targets are plain `.py` files rather than package directories, so the normalized `python-packages.puml` path should be planned whenever a repo contributes more than one Python diagram target.
- Draw.io overlap fixes belong in the shared render path, not only in deterministic starter generation: checked-in repo diagrams may already be agent-authored, so `archility render` should normalize draw.io edge styles in place (for example line-jump settings) before export instead of replacing richer custom sources with the starter layout.
- Draw.io line-jump styling alone is not enough to materially clean up dense diagrams; the shared render path should route managed edges through open horizontal or vertical corridors between obstacle bands so exported PNG/SVG artifacts stop cutting straight through occupied node rows.
