"""Shared architecture rendering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Callable

from .audit import collect_python_diagram_targets

PLANTUML_SUFFIXES = (".puml", ".plantuml")
DRAWIO_SUFFIXES = (".drawio",)
MANAGED_PYREVERSE_FILENAMES = {"python-classes.puml", "python-packages.puml"}
PYDEPS_PREFIX = "python-import-deps-"
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
    if any(_is_package_target(target) for target in targets):
        pyreverse_sources.append(root / "python-packages.puml")
    return PythonDiagramPlan(
        repo_root=repo_root,
        targets=targets,
        pydeps_outputs=pydeps_outputs,
        pyreverse_sources=tuple(pyreverse_sources),
    )


def find_plantuml_sources(repo_path: str | Path) -> list[Path]:
    root = diagram_root(repo_path)
    if not root.exists():
        return []
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in PLANTUML_SUFFIXES
            and path.name not in MANAGED_PYREVERSE_FILENAMES
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
    ensure_tools_available(steps)
    execute = runner or _default_runner
    for step in steps:
        execute(step.command, step.cwd)
        for produced_output, target_output in zip(step.produced_outputs, step.outputs, strict=True):
            _ensure_step_output(step.source, Path(produced_output), Path(target_output))


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
