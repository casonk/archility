# LESSONSLEARNED.md

Tracked durable lessons for `archility`.
Unlike `CHATHISTORY.md`, this file should keep only reusable lessons that should change how future sessions work in this repo.

## How To Use

- Read this file after `AGENTS.md` and before `CHATHISTORY.md` when resuming work.
- Add lessons that generalize beyond a single session.
- Keep entries concise and action-oriented.
- Do not use this file for transient status updates or full session logs.

## Lessons

- Document the repository around its real execution, curation, or integration flow instead of only the top-level folder list.
- Keep local-only, private, reference-only, or generated boundaries explicit so published or runtime behavior is not confused with offline material or non-committable inputs.
- Re-run repo-appropriate validation after changing generated artifacts, diagrams, workflows, or other CI-facing files so formatting and compatibility issues are caught before push.

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
- `pyreverse` package diagrams can look blank when they only contain empty package boxes, and class diagrams can look effectively blank in script-heavy repos that expose few classes. Normalize package outputs into package/module summary rectangles, add a low-signal note that points to the `pydeps` import graph, and exclude top-level `test` / `tests` targets from the automatic Python sidecar plan so the checked-in diagrams stay readable.
- Non-Python supplemental introspection diagrams should follow the same managed-source pattern as the Python sidecars: generate stable `.puml` sources during `archility render`, ignore those managed filenames during ordinary source discovery, and render them through the shared PlantUML path instead of introducing repo-local ad hoc scripts.
- Shell and tooling sidecars become noisy quickly if command extraction treats function definitions, case labels, or heredoc bodies as executable commands. Filter those constructs out and exclude locally defined shell functions before summarizing external tools.
- Normalize final SVG outputs in the shared render handoff, even when the upstream tool produced the file directly, so downstream repos do not rediscover missing terminal newlines only after `end-of-file-fixer` fails in CI.
- Draw.io corridor collision avoidance must track assigned corridors across both orientations on the same axis (left+right share horizontal state, up+down share vertical state). Tracking per-orientation independently allows opposite-orientation edges to still pile onto the same corridor coordinate.
- Precompute one center corridor per lane group sequentially (recording each assignment so subsequent groups treat already-claimed corridors as blocked) rather than recomputing independently per edge; this is the correct level at which to prevent cross-group corridor collisions.
- Panel containers treated as solid routing obstacles force all cross-panel edges to route far outside the diagram; exclude them from blocked-interval selection and normalize inter-row spacing to at least 60 px so corridors exist within the panel height range.
- Side-by-side nodes (same y position within a panel) must be detected as a single row during spacing normalization; treating them as vertically stacked children causes the algorithm to incorrectly separate them with a 60 px gap.
- Panel spacing normalization must account for the panel's own y-shift (accumulated from earlier panels in the same pass) when computing old_panel_bottom for the height-expansion check, otherwise the h_expand calculation is wrong for panels that were already shifted down.
- The lane group key for corridor precomputation must be (orientation, target_id), not (orientation, round(target.mid_y)). Using rounded mid_y groups unrelated edges whose targets coincidentally share the same y, causing the first edge's short span to set a corridor that routes later edges straight through intermediate panels.
- Use the union span of all edges in a lane group (min of all span_starts, max of all span_ends) for the precomputed corridor selection, and exclude all group sources and targets. This ensures the corridor is valid for every edge in the group, not only the representative.
- Span boundary exclusion in blocked-interval selection must use <= / >= (not < / >) so that a node whose padded edge exactly meets the span boundary is excluded rather than treated as an obstacle inside the corridor.
- For edges where source and target are closer than 2×clearance (e.g. side-by-side nodes in the same row), skip explicit waypoints and let Draw.io auto-route; otherwise the clearance buffer places the vertical stub inside the adjacent node.
- `pydeps` can emit a technically valid but empty 8pt Graphviz SVG for stdlib-only or otherwise graphless Python targets. The shared render path should detect those blank outputs and replace them with a readable import-summary SVG so downstream repos do not look broken.
