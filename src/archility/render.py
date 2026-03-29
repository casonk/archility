"""Shared architecture rendering helpers."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import io
from pathlib import Path
import re
import subprocess
from typing import Callable
from xml.etree import ElementTree

from .audit import collect_python_diagram_targets

PLANTUML_SUFFIXES = (".puml", ".plantuml")
DRAWIO_SUFFIXES = (".drawio",)
MANAGED_PYREVERSE_FILENAMES = {"python-classes.puml", "python-packages.puml"}
PYDEPS_PREFIX = "python-import-deps-"
DRAWIO_EDGE_STYLE_DEFAULTS = (
    ("jumpStyle", "arc"),
    ("jumpSize", "10"),
)
LOW_SIGNAL_PYREVERSE_CLASS_THRESHOLD = 1
RunCommand = Callable[[list[str], str | None], None]


@dataclass(slots=True)
class RenderStep:
    tool: str
    source: str
    outputs: tuple[str, ...]
    produced_outputs: tuple[str, ...]
    command: list[str]
    cwd: str | None = None

    @property
    def output(self) -> str:
        return self.outputs[0]

    @property
    def produced_output(self) -> str:
        return self.produced_outputs[0]


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


def find_plantuml_sources(repo_path: str | Path) -> list[Path]:
    repo_root = Path(repo_path).resolve()
    root = diagram_root(repo_path)
    if not root.exists():
        return []
    ignored_filenames = _managed_pyreverse_filenames(repo_root)
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

    return steps


def ensure_tools_available(steps: list[RenderStep]) -> None:
    missing: list[str] = []
    seen: set[str] = set()
    for step in steps:
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


def _managed_pyreverse_filenames(repo_root: Path) -> set[str]:
    project_name = _safe_project_name(repo_root.name)
    return {
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
    bounds_by_cell_id = _drawio_vertex_bounds(root)
    routing_plan = _build_drawio_edge_routes(root, bounds_by_cell_id)
    changed = False

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

    routes: dict[str, list[tuple[float, float]]] = {}
    for edge_id, source_id, target_id, orientation in edges:
        source_bounds = bounds_by_cell_id[source_id]
        target_bounds = bounds_by_cell_id[target_id]
        source_group = source_groups[(source_id, _drawio_source_side(orientation))]
        target_group = target_groups[(target_id, _drawio_target_side(orientation))]
        lane_group = lane_groups[_drawio_lane_group_key(orientation, target_bounds)]
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
) -> list[tuple[float, float]]:
    anchor_margin = 40.0
    clearance = 24.0
    lane_gap = 18.0

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
) -> float:
    blocked_intervals = _drawio_blocked_intervals_for_horizontal_span(
        bounds_by_cell_id,
        excluded_ids=excluded_ids,
        span_start=span_start,
        span_end=span_end,
        padding=padding,
    )
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
) -> float:
    blocked_intervals = _drawio_blocked_intervals_for_vertical_span(
        bounds_by_cell_id,
        excluded_ids=excluded_ids,
        span_start=span_start,
        span_end=span_end,
        padding=padding,
    )
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
