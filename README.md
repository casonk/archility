# archility

Architecture inventory, blueprint scaffolding, and drift-check helpers for portfolio repositories.

`archility` is intended to become the shared utility repo for architecture-aware maintenance across the portfolio. The initial scaffold focuses on a working audit CLI that can inspect repositories for core architecture artifacts and highlight missing baseline documentation.

The shared portfolio standards live in `./util-repos/traction-control` from the portfolio root. This repo is the implementation home for architecture-oriented tooling that supports those standards.

## Current Scope

- Audit one or more repositories for architecture-adjacent baseline files.
- Detect whether a repo looks code-focused and should likely carry a contributor architecture blueprint.
- Report missing architecture docs, workflow coverage, and diagram presence in either text or JSON form.
- Provide a small, dependency-free base that can later grow into blueprint scaffolding and drift checks.

## Install

```bash
python3 -m pip install -e .
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

Audit multiple repositories and emit JSON:

```bash
archility audit ../auto-pass ../nordility --json
```

Example text output fields:

- whether the target looks code-focused
- whether `AGENTS.md` and `LESSONSLEARNED.md` exist
- whether `docs/contributor-architecture-blueprint.md` exists
- how many workflow and diagram files were found
- recommended next actions

## Tests

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Contributing

See `CONTRIBUTING.md`.

## License

MIT
