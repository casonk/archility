"""Repository architecture audit helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

CODE_MARKER_FILES = (
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "Cargo.toml",
    "go.mod",
)
CODE_MARKER_DIRS = ("src", "tests", "test", "scripts", "services", "app")
DIAGRAM_SUFFIXES = {
    ".drawio",
    ".puml",
    ".plantuml",
    ".mmd",
    ".mermaid",
    ".svg",
    ".png",
}


@dataclass(slots=True)
class RepoAudit:
    path: str
    code_like: bool
    has_agents: bool
    has_lessons: bool
    has_blueprint: bool
    workflow_count: int
    diagram_count: int
    source_roots: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def detect_code_like(root: Path) -> bool:
    markers = CODE_MARKER_FILES + CODE_MARKER_DIRS
    return any((root / marker).exists() for marker in markers)


def detect_source_roots(root: Path) -> list[str]:
    return [name for name in CODE_MARKER_DIRS if (root / name).exists()]


def count_workflows(root: Path) -> int:
    workflow_dir = root / '.github' / 'workflows'
    if not workflow_dir.exists():
        return 0
    return sum(1 for path in workflow_dir.iterdir() if path.is_file())


def count_diagrams(root: Path) -> int:
    docs_dir = root / 'docs'
    if not docs_dir.exists():
        return 0
    return sum(
        1
        for path in docs_dir.rglob('*')
        if path.is_file() and path.suffix.lower() in DIAGRAM_SUFFIXES
    )


def build_recommendations(
    *,
    code_like: bool,
    has_agents: bool,
    has_lessons: bool,
    has_blueprint: bool,
    workflow_count: int,
    diagram_count: int,
) -> list[str]:
    recommendations: list[str] = []
    if not has_agents:
        recommendations.append('Add AGENTS.md with repo-specific operating guidance.')
    if not has_lessons:
        recommendations.append('Add repo-root LESSONSLEARNED.md for durable lessons.')
    if code_like and not has_blueprint:
        recommendations.append(
            'Add docs/contributor-architecture-blueprint.md for contributor-facing architecture context.'
        )
    if code_like and workflow_count == 0:
        recommendations.append('Add at least one .github/workflows/ check for code-focused validation.')
    if code_like and diagram_count == 0:
        recommendations.append('Consider adding docs/diagrams/ artifacts for non-trivial flows.')
    return recommendations


def audit_repo(path: str | Path) -> RepoAudit:
    root = Path(path).resolve()
    if not root.exists():
        raise FileNotFoundError(f'Repository path does not exist: {root}')
    if not root.is_dir():
        raise NotADirectoryError(f'Repository path is not a directory: {root}')

    code_like = detect_code_like(root)
    has_agents = (root / 'AGENTS.md').is_file()
    has_lessons = (root / 'LESSONSLEARNED.md').is_file()
    has_blueprint = (root / 'docs' / 'contributor-architecture-blueprint.md').is_file()
    workflow_count = count_workflows(root)
    diagram_count = count_diagrams(root)
    source_roots = detect_source_roots(root)
    recommendations = build_recommendations(
        code_like=code_like,
        has_agents=has_agents,
        has_lessons=has_lessons,
        has_blueprint=has_blueprint,
        workflow_count=workflow_count,
        diagram_count=diagram_count,
    )
    return RepoAudit(
        path=str(root),
        code_like=code_like,
        has_agents=has_agents,
        has_lessons=has_lessons,
        has_blueprint=has_blueprint,
        workflow_count=workflow_count,
        diagram_count=diagram_count,
        source_roots=source_roots,
        recommendations=recommendations,
    )


def audit_repositories(paths: list[str | Path]) -> list[RepoAudit]:
    return [audit_repo(path) for path in paths]


def format_text_report(results: list[RepoAudit]) -> str:
    lines: list[str] = []
    for result in results:
        lines.append(f'repo: {result.path}')
        lines.append(f'  code_like: {"yes" if result.code_like else "no"}')
        lines.append(f'  agents: {"yes" if result.has_agents else "no"}')
        lines.append(f'  lessons: {"yes" if result.has_lessons else "no"}')
        lines.append(f'  blueprint: {"yes" if result.has_blueprint else "no"}')
        lines.append(f'  workflows: {result.workflow_count}')
        lines.append(f'  diagrams: {result.diagram_count}')
        lines.append(
            '  source_roots: ' + (', '.join(result.source_roots) if result.source_roots else 'none')
        )
        if result.recommendations:
            lines.append('  recommendations:')
            for recommendation in result.recommendations:
                lines.append(f'    - {recommendation}')
        else:
            lines.append('  recommendations: none')
    return '\n'.join(lines)
