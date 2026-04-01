"""Shared architecture rendering helpers."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import io
from pathlib import Path
import re
import shlex
import subprocess
from typing import Callable
from xml.etree import ElementTree

from .audit import (
    collect_python_diagram_targets,
    collect_shell_diagram_targets,
    collect_sql_diagram_targets,
    collect_tooling_diagram_targets,
)

PLANTUML_SUFFIXES = (".puml", ".plantuml")
DRAWIO_SUFFIXES = (".drawio",)
MANAGED_PYREVERSE_FILENAMES = {"python-classes.puml", "python-packages.puml"}
MANAGED_SUPPLEMENTAL_FILENAMES = {
    "database-schema.puml",
    "shell-call-graph.puml",
    "tooling-integrations.puml",
}
PYDEPS_PREFIX = "python-import-deps-"
SHELL_GRAPH_FILENAME = "shell-call-graph.puml"
DATABASE_GRAPH_FILENAME = "database-schema.puml"
TOOLING_GRAPH_FILENAME = "tooling-integrations.puml"
NORMALIZED_TEXT_OUTPUT_SUFFIXES = {".svg"}
DRAWIO_EDGE_STYLE_DEFAULTS = (
    ("jumpStyle", "arc"),
    ("jumpSize", "10"),
)
LOW_SIGNAL_PYREVERSE_CLASS_THRESHOLD = 1
_PANEL_MIN_HEADER_GAP = 50.0
_PANEL_MIN_ROW_GAP = 60.0
_PANEL_MIN_FOOTER_GAP = 40.0
_PANEL_NOTE_HEIGHT_THRESHOLD = 80.0
_PANEL_MIN_NOTE_GAP = 25.0
RunCommand = Callable[[list[str], str | None], None]
RenderAction = Callable[[], None]
SHELL_INTERPRETERS = {"bash", "sh", "zsh", "ksh"}
SHELL_CONTROL_KEYWORDS = {
    "{",
    "}",
    "if",
    "then",
    "elif",
    "else",
    "fi",
    "for",
    "while",
    "until",
    "do",
    "done",
    "case",
    "esac",
    "function",
    "select",
    "in",
}
SHELL_BUILTINS = {
    ".",
    ":",
    "[",
    "[[",
    "alias",
    "bg",
    "break",
    "cd",
    "continue",
    "dirs",
    "echo",
    "eval",
    "exec",
    "exit",
    "export",
    "false",
    "fg",
    "getopts",
    "hash",
    "jobs",
    "kill",
    "local",
    "popd",
    "printf",
    "pushd",
    "pwd",
    "read",
    "readonly",
    "return",
    "set",
    "shift",
    "source",
    "test",
    "times",
    "trap",
    "true",
    "type",
    "typeset",
    "ulimit",
    "umask",
    "unalias",
    "unset",
    "wait",
}
COMMAND_WRAPPERS = {"builtin", "command", "env", "nohup", "sudo", "time"}
TOOL_WRAPPER_DIR_PARTS = ("tools", "bin")
ENV_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
CREATE_TABLE_PATTERN = re.compile(
    r"\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?([A-Za-z0-9_.`\"[\]-]+)",
    re.IGNORECASE,
)
ALTER_TABLE_PATTERN = re.compile(
    r"\balter\s+table\s+(?:only\s+)?([A-Za-z0-9_.`\"[\]-]+)",
    re.IGNORECASE,
)
REFERENCES_PATTERN = re.compile(
    r"\breferences\s+([A-Za-z0-9_.`\"[\]-]+)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class RenderStep:
    tool: str
    source: str
    outputs: tuple[str, ...]
    produced_outputs: tuple[str, ...]
    command: list[str]
    cwd: str | None = None
    internal_action: RenderAction | None = None

    @property
    def output(self) -> str:
        return self.outputs[0]

    @property
    def produced_output(self) -> str:
        return self.produced_outputs[0]

    @property
    def is_internal(self) -> bool:
        return self.internal_action is not None


@dataclass(frozen=True, slots=True)
class DrawioCellBounds:
    x: float
    y: float
    width: float
    height: float

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def mid_x(self) -> float:
        return self.x + self.width / 2

    @property
    def mid_y(self) -> float:
        return self.y + self.height / 2


@dataclass(slots=True)
class PythonDiagramPlan:
    repo_root: Path
    targets: tuple[Path, ...]
    pydeps_outputs: tuple[Path, ...]
    pyreverse_sources: tuple[Path, ...]

    @property
    def project_name(self) -> str:
        return _safe_project_name(self.repo_root.name)

    @property
    def pyreverse_render_outputs(self) -> tuple[Path, ...]:
        outputs: list[Path] = []
        for source, produced_stem in zip(
            self.pyreverse_sources,
            self.pyreverse_produced_stems,
            strict=True,
        ):
            outputs.extend(
                [
                    source.parent / f"{produced_stem}.svg",
                    source.parent / f"{produced_stem}.png",
                ]
            )
        return tuple(outputs)

    @property
    def pyreverse_produced_stems(self) -> tuple[str, ...]:
        stems = [f"classes_{self.project_name}"]
        if len(self.pyreverse_sources) > 1:
            stems.append(f"packages_{self.project_name}")
        return tuple(stems)


@dataclass(frozen=True, slots=True)
class PythonModuleInfo:
    name: str
    path: Path
    is_package: bool
    class_count: int
    function_count: int


@dataclass(slots=True)
class ShellDiagramPlan:
    repo_root: Path
    targets: tuple[Path, ...]
    source: Path


@dataclass(slots=True)
class DatabaseDiagramPlan:
    repo_root: Path
    targets: tuple[Path, ...]
    source: Path


@dataclass(slots=True)
class ToolingDiagramPlan:
    repo_root: Path
    targets: tuple[Path, ...]
    source: Path


def package_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def diagram_root(repo_path: str | Path) -> Path:
    return Path(repo_path).resolve() / "docs" / "diagrams"


def build_python_diagram_plan(repo_path: str | Path) -> PythonDiagramPlan | None:
    repo_root = Path(repo_path).resolve()
    targets = tuple(collect_python_diagram_targets(repo_root))
    if not targets:
        return None

    root = diagram_root(repo_root)
    pydeps_outputs = tuple(
        root / f"{PYDEPS_PREFIX}{_python_target_label(repo_root, target)}.svg"
        for target in targets
    )
    pyreverse_sources: list[Path] = [root / "python-classes.puml"]
    if len(targets) > 1 or any(_is_package_target(target) for target in targets):
        pyreverse_sources.append(root / "python-packages.puml")
    return PythonDiagramPlan(
        repo_root=repo_root,
        targets=targets,
        pydeps_outputs=pydeps_outputs,
        pyreverse_sources=tuple(pyreverse_sources),
    )


def build_shell_diagram_plan(repo_path: str | Path) -> ShellDiagramPlan | None:
    repo_root = Path(repo_path).resolve()
    targets = tuple(collect_shell_diagram_targets(repo_root))
    if not targets:
        return None
    return ShellDiagramPlan(
        repo_root=repo_root,
        targets=targets,
        source=diagram_root(repo_root) / SHELL_GRAPH_FILENAME,
    )


def build_database_diagram_plan(repo_path: str | Path) -> DatabaseDiagramPlan | None:
    repo_root = Path(repo_path).resolve()
    targets = tuple(collect_sql_diagram_targets(repo_root))
    if not targets:
        return None
    return DatabaseDiagramPlan(
        repo_root=repo_root,
        targets=targets,
        source=diagram_root(repo_root) / DATABASE_GRAPH_FILENAME,
    )


def build_tooling_diagram_plan(repo_path: str | Path) -> ToolingDiagramPlan | None:
    repo_root = Path(repo_path).resolve()
    targets = tuple(collect_tooling_diagram_targets(repo_root))
    if not targets:
        return None
    return ToolingDiagramPlan(
        repo_root=repo_root,
        targets=targets,
        source=diagram_root(repo_root) / TOOLING_GRAPH_FILENAME,
    )


def find_plantuml_sources(repo_path: str | Path) -> list[Path]:
    repo_root = Path(repo_path).resolve()
    root = diagram_root(repo_path)
    if not root.exists():
        return []
    ignored_filenames = _managed_generated_plantuml_filenames(repo_root)
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in PLANTUML_SUFFIXES
            and path.name not in ignored_filenames
        ),
        key=str,
    )


def find_drawio_sources(repo_path: str | Path) -> list[Path]:
    root = diagram_root(repo_path)
    if not root.exists():
        return []
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in DRAWIO_SUFFIXES),
        key=str,
    )


def build_render_steps(repo_path: str | Path, *, archility_root: Path | None = None) -> list[RenderStep]:
    repo_root = Path(repo_path).resolve()
    tool_root = (archility_root or package_repo_root()).resolve() / "tools" / "bin"
    plantuml_bin = str(tool_root / "plantuml")
    drawio_bin = str(tool_root / "drawio")
    pydeps_bin = str(tool_root / "pydeps")
    pyreverse_bin = str(tool_root / "pyreverse")

    steps: list[RenderStep] = []
    for source in find_plantuml_sources(repo_root):
        steps.extend(_build_plantuml_render_steps(source, plantuml_bin))

    for source in find_drawio_sources(repo_root):
        steps.extend(_build_drawio_render_steps(source, drawio_bin))

    python_plan = build_python_diagram_plan(repo_root)
    if python_plan is not None:
        pyreverse_step = _build_pyreverse_step(python_plan, pyreverse_bin)
        if pyreverse_step is not None:
            steps.append(pyreverse_step)
            for source, produced_stem in zip(
                python_plan.pyreverse_sources,
                python_plan.pyreverse_produced_stems,
                strict=True,
            ):
                steps.extend(_build_plantuml_render_steps(source, plantuml_bin, produced_stem=produced_stem))
        steps.extend(_build_pydeps_steps(python_plan, pydeps_bin))
    shell_plan = build_shell_diagram_plan(repo_root)
    if shell_plan is not None:
        steps.extend(_build_shell_diagram_steps(shell_plan, plantuml_bin))
    database_plan = build_database_diagram_plan(repo_root)
    if database_plan is not None:
        steps.extend(_build_database_diagram_steps(database_plan, plantuml_bin))
    tooling_plan = build_tooling_diagram_plan(repo_root)
    if tooling_plan is not None:
        steps.extend(_build_tooling_diagram_steps(tooling_plan, plantuml_bin))

    return steps


def ensure_tools_available(steps: list[RenderStep]) -> None:
    missing: list[str] = []
    seen: set[str] = set()
    for step in steps:
        if step.is_internal:
            continue
        tool_path = Path(step.command[0])
        if step.command[0] in seen:
            continue
        seen.add(step.command[0])
        if not tool_path.exists():
            missing.append(str(tool_path))
    if missing:
        joined = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(
            "Required archility tool wrappers are missing. Run archility/setup.sh first.\n" + joined
        )


def run_render_steps(steps: list[RenderStep], *, runner: RunCommand | None = None) -> None:
    _normalize_drawio_sources(steps)
    ensure_tools_available(steps)
    execute = runner or _default_runner
    for step in steps:
        if step.internal_action is not None:
            step.internal_action()
        else:
            execute(step.command, step.cwd)
        for produced_output, target_output in zip(step.produced_outputs, step.outputs, strict=True):
            _ensure_step_output(step.source, Path(produced_output), Path(target_output))
        if step.tool == "pyreverse":
            _normalize_pyreverse_outputs(step)


def _default_runner(command: list[str], cwd: str | None) -> None:
    subprocess.run(command, check=True, cwd=cwd)


def format_render_plan(repo_path: str | Path, steps: list[RenderStep]) -> str:
    repo_root = Path(repo_path).resolve()
    lines = [f"repo: {repo_root}", f"steps: {len(steps)}"]
    if not steps:
        lines.append("  no diagram source files found under docs/diagrams")
        return "\n".join(lines)
    for step in steps:
        rendered_names = ", ".join(Path(output).name for output in step.outputs)
        source_name = step.source if ", " in step.source else Path(step.source).name
        lines.append(f"  - {step.tool}: {source_name} -> {rendered_names}")
        lines.append("    command: " + " ".join(step.command))
        if step.cwd is not None:
            lines.append(f"    cwd: {step.cwd}")
    return "\n".join(lines)


def _build_plantuml_render_steps(
    source: Path,
    plantuml_bin: str,
    *,
    produced_stem: str | None = None,
) -> list[RenderStep]:
    source_str = str(source)
    produced_base = source.with_suffix("") if produced_stem is None else source.parent / produced_stem
    return [
        _single_output_step(
            tool="plantuml",
            source=source_str,
            output=source_str + ".svg",
            produced_output=str(produced_base.with_suffix(".svg")),
            command=[plantuml_bin, "-tsvg", source_str],
        ),
        _single_output_step(
            tool="plantuml",
            source=source_str,
            output=source_str + ".png",
            produced_output=str(produced_base.with_suffix(".png")),
            command=[plantuml_bin, "-tpng", source_str],
        ),
    ]


def _build_drawio_render_steps(source: Path, drawio_bin: str) -> list[RenderStep]:
    source_str = str(source)
    return [
        _single_output_step(
            tool="drawio",
            source=source_str,
            output=source_str + ".svg",
            produced_output=source_str + ".svg",
            command=[drawio_bin, "--no-sandbox", "-x", "-f", "svg", "-o", source_str + ".svg", source_str],
        ),
        _single_output_step(
            tool="drawio",
            source=source_str,
            output=source_str + ".png",
            produced_output=source_str + ".png",
            command=[drawio_bin, "--no-sandbox", "-x", "-f", "png", "-o", source_str + ".png", source_str],
        ),
    ]


def _build_pydeps_steps(plan: PythonDiagramPlan, pydeps_bin: str) -> list[RenderStep]:
    steps: list[RenderStep] = []
    for target, output in zip(plan.targets, plan.pydeps_outputs, strict=True):
        relative_target = str(target.relative_to(plan.repo_root))
        relative_output = str(output.relative_to(plan.repo_root))
        steps.append(
            _single_output_step(
                tool="pydeps",
                source=relative_target,
                output=str(output),
                produced_output=str(output),
                command=[
                    pydeps_bin,
                    "--no-config",
                    "--noshow",
                    "--max-bacon",
                    "0",
                    "-T",
                    "svg",
                    "-o",
                    relative_output,
                    relative_target,
                ],
                cwd=str(plan.repo_root),
            )
        )
    return steps


def _build_pyreverse_step(plan: PythonDiagramPlan, pyreverse_bin: str) -> RenderStep | None:
    if not plan.targets:
        return None

    project_name = plan.project_name
    relative_targets = [str(target.relative_to(plan.repo_root)) for target in plan.targets]
    output_directory = str(diagram_root(plan.repo_root).relative_to(plan.repo_root))
    source_roots = sorted(
        {
            str(_pyreverse_source_root(target).relative_to(plan.repo_root))
            for target in plan.targets
        }
    )
    produced_outputs = [diagram_root(plan.repo_root) / f"{stem}.puml" for stem in plan.pyreverse_produced_stems]

    return RenderStep(
        tool="pyreverse",
        source=", ".join(relative_targets),
        outputs=tuple(str(path) for path in plan.pyreverse_sources),
        produced_outputs=tuple(str(path) for path in produced_outputs),
        command=[
            pyreverse_bin,
            "--output",
            "puml",
            "--output-directory",
            output_directory,
            "--project",
            project_name,
            "--source-roots",
            ",".join(source_roots),
            *relative_targets,
        ],
        cwd=str(plan.repo_root),
    )


def _build_shell_diagram_steps(plan: ShellDiagramPlan, plantuml_bin: str) -> list[RenderStep]:
    relative_targets = ", ".join(str(path.relative_to(plan.repo_root)) for path in plan.targets)
    return _build_generated_plantuml_steps(
        tool="archility-shell",
        source=plan.source,
        description=relative_targets,
        plantuml_bin=plantuml_bin,
        generator=lambda: _build_shell_graph_text(plan),
    )


def _build_database_diagram_steps(plan: DatabaseDiagramPlan, plantuml_bin: str) -> list[RenderStep]:
    relative_targets = ", ".join(str(path.relative_to(plan.repo_root)) for path in plan.targets)
    return _build_generated_plantuml_steps(
        tool="archility-database",
        source=plan.source,
        description=relative_targets,
        plantuml_bin=plantuml_bin,
        generator=lambda: _build_database_graph_text(plan),
    )


def _build_tooling_diagram_steps(plan: ToolingDiagramPlan, plantuml_bin: str) -> list[RenderStep]:
    relative_targets = ", ".join(str(path.relative_to(plan.repo_root)) for path in plan.targets)
    return _build_generated_plantuml_steps(
        tool="archility-tooling",
        source=plan.source,
        description=relative_targets,
        plantuml_bin=plantuml_bin,
        generator=lambda: _build_tooling_graph_text(plan),
    )


def _build_generated_plantuml_steps(
    *,
    tool: str,
    source: Path,
    description: str,
    plantuml_bin: str,
    generator: Callable[[], str],
) -> list[RenderStep]:
    def write_source() -> None:
        source.parent.mkdir(parents=True, exist_ok=True)
        text = generator()
        source.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")

    return [
        RenderStep(
            tool=tool,
            source=description,
            outputs=(str(source),),
            produced_outputs=(str(source),),
            command=["archility", tool, str(source)],
            internal_action=write_source,
        ),
        *_build_plantuml_render_steps(source, plantuml_bin),
    ]


def _single_output_step(
    *,
    tool: str,
    source: str,
    output: str,
    produced_output: str,
    command: list[str],
    cwd: str | None = None,
) -> RenderStep:
    return RenderStep(
        tool=tool,
        source=source,
        outputs=(output,),
        produced_outputs=(produced_output,),
        command=command,
        cwd=cwd,
    )


def _ensure_step_output(source: str, produced_path: Path, target_path: Path) -> None:
    if produced_path != target_path and produced_path.exists():
        target_path.parent.mkdir(parents=True, exist_ok=True)
        produced_path.replace(target_path)
    if not target_path.exists():
        raise FileNotFoundError(
            f"Expected render output was not produced for {source}: {target_path}"
        )
    _normalize_text_output(target_path)


def _normalize_text_output(path: Path) -> None:
    if path.suffix.lower() not in NORMALIZED_TEXT_OUTPUT_SUFFIXES or not path.exists():
        return
    payload = path.read_bytes()
    if payload.endswith(b"\n"):
        return
    path.write_bytes(payload + b"\n")


def _is_package_target(path: Path) -> bool:
    return path.is_dir() and (path / "__init__.py").is_file()


def _pyreverse_source_root(target: Path) -> Path:
    return target.parent


def _python_target_label(repo_root: Path, target: Path) -> str:
    normalized = target.relative_to(repo_root).as_posix()
    if target.is_file() and target.suffix == ".py":
        normalized = normalized[: -len(".py")]
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", normalized.replace("/", "-")).strip("-")
    return label or _safe_project_name(repo_root.name)


def _safe_project_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
    return safe or "repository"


def _managed_generated_plantuml_filenames(repo_root: Path) -> set[str]:
    project_name = _safe_project_name(repo_root.name)
    return {
        *MANAGED_SUPPLEMENTAL_FILENAMES,
        *MANAGED_PYREVERSE_FILENAMES,
        f"classes_{project_name}.puml",
        f"packages_{project_name}.puml",
    }


def _normalize_pyreverse_outputs(step: RenderStep) -> None:
    if step.cwd is None:
        return

    repo_root = Path(step.cwd)
    module_info = _collect_python_module_info(repo_root)
    python_plan = build_python_diagram_plan(repo_root)

    for output in (Path(path) for path in step.outputs):
        if not output.exists():
            continue
        if output.name == "python-packages.puml":
            _normalize_pyreverse_package_source(output, module_info)
            continue
        if output.name == "python-classes.puml":
            _normalize_pyreverse_class_source(
                output,
                module_info=module_info,
                pydeps_outputs=tuple(python_plan.pydeps_outputs) if python_plan is not None else (),
                repo_root=repo_root,
            )


def _collect_python_module_info(repo_root: Path) -> dict[str, PythonModuleInfo]:
    module_info: dict[str, PythonModuleInfo] = {}
    for target in collect_python_diagram_targets(repo_root):
        for path in _iter_python_files_for_target(target):
            module_aliases = _python_module_aliases(repo_root, target, path)
            if not module_aliases:
                continue
            class_count, function_count = _count_top_level_python_symbols(path)
            info = PythonModuleInfo(
                name=module_aliases[0],
                path=path,
                is_package=path.name == "__init__.py",
                class_count=class_count,
                function_count=function_count,
            )
            for module_name in module_aliases:
                module_info.setdefault(module_name, info)
    return module_info


def _iter_python_files_for_target(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(
        (
            path
            for path in target.rglob("*.py")
            if path.is_file() and "__pycache__" not in path.parts
        ),
        key=str,
    )


def _python_module_name(source_root: Path, path: Path) -> str:
    relative = path.relative_to(source_root).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _python_module_aliases(repo_root: Path, target: Path, path: Path) -> tuple[str, ...]:
    aliases: list[str] = []
    for source_root in (_pyreverse_source_root(target), repo_root):
        module_name = _python_module_name(source_root, path)
        if not module_name or module_name in aliases:
            continue
        aliases.append(module_name)
    return tuple(aliases)


def _count_top_level_python_symbols(path: Path) -> tuple[int, int]:
    try:
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return (0, 0)

    class_count = 0
    function_count = 0
    for node in module.body:
        if isinstance(node, ast.ClassDef):
            class_count += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_count += 1
    return (class_count, function_count)


def _normalize_pyreverse_package_source(
    source: Path,
    module_info: dict[str, PythonModuleInfo],
) -> None:
    text = source.read_text(encoding="utf-8")
    startuml, nodes, edges = _parse_pyreverse_package_source(text)
    if not nodes:
        return

    lines = [
        startuml,
        "set namespaceSeparator none",
        "top to bottom direction",
        "skinparam componentStyle rectangle",
    ]
    for label, alias in nodes:
        lines.append(f'rectangle "{_escape_plantuml_label(_python_package_summary_label(label, module_info))}" as {alias}')
    lines.extend(edges)
    lines.append("@enduml")
    source.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _normalize_pyreverse_class_source(
    source: Path,
    *,
    module_info: dict[str, PythonModuleInfo],
    pydeps_outputs: tuple[Path, ...],
    repo_root: Path,
) -> None:
    text = source.read_text(encoding="utf-8")
    if _count_pyreverse_class_entities(text) > LOW_SIGNAL_PYREVERSE_CLASS_THRESHOLD:
        return

    module_count = len(_unique_python_module_info(module_info))
    pydeps_names = ", ".join(path.name for path in pydeps_outputs)
    note_lines = [
        "note as archilityPythonSurfaceNote",
        "Minimal class surface detected.",
        f"Scanned {module_count} Python module{'s' if module_count != 1 else ''}.",
    ]
    if pydeps_names:
        note_lines.append(f"See {pydeps_names} for module-level imports.")
    note_lines.append("end note")
    normalized = text.rstrip()
    if normalized.endswith("@enduml"):
        normalized = normalized[: -len("@enduml")].rstrip()
    source.write_text(normalized + "\n" + "\n".join(note_lines) + "\n@enduml\n", encoding="utf-8")


def _parse_pyreverse_package_source(text: str) -> tuple[str, list[tuple[str, str]], list[str]]:
    startuml = "@startuml packages"
    nodes: list[tuple[str, str]] = []
    edges: list[str] = []
    package_pattern = re.compile(r'^package "([^"]+)" as ([^ ]+) \{$')
    edge_pattern = re.compile(r"^[A-Za-z0-9_.-]+ --> [A-Za-z0-9_.-]+$")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("@startuml"):
            startuml = line
            continue
        package_match = package_pattern.match(line)
        if package_match is not None:
            nodes.append((package_match.group(1), package_match.group(2)))
            continue
        if edge_pattern.match(line):
            edges.append(line)
    return (startuml, nodes, edges)


def _python_package_summary_label(package_name: str, module_info: dict[str, PythonModuleInfo]) -> str:
    direct_children: list[PythonModuleInfo] = []
    prefix = f"{package_name}."
    for module_name, info in module_info.items():
        if module_name == package_name:
            continue
        if not module_name.startswith(prefix):
            continue
        remainder = module_name[len(prefix) :]
        if "." in remainder:
            continue
        direct_children.append(info)

    package_modules = sum(
        1
        for module_name in module_info
        if module_name == package_name or module_name.startswith(prefix)
    )
    child_package_count = sum(1 for info in direct_children if info.is_package)
    child_module_count = sum(1 for info in direct_children if not info.is_package)
    child_names = [info.name.rsplit(".", 1)[-1] for info in direct_children[:3]]

    summary_lines = [package_name]
    if direct_children:
        summary_lines.append(
            f"{child_package_count} child pkg, {child_module_count} module{'s' if child_module_count != 1 else ''}"
        )
    summary_lines.append(f"{package_modules} python file{'s' if package_modules != 1 else ''}")
    if child_names:
        summary_lines.append("examples: " + ", ".join(child_names))
    return "\n".join(summary_lines)


def _count_pyreverse_class_entities(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.lstrip().startswith('class "'))


def _escape_plantuml_label(label: str) -> str:
    return label.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _unique_python_module_info(module_info: dict[str, PythonModuleInfo]) -> list[PythonModuleInfo]:
    unique_by_path: dict[Path, PythonModuleInfo] = {}
    for info in module_info.values():
        unique_by_path.setdefault(info.path, info)
    return list(unique_by_path.values())


def _build_shell_graph_text(plan: ShellDiagramPlan) -> str:
    shell_targets = {path.resolve() for path in plan.targets}
    script_aliases: dict[Path, str] = {}
    tool_aliases: dict[str, str] = {}
    alias_counts: dict[str, int] = {}
    local_edges: set[tuple[str, str, str]] = set()
    tool_edges: set[tuple[str, str]] = set()
    script_summaries: list[tuple[Path, str, int, int]] = []
    all_tools: set[str] = set()

    for path in plan.targets:
        relative = _relative_repo_path(plan.repo_root, path)
        script_aliases[path] = _unique_alias("shell", relative, alias_counts)

    for path in plan.targets:
        local_calls, tools = _analyze_shell_script(plan.repo_root, path, shell_targets)
        relative = _relative_repo_path(plan.repo_root, path)
        script_summaries.append((path, relative, len(local_calls), len(tools)))
        all_tools.update(tools)
        for target, relation in local_calls:
            if target not in script_aliases:
                continue
            local_edges.add((script_aliases[path], script_aliases[target], relation))
        for tool_name in tools:
            tool_edges.add((script_aliases[path], tool_name))

    lines = [
        "@startuml",
        f"title {plan.repo_root.name} Shell Script Flow",
        "left to right direction",
        "skinparam shadowing false",
        "skinparam defaultFontName Monospace",
        "skinparam componentStyle rectangle",
        "skinparam linetype ortho",
    ]
    for path, relative, local_count, tool_count in sorted(script_summaries, key=lambda item: item[1]):
        label_lines = [
            relative,
            f"{local_count} local shell edge{'s' if local_count != 1 else ''}",
            f"{tool_count} external tool{'s' if tool_count != 1 else ''}",
        ]
        label_text = _escape_plantuml_label("\n".join(label_lines))
        lines.append(f'rectangle "{label_text}" as {script_aliases[path]} #DBEAFE')
    for tool_name in sorted(all_tools):
        tool_aliases[tool_name] = _unique_alias("tool", tool_name, alias_counts)
        lines.append(
            f'cloud "{_escape_plantuml_label(tool_name)}" as {tool_aliases[tool_name]} #FEF3C7'
        )
    for source_alias, target_alias, relation in sorted(local_edges):
        lines.append(f"{source_alias} --> {target_alias} : {relation}")
    for source_alias, tool_name in sorted(tool_edges):
        lines.append(f"{source_alias} --> {tool_aliases[tool_name]}")
    lines.extend(
        [
            "note as shellGraphSummary",
            f"Scanned {len(plan.targets)} shell script{'s' if len(plan.targets) != 1 else ''}.",
            f"Detected {len(local_edges)} local shell edge{'s' if len(local_edges) != 1 else ''}.",
            f"Detected {len(all_tools)} external tool{'s' if len(all_tools) != 1 else ''}.",
            "end note",
            "@enduml",
        ]
    )
    return "\n".join(lines)


def _build_database_graph_text(plan: DatabaseDiagramPlan) -> str:
    tables: dict[str, set[str]] = {}
    relations: set[tuple[str, str]] = set()
    alias_counts: dict[str, int] = {}
    for path in plan.targets:
        relative = _relative_repo_path(plan.repo_root, path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        for statement in re.split(r";\s*", text):
            statement = statement.strip()
            if not statement:
                continue
            source_table = None
            create_match = CREATE_TABLE_PATTERN.search(statement)
            if create_match is not None:
                source_table = _normalize_sql_identifier(create_match.group(1))
            else:
                alter_match = ALTER_TABLE_PATTERN.search(statement)
                if alter_match is not None:
                    source_table = _normalize_sql_identifier(alter_match.group(1))
            if source_table is None:
                continue
            tables.setdefault(source_table, set()).add(relative)
            for reference in REFERENCES_PATTERN.findall(statement):
                target_table = _normalize_sql_identifier(reference)
                if not target_table:
                    continue
                tables.setdefault(target_table, set())
                relations.add((source_table, target_table))

    lines = [
        "@startuml",
        f"title {plan.repo_root.name} Database Schema Overview",
        "left to right direction",
        "skinparam shadowing false",
        "skinparam defaultFontName Monospace",
        "skinparam linetype ortho",
    ]
    if not tables:
        lines.extend(
            [
                "note as databaseSchemaSummary",
                f"Scanned {len(plan.targets)} SQL file{'s' if len(plan.targets) != 1 else ''}.",
                "No CREATE TABLE or REFERENCES patterns were detected.",
                "Files: " + ", ".join(_relative_repo_path(plan.repo_root, path) for path in plan.targets[:5]),
                "end note",
                "@enduml",
            ]
        )
        return "\n".join(lines)

    table_aliases = {
        table_name: _unique_alias("table", table_name, alias_counts)
        for table_name in sorted(tables)
    }
    for table_name in sorted(tables):
        lines.append(
            f'entity "{_escape_plantuml_label(_sql_table_summary_label(table_name, tables[table_name]))}" as {table_aliases[table_name]} #DCFCE7'
        )
    for source_table, target_table in sorted(relations):
        if source_table not in table_aliases or target_table not in table_aliases:
            continue
        lines.append(f"{table_aliases[source_table]} --> {table_aliases[target_table]} : FK")
    lines.extend(
        [
            "note as databaseSchemaSummary",
            f"Scanned {len(plan.targets)} SQL file{'s' if len(plan.targets) != 1 else ''}.",
            f"Detected {len(tables)} table{'s' if len(tables) != 1 else ''}.",
            f"Detected {len(relations)} foreign-key edge{'s' if len(relations) != 1 else ''}.",
            "end note",
            "@enduml",
        ]
    )
    return "\n".join(lines)


def _build_tooling_graph_text(plan: ToolingDiagramPlan) -> str:
    alias_counts: dict[str, int] = {}
    source_aliases: dict[Path, str] = {}
    source_tool_map: dict[Path, tuple[str, ...]] = {}
    all_tools: set[str] = set()

    for path in plan.targets:
        relative = _relative_repo_path(plan.repo_root, path)
        source_aliases[path] = _unique_alias("source", relative, alias_counts)
        tools = tuple(sorted(_extract_tools_from_tooling_source(plan.repo_root, path)))
        source_tool_map[path] = tools
        all_tools.update(tools)

    tool_aliases = {
        tool_name: _unique_alias("tool", tool_name, alias_counts)
        for tool_name in sorted(all_tools)
    }
    lines = [
        "@startuml",
        f"title {plan.repo_root.name} Tooling Integrations",
        "left to right direction",
        "skinparam shadowing false",
        "skinparam defaultFontName Monospace",
        "skinparam componentStyle rectangle",
        "skinparam linetype ortho",
    ]
    for path in sorted(plan.targets, key=lambda entry: _relative_repo_path(plan.repo_root, entry)):
        relative = _relative_repo_path(plan.repo_root, path)
        tools = source_tool_map[path]
        label_lines = [
            relative,
            f"{len(tools)} detected tool{'s' if len(tools) != 1 else ''}",
        ]
        label_text = _escape_plantuml_label("\n".join(label_lines))
        lines.append(f'rectangle "{label_text}" as {source_aliases[path]} #E0F2FE')
    for tool_name in sorted(all_tools):
        lines.append(f'cloud "{_escape_plantuml_label(tool_name)}" as {tool_aliases[tool_name]} #FEF3C7')
    for path in sorted(plan.targets, key=lambda entry: _relative_repo_path(plan.repo_root, entry)):
        for tool_name in source_tool_map[path]:
            lines.append(f"{source_aliases[path]} --> {tool_aliases[tool_name]}")
    lines.extend(
        [
            "note as toolingGraphSummary",
            f"Scanned {len(plan.targets)} tooling entrypoint{'s' if len(plan.targets) != 1 else ''}.",
            f"Detected {len(all_tools)} third-party tool{'s' if len(all_tools) != 1 else ''}.",
            "end note",
            "@enduml",
        ]
    )
    return "\n".join(lines)


def _analyze_shell_script(
    repo_root: Path,
    path: Path,
    shell_targets: set[Path],
) -> tuple[set[tuple[Path, str]], set[str]]:
    local_calls: set[tuple[Path, str]] = set()
    tools: set[str] = set()
    text = path.read_text(encoding="utf-8", errors="ignore")
    function_names = _collect_shell_function_names(text)
    for tokens in _iter_command_token_lists(text):
        command_tokens = _strip_command_wrappers(tokens)
        if not command_tokens:
            continue
        head = command_tokens[0]
        if Path(head).name in function_names:
            continue
        if head in {".", "source"}:
            local_target = _resolve_local_shell_target(path, command_tokens[1] if len(command_tokens) > 1 else None, shell_targets)
            if local_target is not None:
                local_calls.add((local_target, "source"))
            continue
        if Path(head).name in SHELL_INTERPRETERS and len(command_tokens) > 1:
            local_target = _resolve_local_shell_target(path, command_tokens[1], shell_targets)
            if local_target is not None:
                local_calls.add((local_target, "exec"))
                continue
        local_target = _resolve_local_shell_target(path, head, shell_targets)
        if local_target is not None:
            local_calls.add((local_target, "call"))
            continue
        tool_name = _normalize_tool_command(command_tokens, repo_root=repo_root, current_path=path)
        if tool_name is not None and tool_name not in SHELL_INTERPRETERS:
            tools.add(tool_name)
    return (local_calls, tools)


def _extract_tools_from_tooling_source(repo_root: Path, path: Path) -> set[str]:
    relative = _relative_repo_path(repo_root, path)
    if relative.startswith(".github/workflows/"):
        return _extract_tools_from_workflow(path, repo_root)
    if path.suffix.lower() in {".sh", ".bash", ".zsh", ".ksh"} or path.name == "setup.sh":
        return _extract_tools_from_shell_script(path, repo_root)
    if path.name.startswith(("Dockerfile", "Containerfile")):
        tools = _extract_tools_from_dockerfile(path, repo_root)
        tools.add("docker")
        return tools
    if path.name in {"compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml"}:
        return {"docker compose"}
    if path.name in {"Makefile", "Justfile"} or path.name.startswith("Makefile."):
        return _extract_tools_from_makefile(path, repo_root)
    if path.name.startswith("Taskfile"):
        return _extract_tools_from_taskfile(path, repo_root)
    return _extract_tools_from_command_text(path.read_text(encoding="utf-8", errors="ignore"), repo_root, path)


def _extract_tools_from_shell_script(path: Path, repo_root: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    function_names = _collect_shell_function_names(text)
    tools: set[str] = set()
    for tokens in _iter_command_token_lists(text):
        command_tokens = _strip_command_wrappers(tokens)
        if not command_tokens:
            continue
        if Path(command_tokens[0]).name in function_names:
            continue
        tool_name = _normalize_tool_command(command_tokens, repo_root=repo_root, current_path=path)
        if tool_name is not None:
            tools.add(tool_name)
    return tools


def _extract_tools_from_workflow(path: Path, repo_root: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    tools = {
        (match.group(1) or match.group(2)).strip().split("@", 1)[0]
        for match in re.finditer(
            r"^\s*-\s*uses:\s*([^\s#]+)|^\s*uses:\s*([^\s#]+)",
            text,
            flags=re.MULTILINE,
        )
    }
    for block in _extract_workflow_run_blocks(text):
        tools.update(_extract_tools_from_command_text(block, repo_root, path))
    return {tool for tool in tools if tool}


def _extract_workflow_run_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r"^(\s*)(?:-\s*)?run:\s*(.*)$", line)
        if match is None:
            index += 1
            continue
        indent = len(match.group(1))
        payload = match.group(2).strip()
        if payload and payload not in {"|", "|-", ">", ">-"}:
            blocks.append(payload)
            index += 1
            continue
        index += 1
        block_lines: list[str] = []
        while index < len(lines):
            candidate = lines[index]
            if not candidate.strip():
                block_lines.append("")
                index += 1
                continue
            candidate_indent = len(candidate) - len(candidate.lstrip(" "))
            if candidate_indent <= indent:
                break
            block_lines.append(candidate[indent + 2 :] if candidate_indent >= indent + 2 else candidate.lstrip())
            index += 1
        blocks.append("\n".join(block_lines))
    return blocks


def _extract_tools_from_dockerfile(path: Path, repo_root: Path) -> set[str]:
    tools: set[str] = set()
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    current_run: list[str] = []
    for line in lines:
        stripped = line.strip()
        if current_run:
            current_run.append(stripped.removesuffix("\\").strip())
            if not stripped.endswith("\\"):
                tools.update(_extract_tools_from_command_text(" ".join(current_run), repo_root, path))
                current_run = []
            continue
        if not stripped.upper().startswith("RUN "):
            continue
        payload = stripped[4:].strip()
        current_run.append(payload.removesuffix("\\").strip())
        if not stripped.endswith("\\"):
            tools.update(_extract_tools_from_command_text(" ".join(current_run), repo_root, path))
            current_run = []
    return tools


def _extract_tools_from_makefile(path: Path, repo_root: Path) -> set[str]:
    command_lines = [
        line.lstrip()
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.startswith("\t")
    ]
    return _extract_tools_from_command_text("\n".join(command_lines), repo_root, path)


def _extract_tools_from_taskfile(path: Path, repo_root: Path) -> set[str]:
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        command_match = re.match(r"^\s*(?:cmd|command):\s*(.+)$", line)
        if command_match is not None:
            lines.append(command_match.group(1))
            continue
        list_match = re.match(r"^\s*-\s+(.+)$", line)
        if list_match is not None:
            lines.append(list_match.group(1))
    return _extract_tools_from_command_text("\n".join(lines), repo_root, path)


def _extract_tools_from_command_text(text: str, repo_root: Path, current_path: Path) -> set[str]:
    tools: set[str] = set()
    for tokens in _iter_command_token_lists(text):
        command_tokens = _strip_command_wrappers(tokens)
        tool_name = _normalize_tool_command(command_tokens, repo_root=repo_root, current_path=current_path)
        if tool_name is not None:
            tools.add(tool_name)
    return tools


def _iter_command_token_lists(text: str) -> list[list[str]]:
    token_lists: list[list[str]] = []
    heredoc_end: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if heredoc_end is not None:
            if line == heredoc_end:
                heredoc_end = None
            continue
        if not line or line.startswith("#"):
            continue
        if _looks_like_shell_function_definition(line) or _looks_like_shell_case_label(line):
            continue
        heredoc_match = re.search(r"<<-?\s*['\"]?([A-Za-z0-9_]+)['\"]?", raw_line)
        for segment in re.split(r"\s*(?:&&|\|\||[|;])\s*", line):
            segment = segment.strip()
            if not segment:
                continue
            try:
                tokens = shlex.split(segment, comments=True, posix=True)
            except ValueError:
                continue
            if tokens:
                token_lists.append(tokens)
        if heredoc_match is not None:
            heredoc_end = heredoc_match.group(1)
    return token_lists


def _collect_shell_function_names(text: str) -> set[str]:
    function_names: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = re.match(r"^(?:function\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{?$", line)
        if match is not None:
            function_names.add(match.group(1))
            continue
        match = re.match(r"^function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{?$", line)
        if match is not None:
            function_names.add(match.group(1))
    return function_names


def _looks_like_shell_function_definition(line: str) -> bool:
    return (
        re.match(r"^(?:function\s+)?[A-Za-z_][A-Za-z0-9_]*\s*\(\)\s*\{?$", line) is not None
        or re.match(r"^function\s+[A-Za-z_][A-Za-z0-9_]*\s*\{?$", line) is not None
    )


def _looks_like_shell_case_label(line: str) -> bool:
    return re.match(r"^(?:\*|[-A-Za-z0-9_|]+)\)\s*$", line) is not None


def _strip_command_wrappers(tokens: list[str]) -> list[str]:
    index = 0
    while index < len(tokens) and ENV_ASSIGNMENT_PATTERN.match(tokens[index]):
        index += 1
    while index < len(tokens):
        token_name = Path(tokens[index]).name
        if token_name == "env":
            index += 1
            while index < len(tokens) and (
                tokens[index].startswith("-") or ENV_ASSIGNMENT_PATTERN.match(tokens[index])
            ):
                index += 1
            continue
        if token_name in COMMAND_WRAPPERS:
            index += 1
            continue
        break
    return tokens[index:]


def _resolve_local_shell_target(current_path: Path, token: str | None, shell_targets: set[Path]) -> Path | None:
    if token in {None, ""}:
        return None
    if any(marker in token for marker in ("$", "*", "{", "}", "(", ")")):
        return None
    raw = Path(token)
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw.resolve())
    else:
        candidates.append((current_path.parent / raw).resolve())
    if raw.suffix == "":
        candidates.extend(candidate.with_suffix(".sh") for candidate in list(candidates))
    for candidate in candidates:
        if candidate in shell_targets:
            return candidate
    return None


def _normalize_tool_command(
    command_tokens: list[str],
    *,
    repo_root: Path,
    current_path: Path,
) -> str | None:
    if not command_tokens:
        return None
    head = command_tokens[0]
    head_name = Path(head).name
    if head in {".", "source"} or head_name in SHELL_CONTROL_KEYWORDS or head_name in SHELL_BUILTINS:
        return None
    if (
        not head_name
        or head_name.startswith("-")
        or head_name.endswith(":")
        or head_name.endswith(")")
        or head_name.endswith("()")
        or any(marker in head_name for marker in ("$", "{", "}"))
        or head_name.isupper()
        or not any(character.isalnum() for character in head_name)
    ):
        return None
    if head_name.startswith("python") and len(command_tokens) > 2 and command_tokens[1] == "-m":
        return command_tokens[2].split(".", 1)[0]
    if head_name in {"docker", "podman"} and len(command_tokens) > 1 and command_tokens[1] == "compose":
        return f"{head_name} compose"
    if head_name in SHELL_INTERPRETERS and len(command_tokens) > 1:
        resolved = _resolve_repo_relative_path(current_path, command_tokens[1])
        if resolved is not None and _is_tool_wrapper_path(repo_root, resolved):
            return resolved.name
        if resolved is not None and resolved.is_file():
            return None
        return head_name
    if "/" in head or head.startswith("."):
        resolved = _resolve_repo_relative_path(current_path, head)
        if resolved is not None and _is_tool_wrapper_path(repo_root, resolved):
            return resolved.name
        if resolved is not None and resolved.is_file():
            return None
        return head_name or head
    return head_name


def _resolve_repo_relative_path(current_path: Path, token: str) -> Path | None:
    raw = Path(token)
    candidate = raw if raw.is_absolute() else current_path.parent / raw
    try:
        resolved = candidate.resolve()
    except OSError:
        return None
    return resolved if resolved.exists() else None


def _is_tool_wrapper_path(repo_root: Path, path: Path) -> bool:
    try:
        relative_parts = path.relative_to(repo_root).parts
    except ValueError:
        return False
    return relative_parts[: len(TOOL_WRAPPER_DIR_PARTS)] == TOOL_WRAPPER_DIR_PARTS


def _normalize_sql_identifier(identifier: str) -> str:
    cleaned_parts = [
        part.strip().strip('`"[]')
        for part in identifier.strip().rstrip(",)").split(".")
        if part.strip().strip('`"[]')
    ]
    return ".".join(cleaned_parts)


def _sql_table_summary_label(table_name: str, source_files: set[str]) -> str:
    lines = [table_name]
    if not source_files:
        lines.append("referenced table")
        return "\n".join(lines)
    if len(source_files) == 1:
        lines.append(next(iter(sorted(source_files))))
    else:
        lines.append(f"{len(source_files)} schema files")
        lines.append("examples: " + ", ".join(sorted(source_files)[:2]))
    return "\n".join(lines)


def _relative_repo_path(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def _unique_alias(prefix: str, label: str, counts: dict[str, int]) -> str:
    base = re.sub(r"[^A-Za-z0-9_]+", "_", label).strip("_").lower() or prefix
    if base[0].isdigit():
        base = f"{prefix}_{base}"
    counts[base] = counts.get(base, 0) + 1
    suffix = "" if counts[base] == 1 else f"_{counts[base]}"
    return f"{prefix}_{base}{suffix}"


def _normalize_drawio_sources(steps: list[RenderStep]) -> None:
    normalized_sources: set[Path] = set()
    for step in steps:
        if step.tool != "drawio":
            continue
        source = Path(step.source)
        if source in normalized_sources:
            continue
        normalized_sources.add(source)
        _normalize_drawio_source(source)


def _normalize_drawio_source(source: Path) -> bool:
    tree = ElementTree.parse(source)
    root = tree.getroot()
    spacing_changed = _normalize_drawio_panel_spacing(root)
    bounds_by_cell_id = _drawio_vertex_bounds(root)
    routing_plan = _build_drawio_edge_routes(root, bounds_by_cell_id)
    changed = spacing_changed

    for cell in root.iter("mxCell"):
        if cell.attrib.get("edge") != "1":
            continue
        style = cell.attrib.get("style", "")
        normalized_style = _normalize_drawio_edge_style(style)
        if normalized_style == style:
            style_changed = False
        else:
            cell.set("style", normalized_style)
            style_changed = True

        route_changed = _apply_drawio_edge_route(cell, routing_plan.get(cell.attrib.get("id", "")))
        changed = changed or style_changed or route_changed

    if not changed:
        return False

    ElementTree.indent(tree, space="  ")
    buffer = io.StringIO()
    tree.write(buffer, encoding="unicode", xml_declaration=True)
    source.write_text(buffer.getvalue() + "\n", encoding="utf-8")
    return True


def _normalize_drawio_edge_style(style: str) -> str:
    ordered_keys: list[str] = []
    style_map: dict[str, str] = {}
    for part in style.split(";"):
        if not part:
            continue
        key, separator, value = part.partition("=")
        if key not in style_map:
            ordered_keys.append(key)
        style_map[key] = value if separator else ""

    for key, value in DRAWIO_EDGE_STYLE_DEFAULTS:
        if style_map.get(key) not in {None, "", "none"}:
            continue
        if key not in style_map:
            ordered_keys.append(key)
        style_map[key] = value

    return ";".join(
        f"{key}={style_map[key]}" if style_map[key] else key
        for key in ordered_keys
    ) + ";"


def _drawio_vertex_bounds(root: ElementTree.Element) -> dict[str, DrawioCellBounds]:
    bounds: dict[str, DrawioCellBounds] = {}
    for cell in root.iter("mxCell"):
        if cell.attrib.get("vertex") != "1":
            continue
        geometry = cell.find("mxGeometry")
        if geometry is None:
            continue
        x = _parse_drawio_number(geometry.attrib.get("x"))
        y = _parse_drawio_number(geometry.attrib.get("y"))
        width = _parse_drawio_number(geometry.attrib.get("width"))
        height = _parse_drawio_number(geometry.attrib.get("height"))
        if None in {x, y, width, height}:
            continue
        bounds[cell.attrib["id"]] = DrawioCellBounds(x=x, y=y, width=width, height=height)
    return bounds


def _drawio_container_ids(bounds_by_cell_id: dict[str, DrawioCellBounds]) -> set[str]:
    """Return IDs of vertex cells that visually contain at least one other vertex cell.

    Container cells are visual grouping boxes (panels) that should not be
    treated as routing obstacles — edges between their children need to route
    through the inter-row corridors inside them, not all the way around them.
    """
    container_ids: set[str] = set()
    tolerance = 5.0
    items = list(bounds_by_cell_id.items())
    for c_id, c_bounds in items:
        for v_id, v_bounds in items:
            if v_id == c_id:
                continue
            if (
                v_bounds.left >= c_bounds.left - tolerance
                and v_bounds.right <= c_bounds.right + tolerance
                and v_bounds.top >= c_bounds.top - tolerance
                and v_bounds.bottom <= c_bounds.bottom + tolerance
            ):
                container_ids.add(c_id)
                break
    return container_ids


def _normalize_drawio_panel_spacing(root: ElementTree.Element) -> bool:
    """Redistribute child nodes within panel containers to ensure routing corridors.

    Expands inter-row gaps to _PANEL_MIN_ROW_GAP (or _PANEL_MIN_NOTE_GAP for
    short annotation cells), grows panel heights as needed, and shifts any
    floating nodes below expanded panels downward to prevent overlap.

    Nodes at the same y position are treated as a single side-by-side row and
    are not separated from each other — only the gap between distinct rows is
    expanded.
    """
    bounds = _drawio_vertex_bounds(root)
    container_ids = _drawio_container_ids(bounds)
    if not container_ids:
        return False

    tolerance = 5.0
    y_deltas: dict[str, float] = {}
    h_deltas: dict[str, float] = {}

    for panel_id in sorted(container_ids, key=lambda cid: (bounds[cid].left, bounds[cid].top)):
        pb = bounds[panel_id]

        children: list[tuple[float, str]] = []
        for cell_id, cb in bounds.items():
            if cell_id == panel_id or cell_id in container_ids:
                continue
            if (
                cb.left >= pb.left - tolerance
                and cb.right <= pb.right + tolerance
                and cb.top >= pb.top - tolerance
                and cb.bottom <= pb.bottom + tolerance
            ):
                eff_top = cb.top + y_deltas.get(cell_id, 0.0)
                children.append((eff_top, cell_id))

        children.sort()
        if not children:
            continue

        # Group children that are at the same y position into rows (side-by-side
        # layout).  Only apply minimum row gaps between distinct rows.
        rows: list[list[tuple[float, str]]] = []
        for eff_top, cell_id in children:
            if rows and abs(eff_top - rows[-1][0][0]) <= tolerance:
                rows[-1].append((eff_top, cell_id))
            else:
                rows.append([(eff_top, cell_id)])

        min_y = pb.top + _PANEL_MIN_HEADER_GAP
        for i, row in enumerate(rows):
            row_top = row[0][0]
            row_bottom = max(
                bounds[cell_id].top + y_deltas.get(cell_id, 0.0) + bounds[cell_id].height
                for _, cell_id in row
            )
            new_row_top = max(row_top, min_y)
            push = new_row_top - row_top
            if push > 0.5:
                for _, cell_id in row:
                    y_deltas[cell_id] = y_deltas.get(cell_id, 0.0) + push
                row_bottom += push

            if i < len(rows) - 1:
                next_row = rows[i + 1]
                next_height = max(bounds[cell_id].height for _, cell_id in next_row)
                min_gap = (
                    _PANEL_MIN_ROW_GAP
                    if next_height >= _PANEL_NOTE_HEIGHT_THRESHOLD
                    else _PANEL_MIN_NOTE_GAP
                )
                min_y = row_bottom + min_gap

        last_row = rows[-1]
        new_last_bottom = max(
            bounds[cell_id].top + y_deltas.get(cell_id, 0.0) + bounds[cell_id].height
            for _, cell_id in last_row
        )
        new_panel_bottom = new_last_bottom + _PANEL_MIN_FOOTER_GAP
        # Account for the panel's own y-shift from a prior panel's expansion.
        panel_y_shift = y_deltas.get(panel_id, 0.0)
        old_panel_bottom = pb.bottom + panel_y_shift + h_deltas.get(panel_id, 0.0)
        h_expand = new_panel_bottom - old_panel_bottom

        if h_expand > 0.5:
            h_deltas[panel_id] = h_deltas.get(panel_id, 0.0) + h_expand
            for cell_id, cb in bounds.items():
                if cell_id in {c for row in rows for _, c in row} or cell_id == panel_id:
                    continue
                eff_top = cb.top + y_deltas.get(cell_id, 0.0)
                if (
                    eff_top >= old_panel_bottom - tolerance
                    and cb.left < pb.right + tolerance
                    and cb.right > pb.left - tolerance
                ):
                    y_deltas[cell_id] = y_deltas.get(cell_id, 0.0) + h_expand

    if not y_deltas and not h_deltas:
        return False

    for cell in root.iter("mxCell"):
        cell_id = cell.attrib.get("id")
        geo = cell.find("mxGeometry")
        if geo is None:
            continue
        if cell_id in y_deltas:
            old_y = _parse_drawio_number(geo.attrib.get("y")) or 0.0
            geo.set("y", _format_drawio_number(old_y + y_deltas[cell_id]))
        if cell_id in h_deltas:
            old_h = _parse_drawio_number(geo.attrib.get("height")) or 0.0
            geo.set("height", _format_drawio_number(old_h + h_deltas[cell_id]))

    return True


def _build_drawio_edge_routes(
    root: ElementTree.Element,
    bounds_by_cell_id: dict[str, DrawioCellBounds],
) -> dict[str, list[tuple[float, float]]]:
    edges: list[tuple[str, str, str, str]] = []
    source_groups: dict[tuple[str, str], list[str]] = {}
    target_groups: dict[tuple[str, str], list[str]] = {}
    lane_groups: dict[tuple[str, int], list[str]] = {}

    for cell in root.iter("mxCell"):
        if cell.attrib.get("edge") != "1":
            continue
        if _drawio_geometry_has_manual_points(cell):
            continue
        edge_id = cell.attrib.get("id")
        source_id = cell.attrib.get("source")
        target_id = cell.attrib.get("target")
        if edge_id is None or source_id is None or target_id is None:
            continue
        source_bounds = bounds_by_cell_id.get(source_id)
        target_bounds = bounds_by_cell_id.get(target_id)
        if source_bounds is None or target_bounds is None:
            continue
        orientation = _drawio_edge_orientation(source_bounds, target_bounds)
        edges.append((edge_id, source_id, target_id, orientation))
        source_groups.setdefault((source_id, _drawio_source_side(orientation)), []).append(edge_id)
        target_groups.setdefault((target_id, _drawio_target_side(orientation)), []).append(edge_id)
        lane_groups.setdefault(_drawio_lane_group_key(orientation, target_bounds), []).append(edge_id)

    # Precompute one center corridor per lane group sequentially so that each
    # group's selection treats corridors already claimed by earlier groups as
    # blocked.  This prevents multiple independent lane groups from piling onto
    # the same corridor segment and producing overlapping edges in the export.
    clearance = 24.0
    lane_gap = 18.0
    # Exclude container cells (panel boxes) from routing obstacles so that
    # edges can find corridors in the inter-row gaps inside panels rather than
    # being forced all the way above or below the entire diagram.
    container_ids = _drawio_container_ids(bounds_by_cell_id)
    # Track assigned corridor coordinates by axis (horizontal covers left+right,
    # vertical covers up+down) so that edges of opposite orientations that share
    # the same corridor plane do not collide.
    axis_assigned_corridors: dict[str, list[float]] = {"horizontal": [], "vertical": []}
    lane_group_corridor: dict[tuple, float] = {}
    processed_lane_keys: set = set()

    for edge_id, source_id, target_id, orientation in edges:
        source_bounds = bounds_by_cell_id[source_id]
        target_bounds = bounds_by_cell_id[target_id]
        lane_key = _drawio_lane_group_key(orientation, target_bounds)
        if lane_key in processed_lane_keys:
            continue
        processed_lane_keys.add(lane_key)

        lane_group = lane_groups[lane_key]
        lane_count = len(lane_group)
        # Block already-claimed corridors with a band wide enough to keep
        # the outermost lane of the new group clear.
        half_band = max(lane_count - 1, 0) / 2 * lane_gap + lane_gap * 1.5
        axis = "horizontal" if orientation in {"left", "right"} else "vertical"
        extra_blocked = [
            (c - half_band, c + half_band)
            for c in axis_assigned_corridors[axis]
        ]
        excluded = {source_id, target_id} | container_ids

        if orientation in {"down", "up"}:
            exit_x = (source_bounds.left + source_bounds.right) / 2
            entry_x = (target_bounds.left + target_bounds.right) / 2
            if orientation == "down":
                span_start = source_bounds.bottom + clearance
                span_end = target_bounds.top - clearance
            else:
                span_start = source_bounds.top - clearance
                span_end = target_bounds.bottom + clearance
            corridor = _select_drawio_vertical_corridor(
                bounds_by_cell_id,
                excluded_ids=excluded,
                span_start=span_start,
                span_end=span_end,
                preferred_positions=(exit_x, entry_x, (exit_x + entry_x) / 2),
                lane_index=0,
                lane_count=1,
                lane_gap=lane_gap,
                padding=clearance,
                extra_blocked_intervals=extra_blocked,
            )
        else:
            exit_y = (source_bounds.top + source_bounds.bottom) / 2
            entry_y = (target_bounds.top + target_bounds.bottom) / 2
            if orientation == "right":
                span_start = source_bounds.right + clearance
                span_end = target_bounds.left - clearance
            else:
                span_start = source_bounds.left - clearance
                span_end = target_bounds.right + clearance
            corridor = _select_drawio_horizontal_corridor(
                bounds_by_cell_id,
                excluded_ids=excluded,
                span_start=span_start,
                span_end=span_end,
                preferred_positions=(exit_y, entry_y, (exit_y + entry_y) / 2),
                lane_index=0,
                lane_count=1,
                lane_gap=lane_gap,
                padding=clearance,
                extra_blocked_intervals=extra_blocked,
            )

        lane_group_corridor[lane_key] = corridor
        axis_assigned_corridors[axis].append(corridor)

    routes: dict[str, list[tuple[float, float]]] = {}
    for edge_id, source_id, target_id, orientation in edges:
        source_bounds = bounds_by_cell_id[source_id]
        target_bounds = bounds_by_cell_id[target_id]
        source_group = source_groups[(source_id, _drawio_source_side(orientation))]
        target_group = target_groups[(target_id, _drawio_target_side(orientation))]
        lane_key = _drawio_lane_group_key(orientation, target_bounds)
        lane_group = lane_groups[lane_key]
        source_index = source_group.index(edge_id)
        target_index = target_group.index(edge_id)
        lane_index = lane_group.index(edge_id)
        source_count = len(source_group)
        target_count = len(target_group)
        lane_count = len(lane_group)
        routes[edge_id] = _drawio_route_points(
            source_id,
            target_id,
            source_bounds,
            target_bounds,
            bounds_by_cell_id=bounds_by_cell_id,
            orientation=orientation,
            source_index=source_index,
            source_count=source_count,
            target_index=target_index,
            target_count=target_count,
            lane_index=lane_index,
            lane_count=lane_count,
            precomputed_corridor=lane_group_corridor.get(lane_key),
        )
    return routes


def _apply_drawio_edge_route(
    cell: ElementTree.Element,
    route: list[tuple[float, float]] | None,
) -> bool:
    if route is None:
        return False

    geometry = cell.find("mxGeometry")
    if geometry is None:
        geometry = ElementTree.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
    geometry.attrib["relative"] = "1"
    geometry.attrib["as"] = "geometry"
    geometry.attrib["archilityManagedRoute"] = "1"

    points = geometry.find("Array[@as='points']")
    if points is not None:
        geometry.remove(points)

    points = ElementTree.SubElement(geometry, "Array", {"as": "points"})
    for x, y in route:
        ElementTree.SubElement(
            points,
            "mxPoint",
            {"x": _format_drawio_number(x), "y": _format_drawio_number(y)},
        )
    return True


def _drawio_geometry_has_manual_points(cell: ElementTree.Element) -> bool:
    geometry = cell.find("mxGeometry")
    if geometry is None:
        return False
    if geometry.find("Array[@as='points']") is None:
        return False
    return geometry.attrib.get("archilityManagedRoute") != "1"


def _drawio_edge_orientation(source: DrawioCellBounds, target: DrawioCellBounds) -> str:
    vertical_gap = max(target.top - source.bottom, source.top - target.bottom, 0.0)
    horizontal_gap = max(target.left - source.right, source.left - target.right, 0.0)

    if vertical_gap >= horizontal_gap and vertical_gap > 0:
        return "down" if target.mid_y >= source.mid_y else "up"
    if horizontal_gap > 0:
        return "right" if target.mid_x >= source.mid_x else "left"
    if abs(target.mid_y - source.mid_y) >= abs(target.mid_x - source.mid_x):
        return "down" if target.mid_y >= source.mid_y else "up"
    return "right" if target.mid_x >= source.mid_x else "left"


def _drawio_source_side(orientation: str) -> str:
    return {
        "down": "south",
        "up": "north",
        "right": "east",
        "left": "west",
    }[orientation]


def _drawio_target_side(orientation: str) -> str:
    return {
        "down": "north",
        "up": "south",
        "right": "west",
        "left": "east",
    }[orientation]


def _drawio_lane_group_key(orientation: str, target: DrawioCellBounds) -> tuple[str, int]:
    if orientation in {"left", "right"}:
        return (orientation, round(target.mid_y))
    return (orientation, round(target.mid_x))


def _drawio_route_points(
    source_id: str,
    target_id: str,
    source: DrawioCellBounds,
    target: DrawioCellBounds,
    *,
    bounds_by_cell_id: dict[str, DrawioCellBounds],
    orientation: str,
    source_index: int,
    source_count: int,
    target_index: int,
    target_count: int,
    lane_index: int,
    lane_count: int,
    precomputed_corridor: float | None = None,
) -> list[tuple[float, float]]:
    anchor_margin = 40.0
    clearance = 24.0
    lane_gap = 18.0
    lane_offset = 0.0 if lane_count <= 1 else (lane_index - (lane_count - 1) / 2) * lane_gap

    if orientation in {"down", "up"}:
        exit_x = _spread_positions(source.left + anchor_margin, source.right - anchor_margin, source_count)[source_index]
        entry_x = _clamp_drawio_coordinate(
            _spread_positions(target.left + anchor_margin, target.right - anchor_margin, target_count)[target_index],
            lower=target.left + anchor_margin / 2,
            upper=target.right - anchor_margin / 2,
        )
        if orientation == "down":
            source_buffer_y = source.bottom + clearance
            target_buffer_y = target.top - clearance
        else:
            source_buffer_y = source.top - clearance
            target_buffer_y = target.bottom + clearance
        if precomputed_corridor is not None:
            corridor_x = precomputed_corridor + lane_offset
        else:
            corridor_x = _select_drawio_vertical_corridor(
                bounds_by_cell_id,
                excluded_ids={source_id, target_id},
                span_start=source_buffer_y,
                span_end=target_buffer_y,
                preferred_positions=(exit_x, entry_x, (exit_x + entry_x) / 2),
                lane_index=lane_index,
                lane_count=lane_count,
                lane_gap=lane_gap,
                padding=clearance,
            )
        return _simplify_drawio_route(
            [
                (exit_x, source_buffer_y),
                (corridor_x, source_buffer_y),
                (corridor_x, target_buffer_y),
                (entry_x, target_buffer_y),
            ]
        )

    exit_y = _spread_positions(source.top + anchor_margin, source.bottom - anchor_margin, source_count)[source_index]
    entry_y = _clamp_drawio_coordinate(
        _spread_positions(target.top + anchor_margin, target.bottom - anchor_margin, target_count)[target_index],
        lower=target.top + anchor_margin / 2,
        upper=target.bottom - anchor_margin / 2,
    )
    if orientation == "right":
        source_buffer_x = source.right + clearance
        target_buffer_x = target.left - clearance
    else:
        source_buffer_x = source.left - clearance
        target_buffer_x = target.right + clearance
    if precomputed_corridor is not None:
        corridor_y = precomputed_corridor + lane_offset
    else:
        corridor_y = _select_drawio_horizontal_corridor(
            bounds_by_cell_id,
            excluded_ids={source_id, target_id},
            span_start=source_buffer_x,
            span_end=target_buffer_x,
            preferred_positions=(exit_y, entry_y, (exit_y + entry_y) / 2),
            lane_index=lane_index,
            lane_count=lane_count,
            lane_gap=lane_gap,
            padding=clearance,
        )
    return _simplify_drawio_route(
        [
            (source_buffer_x, exit_y),
            (source_buffer_x, corridor_y),
            (target_buffer_x, corridor_y),
            (target_buffer_x, entry_y),
        ]
    )


def _select_drawio_horizontal_corridor(
    bounds_by_cell_id: dict[str, DrawioCellBounds],
    *,
    excluded_ids: set[str],
    span_start: float,
    span_end: float,
    preferred_positions: tuple[float, ...],
    lane_index: int,
    lane_count: int,
    lane_gap: float,
    padding: float,
    extra_blocked_intervals: list[tuple[float, float]] | None = None,
) -> float:
    blocked_intervals = _drawio_blocked_intervals_for_horizontal_span(
        bounds_by_cell_id,
        excluded_ids=excluded_ids,
        span_start=span_start,
        span_end=span_end,
        padding=padding,
    )
    if extra_blocked_intervals:
        blocked_intervals = blocked_intervals + extra_blocked_intervals
    lower_bound, upper_bound = _drawio_routing_bounds(bounds_by_cell_id, axis="y", padding=padding)
    return _select_drawio_corridor_coordinate(
        blocked_intervals,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        preferred_positions=preferred_positions,
        lane_index=lane_index,
        lane_count=lane_count,
        lane_gap=lane_gap,
    )


def _select_drawio_vertical_corridor(
    bounds_by_cell_id: dict[str, DrawioCellBounds],
    *,
    excluded_ids: set[str],
    span_start: float,
    span_end: float,
    preferred_positions: tuple[float, ...],
    lane_index: int,
    lane_count: int,
    lane_gap: float,
    padding: float,
    extra_blocked_intervals: list[tuple[float, float]] | None = None,
) -> float:
    blocked_intervals = _drawio_blocked_intervals_for_vertical_span(
        bounds_by_cell_id,
        excluded_ids=excluded_ids,
        span_start=span_start,
        span_end=span_end,
        padding=padding,
    )
    if extra_blocked_intervals:
        blocked_intervals = blocked_intervals + extra_blocked_intervals
    lower_bound, upper_bound = _drawio_routing_bounds(bounds_by_cell_id, axis="x", padding=padding)
    return _select_drawio_corridor_coordinate(
        blocked_intervals,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        preferred_positions=preferred_positions,
        lane_index=lane_index,
        lane_count=lane_count,
        lane_gap=lane_gap,
    )


def _drawio_blocked_intervals_for_horizontal_span(
    bounds_by_cell_id: dict[str, DrawioCellBounds],
    *,
    excluded_ids: set[str],
    span_start: float,
    span_end: float,
    padding: float,
) -> list[tuple[float, float]]:
    blocked: list[tuple[float, float]] = []
    left = min(span_start, span_end)
    right = max(span_start, span_end)
    for cell_id, bounds in bounds_by_cell_id.items():
        if cell_id in excluded_ids:
            continue
        if bounds.right + padding < left or bounds.left - padding > right:
            continue
        blocked.append((bounds.top - padding, bounds.bottom + padding))
    return blocked


def _drawio_blocked_intervals_for_vertical_span(
    bounds_by_cell_id: dict[str, DrawioCellBounds],
    *,
    excluded_ids: set[str],
    span_start: float,
    span_end: float,
    padding: float,
) -> list[tuple[float, float]]:
    blocked: list[tuple[float, float]] = []
    top = min(span_start, span_end)
    bottom = max(span_start, span_end)
    for cell_id, bounds in bounds_by_cell_id.items():
        if cell_id in excluded_ids:
            continue
        if bounds.bottom + padding < top or bounds.top - padding > bottom:
            continue
        blocked.append((bounds.left - padding, bounds.right + padding))
    return blocked


def _drawio_routing_bounds(
    bounds_by_cell_id: dict[str, DrawioCellBounds],
    *,
    axis: str,
    padding: float,
) -> tuple[float, float]:
    if axis == "x":
        starts = [bounds.left for bounds in bounds_by_cell_id.values()]
        ends = [bounds.right for bounds in bounds_by_cell_id.values()]
    else:
        starts = [bounds.top for bounds in bounds_by_cell_id.values()]
        ends = [bounds.bottom for bounds in bounds_by_cell_id.values()]
    return (min(starts) - (padding * 2), max(ends) + (padding * 2))


def _select_drawio_corridor_coordinate(
    blocked_intervals: list[tuple[float, float]],
    *,
    lower_bound: float,
    upper_bound: float,
    preferred_positions: tuple[float, ...],
    lane_index: int,
    lane_count: int,
    lane_gap: float,
) -> float:
    open_intervals = _drawio_open_intervals(blocked_intervals, lower_bound=lower_bound, upper_bound=upper_bound)
    if not open_intervals:
        return preferred_positions[0]

    preferred_mean = sum(preferred_positions) / len(preferred_positions)
    ranked_intervals = sorted(
        open_intervals,
        key=lambda interval: (
            min(_drawio_interval_distance(interval, position) for position in preferred_positions),
            abs(((interval[0] + interval[1]) / 2) - preferred_mean),
            -(interval[1] - interval[0]),
        ),
    )
    return _drawio_place_in_interval(
        ranked_intervals[0],
        preferred_positions=preferred_positions,
        lane_index=lane_index,
        lane_count=lane_count,
        lane_gap=lane_gap,
    )


def _drawio_open_intervals(
    blocked_intervals: list[tuple[float, float]],
    *,
    lower_bound: float,
    upper_bound: float,
) -> list[tuple[float, float]]:
    if lower_bound > upper_bound:
        lower_bound, upper_bound = upper_bound, lower_bound

    merged: list[tuple[float, float]] = []
    for start, end in sorted(blocked_intervals):
        clipped_start = max(start, lower_bound)
        clipped_end = min(end, upper_bound)
        if clipped_end <= clipped_start:
            continue
        if merged and clipped_start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], clipped_end))
            continue
        merged.append((clipped_start, clipped_end))

    open_intervals: list[tuple[float, float]] = []
    cursor = lower_bound
    for start, end in merged:
        if start > cursor:
            open_intervals.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < upper_bound:
        open_intervals.append((cursor, upper_bound))
    return open_intervals


def _drawio_interval_distance(interval: tuple[float, float], value: float) -> float:
    lower, upper = interval
    return abs(_clamp_drawio_coordinate(value, lower=lower, upper=upper) - value)


def _drawio_place_in_interval(
    interval: tuple[float, float],
    *,
    preferred_positions: tuple[float, ...],
    lane_index: int,
    lane_count: int,
    lane_gap: float,
) -> float:
    route_margin = 8.0
    usable_lower = interval[0] + route_margin
    usable_upper = interval[1] - route_margin
    if usable_lower > usable_upper:
        usable_lower, usable_upper = interval

    base_position = min(
        preferred_positions,
        key=lambda position: (
            abs(_clamp_drawio_coordinate(position, lower=usable_lower, upper=usable_upper) - position),
            abs(position - ((usable_lower + usable_upper) / 2)),
        ),
    )
    lane_offset = 0.0 if lane_count <= 1 else (lane_index - (lane_count - 1) / 2) * lane_gap
    return _clamp_drawio_coordinate(
        base_position + lane_offset,
        lower=usable_lower,
        upper=usable_upper,
    )


def _simplify_drawio_route(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    simplified: list[tuple[float, float]] = []
    for point in points:
        if simplified and point == simplified[-1]:
            continue
        simplified.append(point)

    collapsed: list[tuple[float, float]] = []
    for point in simplified:
        if len(collapsed) < 2:
            collapsed.append(point)
            continue
        prev_prev = collapsed[-2]
        prev = collapsed[-1]
        if (
            abs(prev_prev[0] - prev[0]) < 1e-9
            and abs(prev[0] - point[0]) < 1e-9
        ) or (
            abs(prev_prev[1] - prev[1]) < 1e-9
            and abs(prev[1] - point[1]) < 1e-9
        ):
            collapsed[-1] = point
            continue
        collapsed.append(point)
    return collapsed


def _spread_positions(start: float, end: float, count: int) -> list[float]:
    if count <= 0:
        return []
    if count == 1:
        return [(start + end) / 2]
    span = end - start
    return [start + (span * index / (count - 1)) for index in range(count)]


def _clamp_drawio_coordinate(value: float, *, lower: float, upper: float) -> float:
    if lower > upper:
        return (lower + upper) / 2
    return min(max(value, lower), upper)


def _parse_drawio_number(value: str | None) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)


def _format_drawio_number(value: float) -> str:
    rounded = round(value)
    if abs(value - rounded) < 1e-9:
        return str(int(rounded))
    return f"{value:.2f}".rstrip("0").rstrip(".")
