# REFS-PUBLIC.md - Public References

> Record external public repositories, datasets, documentation, APIs, or other
> public resources that this repository utilizes or depends on.
> This file is tracked and intentionally kept free of private or local-only details.

## Public Repositories

- https://github.com/plantuml/plantuml - PlantUML renderer used for checked-in diagram outputs
- https://github.com/jgraph/drawio - draw.io / diagrams.net project used for .drawio exports
- https://github.com/thebjorn/pydeps - import-graph sidecar generation
- https://github.com/pylint-dev/pylint - pyreverse UML sidecar generation

## Public Datasets and APIs

- No standing external data APIs are required; the tool operates on local repository content.

## Documentation and Specifications

- https://plantuml.com/ - PlantUML language and rendering reference
- https://www.drawio.com/doc/ - draw.io / diagrams.net documentation
- https://graphviz.org/documentation/ - Graphviz documentation for richer PlantUML layouts when custom diagrams rely on dot

## Notes

- archility is a local toolchain orchestrator. Its public dependency surface is the diagram and introspection toolchain, not a remote service API.
