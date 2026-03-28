"""Shared architecture rendering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Callable

PLANTUML_SUFFIXES = (".puml", ".plantuml")
DRAWIO_SUFFIXES = (".drawio",)
RunCommand = Callable[[list[str]], None]


@dataclass(slots=True)
class RenderStep:
    tool: str
    source: str
    output: str
    produced_output: str
    command: list[str]


def package_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def diagram_root(repo_path: str | Path) -> Path:
    return Path(repo_path).resolve() / "docs" / "diagrams"


def find_plantuml_sources(repo_path: str | Path) -> list[Path]:
    root = diagram_root(repo_path)
    if not root.exists():
        return []
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in PLANTUML_SUFFIXES),
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

    steps: list[RenderStep] = []
    for source in find_plantuml_sources(repo_root):
        source_str = str(source)
        steps.append(
            RenderStep(
                tool="plantuml",
                source=source_str,
                output=source_str + ".svg",
                produced_output=str(source.with_suffix(".svg")),
                command=[plantuml_bin, "-tsvg", source_str],
            )
        )
        steps.append(
            RenderStep(
                tool="plantuml",
                source=source_str,
                output=source_str + ".png",
                produced_output=str(source.with_suffix(".png")),
                command=[plantuml_bin, "-tpng", source_str],
            )
        )

    for source in find_drawio_sources(repo_root):
        source_str = str(source)
        steps.append(
            RenderStep(
                tool="drawio",
                source=source_str,
                output=source_str + ".svg",
                produced_output=source_str + ".svg",
                command=[drawio_bin, "--no-sandbox", "-x", "-f", "svg", "-o", source_str + ".svg", source_str],
            )
        )
        steps.append(
            RenderStep(
                tool="drawio",
                source=source_str,
                output=source_str + ".png",
                produced_output=source_str + ".png",
                command=[drawio_bin, "--no-sandbox", "-x", "-f", "png", "-o", source_str + ".png", source_str],
            )
        )

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
        execute(step.command)
        produced_path = Path(step.produced_output)
        target_path = Path(step.output)
        if produced_path != target_path and produced_path.exists():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            produced_path.replace(target_path)
        if not target_path.exists():
            raise FileNotFoundError(
                f"Expected render output was not produced for {step.source}: {target_path}"
            )


def _default_runner(command: list[str]) -> None:
    subprocess.run(command, check=True)


def format_render_plan(repo_path: str | Path, steps: list[RenderStep]) -> str:
    repo_root = Path(repo_path).resolve()
    lines = [f"repo: {repo_root}", f"steps: {len(steps)}"]
    if not steps:
        lines.append("  no diagram source files found under docs/diagrams")
        return "\n".join(lines)
    for step in steps:
        lines.append(
            f"  - {step.tool}: {Path(step.source).name} -> {Path(step.output).name}"
        )
        lines.append("    command: " + " ".join(step.command))
    return "\n".join(lines)
