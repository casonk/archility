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
PYTHON_MARKER_FILES = ("pyproject.toml", "setup.py", "setup.cfg")
PYTHON_SOURCE_ROOT_DIRS = ("src", "app", "services", "scripts")
PYTHON_EXCLUDED_DIRS = {
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
SOURCE_DIAGRAM_SUFFIXES = {
    ".drawio",
    ".puml",
    ".plantuml",
    ".mmd",
    ".mermaid",
}
RENDER_ARTIFACT_SUFFIXES = {
    ".png",
    ".svg",
}
DIAGRAM_SUFFIXES = SOURCE_DIAGRAM_SUFFIXES | RENDER_ARTIFACT_SUFFIXES
TOOLCHAIN_SOURCE_SUFFIXES = {
    "plantuml": {".puml", ".plantuml"},
    "drawio": {".drawio"},
    "mermaid": {".mmd", ".mermaid"},
}
TOOLCHAIN_HINT_PATTERNS = {
    "plantuml": ("plantuml",),
    "drawio": ("draw.io", "drawio", "diagrams.net"),
    "pydeps": ("pydeps",),
    "pyreverse": ("pyreverse",),
    "inkscape": ("inkscape",),
    "mermaid": ("mermaid",),
}
TOOLCHAIN_ORDER = ("plantuml", "drawio", "pydeps", "pyreverse", "inkscape", "mermaid")
TOOLCHAIN_HINT_FILES = (
    Path("README.md"),
    Path("AGENTS.md"),
    Path("setup.sh"),
    Path("docs/contributor-architecture-blueprint.md"),
)


@dataclass(slots=True)
class RepoAudit:
    path: str
    code_like: bool
    has_agents: bool
    has_lessons: bool
    has_blueprint: bool
    workflow_count: int
    diagram_count: int
    diagram_source_count: int
    render_artifact_count: int
    diagram_formats: list[str]
    toolchains: list[str]
    source_roots: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def detect_code_like(root: Path) -> bool:
    markers = CODE_MARKER_FILES + CODE_MARKER_DIRS
    return any((root / marker).exists() for marker in markers)


def detect_source_roots(root: Path) -> list[str]:
    return [name for name in CODE_MARKER_DIRS if (root / name).exists()]


def _should_skip_python_scan(path: Path) -> bool:
    return path.name.startswith(".") or path.name in PYTHON_EXCLUDED_DIRS


def _is_python_package(path: Path) -> bool:
    return path.is_dir() and (path / "__init__.py").is_file()


def _has_python_descendants(path: Path) -> bool:
    if path.is_file():
        return path.suffix == ".py"
    if not path.is_dir():
        return False

    for child in sorted(path.iterdir(), key=lambda entry: entry.name):
        if _should_skip_python_scan(child):
            continue
        if child.is_file() and child.suffix == ".py":
            return True
        if child.is_dir() and (_is_python_package(child) or _has_python_descendants(child)):
            return True
    return False


def _direct_python_targets(container: Path) -> list[Path]:
    if container.is_file():
        return [container] if container.suffix == ".py" else []
    if not container.is_dir():
        return []

    targets: list[Path] = []
    for child in sorted(container.iterdir(), key=lambda entry: entry.name):
        if _should_skip_python_scan(child):
            continue
        if _is_python_package(child) or (child.is_file() and child.suffix == ".py"):
            targets.append(child)
    return targets


def collect_python_diagram_targets(root: Path) -> list[Path]:
    containers: list[Path] = []
    for name in PYTHON_SOURCE_ROOT_DIRS:
        candidate = root / name
        if candidate.is_dir() and _has_python_descendants(candidate):
            containers.append(candidate)

    root_targets = _direct_python_targets(root)
    if root_targets or any((root / marker).exists() for marker in PYTHON_MARKER_FILES):
        containers.append(root)

    seen: set[Path] = set()
    targets: list[Path] = []
    for container in containers:
        for target in _direct_python_targets(container):
            resolved = target.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            targets.append(resolved)
    return targets


def count_workflows(root: Path) -> int:
    workflow_dir = root / '.github' / 'workflows'
    if not workflow_dir.exists():
        return 0
    return sum(1 for path in workflow_dir.iterdir() if path.is_file())


def collect_diagram_files(root: Path) -> list[Path]:
    docs_dir = root / 'docs'
    if not docs_dir.exists():
        return []
    return sorted(
        (
            path
            for path in docs_dir.rglob('*')
            if path.is_file() and path.suffix.lower() in DIAGRAM_SUFFIXES
        ),
        key=lambda path: str(path.relative_to(root)),
    )


def detect_diagram_formats(diagram_files: list[Path]) -> list[str]:
    return sorted({path.suffix.lower() for path in diagram_files})


def count_source_diagrams(diagram_files: list[Path]) -> int:
    return sum(1 for path in diagram_files if path.suffix.lower() in SOURCE_DIAGRAM_SUFFIXES)


def count_render_artifacts(diagram_files: list[Path]) -> int:
    return sum(1 for path in diagram_files if path.suffix.lower() in RENDER_ARTIFACT_SUFFIXES)


def iter_toolchain_hint_files(root: Path) -> list[Path]:
    hint_files = [root / relative_path for relative_path in TOOLCHAIN_HINT_FILES]
    workflow_dir = root / '.github' / 'workflows'
    if workflow_dir.exists():
        hint_files.extend(path for path in workflow_dir.iterdir() if path.is_file())
    return [path for path in hint_files if path.is_file()]


def read_search_text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8').lower()
    except UnicodeDecodeError:
        return path.read_text(encoding='utf-8', errors='ignore').lower()


def detect_toolchains(root: Path, diagram_files: list[Path]) -> list[str]:
    detected: set[str] = set()
    diagram_formats = set(detect_diagram_formats(diagram_files))
    for toolchain, suffixes in TOOLCHAIN_SOURCE_SUFFIXES.items():
        if diagram_formats & suffixes:
            detected.add(toolchain)

    for path in iter_toolchain_hint_files(root):
        text = read_search_text(path)
        for toolchain, patterns in TOOLCHAIN_HINT_PATTERNS.items():
            if any(pattern in text for pattern in patterns):
                detected.add(toolchain)

    return [toolchain for toolchain in TOOLCHAIN_ORDER if toolchain in detected]


def build_recommendations(
    *,
    code_like: bool,
    has_agents: bool,
    has_lessons: bool,
    has_blueprint: bool,
    workflow_count: int,
    diagram_count: int,
    toolchains: list[str],
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
        recommendations.append(
            'Consider adding docs/diagrams/ artifacts for non-trivial flows. The current portfolio pattern uses PlantUML (.puml) and/or Draw.io (.drawio) sources plus rendered PNG/SVG artifacts.'
        )
    if diagram_count > 0 and not toolchains:
        recommendations.append(
            'Document the local architecture-diagram toolchain in README.md or docs/contributor-architecture-blueprint.md so contributors can regenerate the artifacts.'
        )
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
    diagram_files = collect_diagram_files(root)
    diagram_count = len(diagram_files)
    diagram_source_count = count_source_diagrams(diagram_files)
    render_artifact_count = count_render_artifacts(diagram_files)
    diagram_formats = detect_diagram_formats(diagram_files)
    toolchains = detect_toolchains(root, diagram_files)
    source_roots = detect_source_roots(root)
    recommendations = build_recommendations(
        code_like=code_like,
        has_agents=has_agents,
        has_lessons=has_lessons,
        has_blueprint=has_blueprint,
        workflow_count=workflow_count,
        diagram_count=diagram_count,
        toolchains=toolchains,
    )
    return RepoAudit(
        path=str(root),
        code_like=code_like,
        has_agents=has_agents,
        has_lessons=has_lessons,
        has_blueprint=has_blueprint,
        workflow_count=workflow_count,
        diagram_count=diagram_count,
        diagram_source_count=diagram_source_count,
        render_artifact_count=render_artifact_count,
        diagram_formats=diagram_formats,
        toolchains=toolchains,
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
        lines.append(f'  diagram_sources: {result.diagram_source_count}')
        lines.append(f'  diagram_renders: {result.render_artifact_count}')
        lines.append(
            '  diagram_formats: '
            + (', '.join(result.diagram_formats) if result.diagram_formats else 'none')
        )
        lines.append('  toolchains: ' + (', '.join(result.toolchains) if result.toolchains else 'none'))
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
