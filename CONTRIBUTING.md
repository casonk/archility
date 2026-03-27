# Contributing

`archility` is the shared utility repo for architecture inventory and documentation-audit workflows across the portfolio.

## Workflow

1. Keep changes scoped to one architecture-maintenance theme when possible.
2. Update `README.md`, `AGENTS.md`, and `docs/contributor-architecture-blueprint.md` when CLI behavior or repo expectations change.
3. Add or update tests in the same change when audit logic changes.
4. Use Conventional Commits such as `feat: add repo audit command` or `docs: refine architecture guidance`.

## Quality Gates

Run these repo-root commands before publishing changes:

```bash
python3 -m pip install -e .
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m archility audit .
```

## Content Standards

- Keep runtime dependencies minimal unless they materially improve cross-repo architecture automation.
- Prefer deterministic, inspectable output over opaque heuristics.
- Treat architecture drift checks as governance support, not as permission to rewrite repo structure automatically.
- Keep portfolio-wide standards aligned with `./util-repos/traction-control`.
