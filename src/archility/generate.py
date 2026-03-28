"""Architecture scaffolding helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import re
from xml.sax.saxutils import escape

from .audit import detect_source_roots
from .render import build_render_steps, package_repo_root, run_render_steps

EXCLUDED_TOP_LEVEL_DIRS = {
    ".git",
    ".github",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "docs",
    "node_modules",
    "tools",
    "venv",
}

COURSE_DIRECTORY_PATTERN = re.compile(r"^([A-Z]{3})\d{3}(?:-.+)?$")
COMMON_DELIVERABLE_FAMILIES = [
    "HW/",
    "Project/",
    "Assignments/",
    "Exam/Exams/",
    "Final/",
    "Notes/",
    "Labs/",
    "Presentations/",
    "Deliverables/",
]


@dataclass(slots=True)
class GenerateResult:
    path: str
    created: list[str]
    skipped: list[str]
    rendered: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def top_level_content_dirs(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.iterdir(), key=lambda entry: entry.name)
        if path.is_dir() and path.name not in EXCLUDED_TOP_LEVEL_DIRS and not path.name.startswith(".")
    ]


def detect_course_taxonomy(root: Path) -> dict[str, list[str]] | None:
    candidates = top_level_content_dirs(root)
    if len(candidates) < 8:
        return None

    groups: dict[str, list[str]] = {}
    for path in candidates:
        match = COURSE_DIRECTORY_PATTERN.match(path.name)
        if match is None:
            return None
        groups.setdefault(match.group(1), []).append(path.name)
    return dict(sorted(groups.items()))


def detect_focus_roots(root: Path) -> list[str]:
    source_roots = detect_source_roots(root)
    if source_roots:
        return source_roots

    candidates = [path.name for path in top_level_content_dirs(root)]
    if candidates:
        return candidates[:5]
    return ["repository root"]


def blueprint_structure_lines(repo_root: Path) -> list[str]:
    course_groups = detect_course_taxonomy(repo_root)
    if course_groups is None:
        focus_roots = detect_focus_roots(repo_root)
        focus_root_lines = "\n".join(f"- `{root_name}/`" for root_name in focus_roots)
        return [
            "## Current Focus Roots",
            "",
            focus_root_lines,
        ]

    lines = [
        "## Current Course Taxonomy",
        "",
        f"- This archive groups {sum(len(courses) for courses in course_groups.values())} course directories under {len(course_groups)} subject prefixes.",
        "- Subject prefixes are the primary navigation layer for the repository.",
        "",
    ]
    for prefix, courses in course_groups.items():
        lines.append(f"### `{prefix}/` — {len(courses)} {_course_directory_label(len(courses))}")
        lines.append("")
        for course_name in courses:
            lines.append(f"- `{course_name}/`")
        lines.append("")
    lines.extend(
        [
            "## Common Nested Deliverable Families",
            "",
            "- `HW/`, `Project/`, `Assignments/`, `Exam/` or `Exams/`, `Final/`, `Notes/`, `Labs/`, `Presentations/`, and `Deliverables/` appear under individual course directories depending on course format.",
        ]
    )
    return lines


def _course_taxonomy_summary(course_groups: dict[str, list[str]]) -> str:
    total_courses = sum(len(courses) for courses in course_groups.values())
    subject_area_label = "subject area" if len(course_groups) == 1 else "subject areas"
    course_directory_label = "course directory" if total_courses == 1 else "course directories"
    return f"Course Taxonomy\\n{len(course_groups)} {subject_area_label} / {total_courses} {course_directory_label}"


def _deliverable_families_text(separator: str) -> str:
    joined = separator.join(COMMON_DELIVERABLE_FAMILIES)
    return f"Common Nested Deliverable Families{separator}{joined}"


def _course_directory_label(count: int) -> str:
    return "course directory" if count == 1 else "course directories"


def relative_archility_path(repo_root: Path, *, archility_root: Path | None = None) -> str:
    tool_root = (archility_root or package_repo_root()).resolve()
    return os.path.relpath(tool_root, repo_root)


def relative_repo_from_archility(repo_root: Path, *, archility_root: Path | None = None) -> str:
    tool_root = (archility_root or package_repo_root()).resolve()
    return os.path.relpath(repo_root, tool_root)


def architecture_file_paths(repo_root: Path) -> dict[str, Path]:
    return {
        "blueprint": repo_root / "docs" / "contributor-architecture-blueprint.md",
        "plantuml": repo_root / "docs" / "diagrams" / "repo-architecture.puml",
        "drawio": repo_root / "docs" / "diagrams" / "repo-architecture.drawio",
    }


def build_blueprint_text(repo_root: Path, *, archility_root: Path | None = None) -> str:
    rel_archility = relative_archility_path(repo_root, archility_root=archility_root)
    rel_repo = relative_repo_from_archility(repo_root, archility_root=archility_root)
    structure_lines = blueprint_structure_lines(repo_root)
    workflow_line = (
        "- `.github/workflows/` is the standard automation directory for repo validation."
        if (repo_root / ".github" / "workflows").exists()
        else "- No `.github/workflows/` directory is present yet."
    )
    return "\n".join(
        [
            "# Contributor Architecture Blueprint",
            "",
            f"This document is the starter architecture map for `{repo_root.name}`.",
            "Keep it aligned with the real repository layout and execution flow as the repo evolves.",
            "",
            "## Standard Architecture Assets",
            "",
            "- PlantUML source: `docs/diagrams/repo-architecture.puml`",
            "- Draw.io source: `docs/diagrams/repo-architecture.drawio`",
            "- Expected renders after `archility render`:",
            "  - `docs/diagrams/repo-architecture.puml.svg`",
            "  - `docs/diagrams/repo-architecture.puml.png`",
            "  - `docs/diagrams/repo-architecture.drawio.svg`",
            "  - `docs/diagrams/repo-architecture.drawio.png`",
            f"- Shared toolchain owner: `{rel_archility}` from this repo",
            "",
            "## Architecture Authoring Paths",
            "",
            "- Programmatic path: `archility generate` builds this starter strictly from repository code and folder markers. This path is deterministic.",
            "- Agentic path: an AI agent should inspect the full repository, understand the real execution and dependency boundaries, then rewrite or extend this starter into a repo-specific architecture. This path is intentionally non-deterministic.",
            "- Keep the standard filenames and folder layout even when the agentic path replaces the starter content with a more unique architecture.",
            "",
            "## Regeneration",
            "",
            "```bash",
            f"cd {rel_archility}",
            f"PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m archility generate {rel_repo}",
            f"PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m archility render {rel_repo}",
            "```",
            "",
            *structure_lines,
            "",
            "## Automation",
            "",
            workflow_line,
            "",
            "## Contributor Notes",
            "",
            "- Treat this file and the paired `docs/diagrams/` sources as the default architecture handoff surface.",
            "- Expand this starter blueprint with repo-specific flow, dependency, and deployment details when the repository grows beyond the generated baseline.",
            "- Update the blueprint and diagram sources together when folder structure, execution flow, or integration boundaries change.",
        ]
    )


def _alias_for(index: int) -> str:
    return f"root_{index}"


def build_plantuml_text(repo_root: Path) -> str:
    repo_name = repo_root.name
    focus_roots = detect_focus_roots(repo_root)
    course_groups = detect_course_taxonomy(repo_root)
    workflow_label = ".github/workflows/" if (repo_root / ".github" / "workflows").exists() else "workflow coverage not added yet"
    lines = [
        "@startuml",
        f"title {repo_name} Repository Architecture Starter",
        "!pragma layout smetana",
        "' Deterministic starter generated from repository structure by archility.",
        "skinparam shadowing false",
        "skinparam defaultFontName Monospace",
        "skinparam packageStyle rectangle",
        "skinparam linetype ortho",
        "",
        'actor Contributor as contributor',
        'rectangle "README.md\\nAGENTS.md\\nLESSONSLEARNED.md" as governance #E2E8F0',
        'rectangle "docs/contributor-architecture-blueprint.md" as blueprint #DBEAFE',
        'rectangle "docs/diagrams/repo-architecture.puml" as plantuml_source #FCE7F3',
        'rectangle "docs/diagrams/repo-architecture.drawio" as drawio_source #FCE7F3',
        f'rectangle "{workflow_label}" as workflows #DCFCE7',
    ]

    if course_groups is not None:
        lines.extend(
            [
                f'rectangle "{_course_taxonomy_summary(course_groups)}" as taxonomy_summary #E0F2FE',
                f'rectangle "{_deliverable_families_text("\\n")}" as nested_patterns #DCFCE7',
                'package "Subject Areas" #F8FAFC {',
            ]
        )
        for prefix, courses in course_groups.items():
            lines.append(f'  package "{prefix} ({len(courses)} {"course" if len(courses) == 1 else "courses"})" #EEF7FF {{')
            for index, course_name in enumerate(courses, start=1):
                lines.append(f'    folder "{course_name}/" as {prefix.lower()}_{index} #FFFFFF')
            lines.append("  }")
        lines.extend(
            [
                "}",
                "",
                "contributor --> governance",
                "governance --> blueprint",
                "blueprint --> plantuml_source",
                "blueprint --> drawio_source",
                "blueprint --> taxonomy_summary",
                "plantuml_source --> taxonomy_summary",
                "drawio_source --> taxonomy_summary",
                "workflows --> taxonomy_summary",
                "taxonomy_summary --> nested_patterns",
            ]
        )
    else:
        lines.append('package "Implementation / Content Roots" #F8FAFC {')
        for index, root_name in enumerate(focus_roots, start=1):
            lines.append(f'  rectangle "{root_name}/" as {_alias_for(index)} #E0F2FE')
        lines.extend(
            [
                "}",
                "",
                "contributor --> governance",
                "governance --> blueprint",
                "blueprint --> plantuml_source",
                "blueprint --> drawio_source",
            ]
        )
        for index, _ in enumerate(focus_roots, start=1):
            alias = _alias_for(index)
            lines.append(f"plantuml_source --> {alias}")
            lines.append(f"drawio_source --> {alias}")
            lines.append(f"workflows --> {alias}")
    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def _drawio_header_cell(repo_name: str) -> str:
    return (
        '        <mxCell id="2" value="'
        + escape(f"{repo_name} Architecture Starter", {"\"": "&quot;"})
        + '&#10;(generated by archility)" '
        + 'style="rounded=0;whiteSpace=wrap;html=0;fillColor=#1F2937;strokeColor=#111827;fontColor=#FFFFFF;fontSize=26;fontStyle=1;align=center;verticalAlign=middle;spacing=10;" vertex="1" parent="1">\n'
        + '          <mxGeometry x="40" y="20" width="1520" height="80" as="geometry" />\n'
        + "        </mxCell>"
    )


def _drawio_value(text: str) -> str:
    return escape(text, {'"': "&quot;"}).replace("\n", "&#10;")


def _drawio_vertex(cell_id: int, value: str, style: str, x: int, y: int, width: int, height: int) -> str:
    return "\n".join(
        [
            f'        <mxCell id="{cell_id}" value="{_drawio_value(value)}" style="{style}" vertex="1" parent="1">',
            f'          <mxGeometry x="{x}" y="{y}" width="{width}" height="{height}" as="geometry" />',
            "        </mxCell>",
        ]
    )


def _drawio_edge(cell_id: int, source: int, target: int) -> str:
    return "\n".join(
        [
            f'        <mxCell id="{cell_id}" style="rounded=0;html=0;strokeColor=#1F2937;edgeStyle=orthogonalEdgeStyle;orthogonalLoop=1;jettySize=12;endArrow=classic;endFill=1;endSize=10;strokeWidth=2;" edge="1" parent="1" source="{source}" target="{target}">',
            '          <mxGeometry relative="1" as="geometry" />',
            "        </mxCell>",
        ]
    )


def build_drawio_text(repo_root: Path) -> str:
    repo_name = repo_root.name
    focus_roots = detect_focus_roots(repo_root)
    course_groups = detect_course_taxonomy(repo_root)
    workflow_label = ".github/workflows/" if (repo_root / ".github" / "workflows").exists() else "workflow coverage not added yet"

    cells = [
        _drawio_header_cell(repo_name),
        _drawio_vertex(
            10,
            "Contributor\nmaintains repo shape",
            "rounded=1;whiteSpace=wrap;html=0;fillColor=#FCE7F3;strokeColor=#DB2777;fontColor=#111827;fontSize=18;align=center;verticalAlign=middle;spacing=8;",
            80,
            150,
            240,
            90,
        ),
        _drawio_vertex(
            20,
            "Governance Surface\nREADME.md\nAGENTS.md\nLESSONSLEARNED.md",
            "rounded=1;whiteSpace=wrap;html=0;fillColor=#E2E8F0;strokeColor=#64748B;fontColor=#111827;fontSize=18;align=center;verticalAlign=middle;spacing=8;",
            380,
            150,
            300,
            120,
        ),
        _drawio_vertex(
            30,
            "Blueprint\n docs/contributor-architecture-blueprint.md",
            "rounded=1;whiteSpace=wrap;html=0;fillColor=#DBEAFE;strokeColor=#2563EB;fontColor=#111827;fontSize=18;align=center;verticalAlign=middle;spacing=8;",
            760,
            150,
            330,
            90,
        ),
        _drawio_vertex(
            40,
            "Diagram Sources\nrepo-architecture.puml\nrepo-architecture.drawio",
            "rounded=1;whiteSpace=wrap;html=0;fillColor=#FCE7F3;strokeColor=#DB2777;fontColor=#111827;fontSize=18;align=center;verticalAlign=middle;spacing=8;",
            1170,
            150,
            330,
            110,
        ),
        _drawio_vertex(
            50,
            f"Automation\n{workflow_label}",
            "rounded=1;whiteSpace=wrap;html=0;fillColor=#DCFCE7;strokeColor=#16A34A;fontColor=#111827;fontSize=18;align=center;verticalAlign=middle;spacing=8;",
            1170,
            310,
            330,
            90,
        ),
    ]

    edges = [_drawio_edge(500, 10, 20), _drawio_edge(501, 20, 30), _drawio_edge(502, 30, 40)]
    page_height = 1200

    if course_groups is not None:
        cells.extend(
            [
                _drawio_vertex(
                    60,
                    _course_taxonomy_summary(course_groups).replace("\\n", "\n"),
                    "rounded=1;whiteSpace=wrap;html=0;fillColor=#E0F2FE;strokeColor=#0284C7;fontColor=#111827;fontSize=18;align=center;verticalAlign=middle;spacing=8;",
                    80,
                    470,
                    560,
                    110,
                ),
                _drawio_vertex(
                    70,
                    _deliverable_families_text("\n"),
                    "rounded=1;whiteSpace=wrap;html=0;fillColor=#DCFCE7;strokeColor=#16A34A;fontColor=#111827;fontSize=18;align=center;verticalAlign=middle;spacing=8;",
                    720,
                    470,
                    780,
                    110,
                ),
            ]
        )
        edges.extend(
            [
                _drawio_edge(503, 40, 60),
                _drawio_edge(504, 50, 60),
                _drawio_edge(505, 60, 70),
            ]
        )

        group_items = list(course_groups.items())
        columns = 3
        box_width = 420
        x_base = 80
        x_step = 480
        y_base = 660
        y_gap = 60
        row_heights: dict[int, int] = {}
        for index, (_, courses) in enumerate(group_items):
            row = index // columns
            line_count = 2 + len(courses)
            row_heights[row] = max(row_heights.get(row, 0), max(150, 50 + line_count * 18))

        row_offsets: dict[int, int] = {}
        next_row_y = y_base
        for row in range((len(group_items) + columns - 1) // columns):
            row_offsets[row] = next_row_y
            next_row_y += row_heights[row] + y_gap

        for index, (prefix, courses) in enumerate(group_items):
            row = index // columns
            column = index % columns
            cell_id = 100 + index
            value = "\n".join([f"Subject Area", f'{prefix} ({len(courses)} {"course" if len(courses) == 1 else "courses"})', *courses])
            cells.append(
                _drawio_vertex(
                    cell_id,
                    value,
                    "rounded=1;whiteSpace=wrap;html=0;fillColor=#EEF7FF;strokeColor=#0284C7;fontColor=#111827;fontSize=16;align=left;verticalAlign=top;spacing=10;",
                    x_base + column * x_step,
                    row_offsets[row],
                    box_width,
                    max(150, 50 + (2 + len(courses)) * 18),
                )
            )
            edges.append(_drawio_edge(520 + index, 60, cell_id))
        page_height = next_row_y + 80
    else:
        root_ids: list[int] = []
        next_id = 100
        root_y = 470
        for index, root_name in enumerate(focus_roots):
            cell_id = next_id + index
            root_ids.append(cell_id)
            cells.append(
                _drawio_vertex(
                    cell_id,
                    f"Focus Root\n{root_name}/",
                    "rounded=1;whiteSpace=wrap;html=0;fillColor=#E0F2FE;strokeColor=#0284C7;fontColor=#111827;fontSize=18;align=center;verticalAlign=middle;spacing=8;",
                    220 + (index % 3) * 420,
                    root_y + (index // 3) * 140,
                    320,
                    90,
                )
            )
        for offset, root_id in enumerate(root_ids, start=1):
            edges.append(_drawio_edge(510 + offset, 40, root_id))
            edges.append(_drawio_edge(520 + offset, 50, root_id))

    xml_lines = [
        "<?xml version='1.0' encoding='utf-8'?>",
        '<mxfile host="app.diagrams.net" modified="generated-by-archility" agent="Codex GPT-5" version="24.7.17" type="device" compressed="false">',
        '  <diagram id="repo-architecture" name="Repo Architecture">',
        f'    <mxGraphModel dx="1600" dy="1000" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" pageHeight="{page_height}" math="0" shadow="0" keepEdgesInForeground="1" keepEdgesInBackground="0">',
        "      <root>",
        '        <mxCell id="0" />',
        '        <mxCell id="1" parent="0" />',
    ]
    xml_lines.extend(cells)
    xml_lines.extend(edges)
    xml_lines.extend(
        [
            "      </root>",
            "    </mxGraphModel>",
            "  </diagram>",
            "</mxfile>",
            "",
        ]
    )
    return "\n".join(xml_lines)


def write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def generate_repo(
    repo_path: str | Path,
    *,
    archility_root: Path | None = None,
    render: bool = False,
) -> GenerateResult:
    repo_root = Path(repo_path).resolve()
    if not repo_root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_root}")
    if not repo_root.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {repo_root}")

    paths = architecture_file_paths(repo_root)
    created: list[str] = []
    skipped: list[str] = []

    file_builders = {
        "blueprint": lambda: build_blueprint_text(repo_root, archility_root=archility_root),
        "plantuml": lambda: build_plantuml_text(repo_root),
        "drawio": lambda: build_drawio_text(repo_root),
    }

    for key, path in paths.items():
        if write_if_missing(path, file_builders[key]()):
            created.append(str(path.relative_to(repo_root)))
        else:
            skipped.append(str(path.relative_to(repo_root)))

    rendered: list[str] = []
    if render:
        steps = build_render_steps(repo_root, archility_root=archility_root)
        if steps:
            run_render_steps(steps)
            rendered = [str(Path(step.output).relative_to(repo_root)) for step in steps]
    return GenerateResult(
        path=str(repo_root),
        created=created,
        skipped=skipped,
        rendered=rendered,
    )


def generate_repositories(
    paths: list[str | Path],
    *,
    archility_root: Path | None = None,
    render: bool = False,
) -> list[GenerateResult]:
    return [
        generate_repo(path, archility_root=archility_root, render=render)
        for path in paths
    ]


def format_generate_report(results: list[GenerateResult]) -> str:
    lines: list[str] = []
    for result in results:
        lines.append(f"repo: {result.path}")
        lines.append(f"  created: {len(result.created)}")
        for item in result.created:
            lines.append(f"    - {item}")
        lines.append(f"  skipped_existing: {len(result.skipped)}")
        for item in result.skipped:
            lines.append(f"    - {item}")
        lines.append(f"  rendered: {len(result.rendered)}")
        for item in result.rendered:
            lines.append(f"    - {item}")
    return "\n".join(lines)
