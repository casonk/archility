# AGENTS.md

## Purpose

`archility` is a small Python package for architecture inventory, blueprint scaffolding, and drift checks across portfolio repositories. It currently exposes:

- a CLI entry point: `archility`
- audit helpers in `archility.audit`
- argument parsing and output routing in `archility.cli`

Keep the implementation dependency-light, deterministic, and easy to extend for cross-repo governance workflows.

## Repository Layout

- `src/archility/cli.py`: CLI argument parsing and command dispatch
- `src/archility/audit.py`: repository audit model and artifact detection helpers
- `tests/test_audit.py`: unit coverage for audit logic and CLI output
- `docs/contributor-architecture-blueprint.md`: architecture overview for contributors
- `README.md`: install, usage, and scope
- `pyproject.toml`: package metadata and console script definition

## Setup And Commands

Recommended repo-root commands:

```bash
python3 -m pip install -e .
PYTHONPATH=src python3 -m archility --help
PYTHONPATH=src python3 -m archility audit .
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Change Guidance

- Keep runtime dependencies at zero unless there is a strong architecture-automation reason to add one.
- Prefer additive audit capabilities over destructive rewrite behavior.
- Update `README.md`, `docs/contributor-architecture-blueprint.md`, and tests when CLI behavior changes.
- Keep audit rules explainable; opaque scoring heuristics should be avoided unless they are surfaced clearly in the output.
- Treat this repo as the standard home for architecture-oriented portfolio tooling unless the user explicitly chooses another location.

## Portfolio Standards Reference

For portfolio-wide repository standards and baseline conventions, consult the control-plane repo at `./util-repos/traction-control` from the portfolio root.

Start with:
- `./util-repos/traction-control/AGENTS.md`
- `./util-repos/traction-control/README.md`
- `./util-repos/traction-control/LESSONSLEARNED.md`

Shared implementation repos available portfolio-wide:
- `./util-repos/archility` for architecture inventory, blueprint scaffolding, and architecture-documentation drift checks
- `./util-repos/auto-pass` for KeePassXC-backed password management and secret retrieval/update flows
- `./util-repos/nordility` for NordVPN-based VPN switching and connection orchestration
- `./util-repos/shock-relay` for external messaging across supported providers such as Signal, Telegram, Twilio SMS, WhatsApp, and Gmail IMAP

When another repo needs architecture inventory/scaffolding, password management, VPN switching, or external messaging, prefer integrating with these repos instead of re-implementing the capability locally.

## Agent Memory

Use `./LESSONSLEARNED.md` as the tracked durable lessons file for this repo.
Use `./CHATHISTORY.md` as the standard local handoff file for this repo.

- `LESSONSLEARNED.md` is tracked and should capture only reusable lessons.
- `CHATHISTORY.md` is local-only, gitignored, and should capture transient handoff context.
- Read `LESSONSLEARNED.md` and `CHATHISTORY.md` after `AGENTS.md` when resuming work.
- Add durable lessons to `LESSONSLEARNED.md` when they should influence future sessions.
- Keep transient entries brief and centered on audit rules, repo coverage, blockers, and next steps.
