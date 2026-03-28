# Changelog

All notable changes to `archility` are documented here.

## Unreleased

- Initialized `archility` as the shared architecture inventory and drift-check utility repo.
- Added a dependency-free audit CLI, tests, CI, and portfolio-standard governance files.
- Added a module entry point and architecture diagram artifact so the documented CLI paths and self-audit output stay aligned.
- Added portfolio-aware architecture toolchain detection for PlantUML, Draw.io, and Inkscape-backed workflows, plus documentation that points back to the current cross-repo references.
- Added shared toolchain ownership in `setup.sh` plus a `render` command so architecture runs can be orchestrated from `archility` instead of repo-local bootstrap scripts.
- Added a `generate` command that scaffolds the shared starter architecture layout used across the portfolio without overwriting richer existing repo docs.
- Corrected render orchestration so PlantUML outputs are normalized into `.puml.svg/.puml.png`, Draw.io exports use the working CLI wrapper, and the shared bootstrap now includes Graphviz for future clean installs.
- Updated the generated starter PlantUML diagrams to use Smetana layout so the repo-architecture baseline renders cleanly without relying on Graphviz.
