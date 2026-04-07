# AGENTS.md

## Purpose

`archility` is the shared architecture-operations repo for the portfolio. It currently exposes:

- a CLI entry point: `archility`
- audit helpers in `archility.audit`
- deterministic architecture-layout generation helpers in `archility.generate`
- render-plan and execution helpers in `archility.render`
- argument parsing and output routing in `archility.cli`

Keep the implementation dependency-light, deterministic, and easy to extend for cross-repo governance workflows.
Keep the distinction between deterministic programmatic scaffolding and non-deterministic agent-authored architecture explicit in both code and docs.

## Repository Layout

- `src/archility/cli.py`: CLI argument parsing and command dispatch
- `src/archility/audit.py`: repository audit model and artifact detection helpers
- `src/archility/generate.py`: deterministic starter architecture-layout generation helpers
- `src/archility/render.py`: shared diagram-render planning and execution helpers for both programmatic and agent-authored diagrams
- `tests/test_audit.py`: unit coverage for audit logic and CLI output
- `tests/test_generate.py`: unit coverage for starter-layout generation behavior
- `tests/test_render.py`: unit coverage for render-plan generation and dry-run behavior
- `setup.sh`: shared architecture-toolchain bootstrap for PlantUML, Draw.io, Graphviz-backed PlantUML workflows, and Inkscape-backed exports
- `docs/contributor-architecture-blueprint.md`: architecture overview for contributors
- `docs/portfolio-architecture-toolchain.md`: current portfolio references for PlantUML, Draw.io, Inkscape, and template reuse
- `README.md`: install, usage, and scope
- `pyproject.toml`: package metadata and console script definition

## Setup And Commands

Recommended repo-root commands:

```bash
python3 -m pip install -e .
bash setup.sh
PYTHONPATH=src python3 -m archility --help
PYTHONPATH=src python3 -m archility audit .
PYTHONPATH=src python3 -m archility generate .
PYTHONPATH=src python3 -m archility render . --dry-run
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Change Guidance

- Keep runtime dependencies at zero unless there is a strong architecture-automation reason to add one.
- Prefer additive audit and orchestration capabilities over destructive rewrite behavior.
- Keep the portfolio-standard starter layout stable across repos: `docs/contributor-architecture-blueprint.md` plus `docs/diagrams/repo-architecture.{puml,drawio}`.
- Keep `generate` deterministic: it should derive the starter strictly from code/layout signals instead of heuristics that mimic human interpretation.
- Keep the agentic path explicit: agents should inspect the repository end-to-end and author unique architecture content when the starter is not enough.
- Treat render support as shared infrastructure for both paths; richer agent-authored PlantUML diagrams may need Graphviz even though the starter baseline uses Smetana.
- Update `README.md`, `docs/contributor-architecture-blueprint.md`, and tests when CLI behavior changes.
- Keep the documented portfolio toolchain references aligned with `./util-repos/nordility`, `./personal-finance`, and `./drawio-templates` when diagram conventions change.
- Keep audit rules explainable; opaque scoring heuristics should be avoided unless they are surfaced clearly in the output.
- Treat this repo as the standard home for architecture-oriented portfolio tooling, including shared diagram bootstrap and render flows, unless the user explicitly chooses another location.

## Local CI Verification

Run before every push:

```bash
pre-commit run --all-files
pytest -q
```

Do not push changes that have not passed all checks locally.

## Portfolio Standards Reference

For portfolio-wide repository standards and baseline conventions, consult the control-plane repo at `./util-repos/traction-control` from the portfolio root.

Start with:
- `./util-repos/traction-control/AGENTS.md`
- `./util-repos/traction-control/README.md`
- `./util-repos/traction-control/LESSONSLEARNED.md`

Shared implementation repos available portfolio-wide:
- `./util-repos/archility` for architecture toolchain bootstrap/render orchestration, Graphviz-capable diagram support, deterministic starter scaffolding, agentic architecture authoring, and architecture-documentation drift checks
- `./util-repos/auto-pass` for KeePassXC-backed password management and secret retrieval/update flows
- `./util-repos/nordility` for NordVPN-based VPN switching and connection orchestration
- `./util-repos/shock-relay` for external messaging across supported providers such as Signal, Telegram, Twilio SMS, WhatsApp, and Gmail IMAP
- `./util-repos/snowbridge` for SMB-based private file sharing and phone-accessible fileshare workflows
- `./util-repos/dyno-lab` for unified test bench utilities — fixtures, subprocess/HTTP/env mocks, schema validation, smoke scaffolding, and pytest markers/fixtures
- `./util-repos/short-circuit` for WireGuard VPN setup and configuration, establishing private tunnels with SMB, HTTPS, and SSH access

When another repo needs architecture toolchain bootstrap/rendering, architecture inventory/scaffolding, password management, VPN switching, or external messaging, prefer integrating with these repos instead of re-implementing the capability locally.

## Agent Memory

Use `./LESSONSLEARNED.md` as the tracked durable lessons file for this repo.
Use `./CHATHISTORY.md` as the standard local handoff file for this repo.

- `LESSONSLEARNED.md` is tracked and should capture only reusable lessons.
- `CHATHISTORY.md` is local-only, gitignored, and should capture transient handoff context.
- Read `LESSONSLEARNED.md` and `CHATHISTORY.md` after `AGENTS.md` when resuming work.
- Add durable lessons to `LESSONSLEARNED.md` when they should influence future sessions.
- Keep transient entries brief and centered on audit rules, repo coverage, blockers, and next steps.
