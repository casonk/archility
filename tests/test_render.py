import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from xml.etree import ElementTree

from archility.cli import main
from archility.render import build_render_steps, format_render_plan, run_render_steps


class RenderTests(unittest.TestCase):
    def _edge_points(self, drawio: str, edge_id: int) -> list[tuple[int, int]]:
        document = ElementTree.fromstring(drawio)
        for cell in document.iter("mxCell"):
            if cell.attrib.get("id") != str(edge_id):
                continue
            geometry = cell.find("mxGeometry")
            self.assertIsNotNone(geometry, f"edge {edge_id} is missing geometry")
            points = geometry.find("Array")
            if points is None:
                return []
            return [
                (int(float(point.attrib["x"])), int(float(point.attrib["y"])))
                for point in points.findall("mxPoint")
            ]
        self.fail(f"edge {edge_id} not found")

    def test_build_render_steps_for_puml_and_drawio_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "demo"
            (repo_root / "docs" / "diagrams").mkdir(parents=True)
            (repo_root / "docs" / "diagrams" / "repo-architecture.puml").write_text("@startuml\n@enduml\n")
            (repo_root / "docs" / "diagrams" / "repo-architecture.drawio").write_text("<mxfile />\n")

            steps = build_render_steps(repo_root, archility_root=Path("/tool-home"))

            self.assertEqual(len(steps), 4)
            self.assertEqual(steps[0].command, [
                "/tool-home/tools/bin/plantuml",
                "-tsvg",
                str(repo_root / "docs" / "diagrams" / "repo-architecture.puml"),
            ])
            self.assertEqual(
                steps[0].produced_output,
                str(repo_root / "docs" / "diagrams" / "repo-architecture.svg"),
            )
            self.assertEqual(steps[2].command, [
                "/tool-home/tools/bin/drawio",
                "--no-sandbox",
                "-x",
                "-f",
                "svg",
                "-o",
                str(repo_root / "docs" / "diagrams" / "repo-architecture.drawio.svg"),
                str(repo_root / "docs" / "diagrams" / "repo-architecture.drawio"),
            ])
            self.assertEqual(
                steps[2].produced_output,
                str(repo_root / "docs" / "diagrams" / "repo-architecture.drawio.svg"),
            )

    def test_build_render_steps_for_python_repo_adds_pydeps_and_pyreverse(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "demo-repo"
            (repo_root / "docs" / "diagrams").mkdir(parents=True)
            (repo_root / "docs" / "diagrams" / "classes_demo-repo.puml").write_text("@startuml\n@enduml\n")
            (repo_root / "docs" / "diagrams" / "packages_demo-repo.puml").write_text("@startuml\n@enduml\n")
            (repo_root / "pyproject.toml").write_text('[project]\nname = "demo-repo"\n')
            (repo_root / "src" / "demo").mkdir(parents=True)
            (repo_root / "src" / "demo" / "__init__.py").write_text("")
            (repo_root / "src" / "demo" / "core.py").write_text("from . import __init__\n")

            steps = build_render_steps(repo_root, archility_root=Path("/tool-home"))

            self.assertEqual(len(steps), 6)
            self.assertEqual(steps[0].tool, "pyreverse")
            self.assertEqual(
                [Path(step.source).name for step in steps if step.tool == "plantuml"],
                [
                    "python-classes.puml",
                    "python-classes.puml",
                    "python-packages.puml",
                    "python-packages.puml",
                ],
            )
            self.assertEqual(
                steps[0].command,
                [
                    "/tool-home/tools/bin/pyreverse",
                    "--output",
                    "puml",
                    "--output-directory",
                    "docs/diagrams",
                    "--project",
                    "demo-repo",
                    "--source-roots",
                    "src",
                    "src/demo",
                ],
            )
            self.assertEqual(steps[0].cwd, str(repo_root))
            self.assertEqual(
                steps[0].outputs,
                (
                    str(repo_root / "docs" / "diagrams" / "python-classes.puml"),
                    str(repo_root / "docs" / "diagrams" / "python-packages.puml"),
                ),
            )
            self.assertEqual(
                steps[0].produced_outputs,
                (
                    str(repo_root / "docs" / "diagrams" / "classes_demo-repo.puml"),
                    str(repo_root / "docs" / "diagrams" / "packages_demo-repo.puml"),
                ),
            )
            self.assertEqual(
                steps[1].produced_output,
                str(repo_root / "docs" / "diagrams" / "classes_demo-repo.svg"),
            )
            self.assertEqual(
                steps[3].produced_output,
                str(repo_root / "docs" / "diagrams" / "packages_demo-repo.svg"),
            )
            self.assertEqual(steps[-1].tool, "pydeps")
            self.assertEqual(
                steps[-1].command,
                [
                    "/tool-home/tools/bin/pydeps",
                    "--no-config",
                    "--noshow",
                    "--max-bacon",
                    "0",
                    "-T",
                    "svg",
                    "-o",
                    "docs/diagrams/python-import-deps-src-demo.svg",
                    "src/demo",
                ],
            )
            self.assertEqual(
                steps[-1].output,
                str(repo_root / "docs" / "diagrams" / "python-import-deps-src-demo.svg"),
            )

    def test_build_render_steps_for_multiple_python_modules_adds_package_diagram(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "demo-repo"
            (repo_root / "docs" / "diagrams").mkdir(parents=True)
            (repo_root / "pyproject.toml").write_text('[project]\nname = "demo-repo"\n')
            (repo_root / "scripts").mkdir()
            (repo_root / "scripts" / "alpha.py").write_text("import beta\n")
            (repo_root / "beta.py").write_text("VALUE = 1\n")

            steps = build_render_steps(repo_root, archility_root=Path("/tool-home"))

            self.assertEqual(steps[0].tool, "pyreverse")
            self.assertEqual(
                steps[0].outputs,
                (
                    str(repo_root / "docs" / "diagrams" / "python-classes.puml"),
                    str(repo_root / "docs" / "diagrams" / "python-packages.puml"),
                ),
            )
            self.assertEqual(
                steps[0].produced_outputs,
                (
                    str(repo_root / "docs" / "diagrams" / "classes_demo-repo.puml"),
                    str(repo_root / "docs" / "diagrams" / "packages_demo-repo.puml"),
                ),
            )
            self.assertIn(
                [
                    "/tool-home/tools/bin/pydeps",
                    "--no-config",
                    "--noshow",
                    "--max-bacon",
                    "0",
                    "-T",
                    "svg",
                    "-o",
                    "docs/diagrams/python-import-deps-beta.svg",
                    "beta.py",
                ],
                [step.command for step in steps if step.tool == "pydeps"],
            )
            self.assertIn(
                [
                    "/tool-home/tools/bin/pydeps",
                    "--no-config",
                    "--noshow",
                    "--max-bacon",
                    "0",
                    "-T",
                    "svg",
                    "-o",
                    "docs/diagrams/python-import-deps-scripts-alpha.svg",
                    "scripts/alpha.py",
                ],
                [step.command for step in steps if step.tool == "pydeps"],
            )

    def test_format_render_plan_for_empty_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            plan = format_render_plan(repo_root, [])
            self.assertIn("steps: 0", plan)
            self.assertIn("no diagram source files found", plan)

    def test_cli_render_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "demo"
            (repo_root / "docs" / "diagrams").mkdir(parents=True)
            (repo_root / "docs" / "diagrams" / "repo-architecture.puml").write_text("@startuml\n@enduml\n")

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = main(["render", str(repo_root), "--dry-run"])

            output = buffer.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("steps: 2", output)
            self.assertIn("plantuml", output)

    def test_run_render_steps_renames_plantuml_default_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "demo"
            (repo_root / "docs" / "diagrams").mkdir(parents=True)
            source = repo_root / "docs" / "diagrams" / "repo-architecture.puml"
            source.write_text("@startuml\n@enduml\n")
            tool_root = repo_root / "tool-home" / "tools" / "bin"
            tool_root.mkdir(parents=True)
            (tool_root / "plantuml").write_text("#!/usr/bin/env bash\n")
            (tool_root / "drawio").write_text("#!/usr/bin/env bash\n")

            steps = build_render_steps(repo_root, archility_root=repo_root / "tool-home")

            def runner(command: list[str], cwd: str | None) -> None:
                if "-tsvg" in command:
                    (repo_root / "docs" / "diagrams" / "repo-architecture.svg").write_text("<svg />\n")
                elif "-tpng" in command:
                    (repo_root / "docs" / "diagrams" / "repo-architecture.png").write_text("png\n")

            run_render_steps(steps[:2], runner=runner)

            self.assertTrue((repo_root / "docs" / "diagrams" / "repo-architecture.puml.svg").exists())
            self.assertTrue((repo_root / "docs" / "diagrams" / "repo-architecture.puml.png").exists())
            self.assertFalse((repo_root / "docs" / "diagrams" / "repo-architecture.svg").exists())
            self.assertFalse((repo_root / "docs" / "diagrams" / "repo-architecture.png").exists())

    def test_run_render_steps_normalizes_drawio_edge_styles_before_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "demo"
            (repo_root / "docs" / "diagrams").mkdir(parents=True)
            source = repo_root / "docs" / "diagrams" / "repo-architecture.drawio"
            source.write_text(
                """<?xml version="1.0" encoding="utf-8"?>
<mxfile host="app.diagrams.net">
  <diagram id="repo-architecture" name="Repo Architecture">
    <mxGraphModel>
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <mxCell id="10" vertex="1" parent="1">
          <mxGeometry x="520" y="120" width="180" height="80" as="geometry" />
        </mxCell>
        <mxCell id="20" vertex="1" parent="1">
          <mxGeometry x="60" y="120" width="180" height="80" as="geometry" />
        </mxCell>
        <mxCell id="30" vertex="1" parent="1">
          <mxGeometry x="260" y="120" width="180" height="80" as="geometry" />
        </mxCell>
        <mxCell id="500" style="rounded=0;html=0;strokeColor=#1F2937;" edge="1" parent="1" source="10" target="20">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="501" style="rounded=0;html=0;strokeColor=#1F2937;" edge="1" parent="1" source="10" target="30">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
""",
                encoding="utf-8",
            )
            tool_root = repo_root / "tool-home" / "tools" / "bin"
            tool_root.mkdir(parents=True)
            (tool_root / "drawio").write_text("#!/usr/bin/env bash\n")

            steps = build_render_steps(repo_root, archility_root=repo_root / "tool-home")

            def runner(command: list[str], cwd: str | None) -> None:
                output = Path(command[command.index("-o") + 1])
                output.write_text("<svg />\n" if output.suffix == ".svg" else "png\n")

            run_render_steps(steps, runner=runner)

            normalized = source.read_text(encoding="utf-8")
            self.assertIn("jumpStyle=arc", normalized)
            self.assertIn("jumpSize=10", normalized)
            edge_500 = self._edge_points(normalized, 500)
            edge_501 = self._edge_points(normalized, 501)
            self.assertGreaterEqual(len(edge_500), 2)
            self.assertGreaterEqual(len(edge_501), 2)
            self.assertNotEqual(edge_500, edge_501)
            self.assertNotEqual(edge_500[1][1], edge_501[1][1])
            self.assertTrue((repo_root / "docs" / "diagrams" / "repo-architecture.drawio.svg").exists())
            self.assertTrue((repo_root / "docs" / "diagrams" / "repo-architecture.drawio.png").exists())

    def test_run_render_steps_routes_drawio_edges_through_open_corridors(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "demo"
            (repo_root / "docs" / "diagrams").mkdir(parents=True)
            source = repo_root / "docs" / "diagrams" / "repo-architecture.drawio"
            source.write_text(
                """<?xml version="1.0" encoding="utf-8"?>
<mxfile host="app.diagrams.net">
  <diagram id="repo-architecture" name="Repo Architecture">
    <mxGraphModel>
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <mxCell id="10" vertex="1" parent="1">
          <mxGeometry x="720" y="500" width="180" height="100" as="geometry" />
        </mxCell>
        <mxCell id="20" vertex="1" parent="1">
          <mxGeometry x="60" y="260" width="180" height="100" as="geometry" />
        </mxCell>
        <mxCell id="30" vertex="1" parent="1">
          <mxGeometry x="280" y="260" width="180" height="100" as="geometry" />
        </mxCell>
        <mxCell id="40" vertex="1" parent="1">
          <mxGeometry x="500" y="260" width="180" height="100" as="geometry" />
        </mxCell>
        <mxCell id="500" style="rounded=0;html=0;strokeColor=#1F2937;" edge="1" parent="1" source="10" target="20">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
""",
                encoding="utf-8",
            )
            tool_root = repo_root / "tool-home" / "tools" / "bin"
            tool_root.mkdir(parents=True)
            (tool_root / "drawio").write_text("#!/usr/bin/env bash\n")

            steps = build_render_steps(repo_root, archility_root=repo_root / "tool-home")

            def runner(command: list[str], cwd: str | None) -> None:
                output = Path(command[command.index("-o") + 1])
                output.write_text("<svg />\n" if output.suffix == ".svg" else "png\n")

            run_render_steps(steps, runner=runner)

            normalized = source.read_text(encoding="utf-8")
            edge_500 = self._edge_points(normalized, 500)
            self.assertGreaterEqual(len(edge_500), 3)
            corridor_y = next(
                (first[1] for first, second in zip(edge_500, edge_500[1:]) if first[1] == second[1]),
                None,
            )
            self.assertIsNotNone(corridor_y)
            self.assertTrue(corridor_y < 260 or corridor_y > 360)

    def test_run_render_steps_renames_pyreverse_outputs_and_renders_generated_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "demo"
            (repo_root / "docs" / "diagrams").mkdir(parents=True)
            (repo_root / "pyproject.toml").write_text('[project]\nname = "demo"\n')
            (repo_root / "src" / "demo").mkdir(parents=True)
            (repo_root / "src" / "demo" / "__init__.py").write_text("")
            (repo_root / "src" / "demo" / "core.py").write_text("class Demo:\n    pass\n")
            tool_root = repo_root / "tool-home" / "tools" / "bin"
            tool_root.mkdir(parents=True)
            for tool_name in ("plantuml", "pydeps", "pyreverse"):
                (tool_root / tool_name).write_text("#!/usr/bin/env bash\n")

            steps = build_render_steps(repo_root, archility_root=repo_root / "tool-home")

            def runner(command: list[str], cwd: str | None) -> None:
                if command[0].endswith("pyreverse"):
                    (repo_root / "docs" / "diagrams" / "classes_demo.puml").write_text("@startuml\n@enduml\n")
                    (repo_root / "docs" / "diagrams" / "packages_demo.puml").write_text("@startuml\n@enduml\n")
                elif command[0].endswith("pydeps"):
                    (repo_root / "docs" / "diagrams" / "python-import-deps-src-demo.svg").write_text("<svg />\n")
                elif "-tsvg" in command:
                    source_name = Path(command[-1]).name
                    if source_name == "python-classes.puml":
                        (repo_root / "docs" / "diagrams" / "classes_demo.svg").write_text("<svg />\n")
                    elif source_name == "python-packages.puml":
                        (repo_root / "docs" / "diagrams" / "packages_demo.svg").write_text("<svg />\n")
                    else:
                        Path(command[-1].replace(".puml", ".svg")).write_text("<svg />\n")
                elif "-tpng" in command:
                    source_name = Path(command[-1]).name
                    if source_name == "python-classes.puml":
                        (repo_root / "docs" / "diagrams" / "classes_demo.png").write_text("png\n")
                    elif source_name == "python-packages.puml":
                        (repo_root / "docs" / "diagrams" / "packages_demo.png").write_text("png\n")
                    else:
                        Path(command[-1].replace(".puml", ".png")).write_text("png\n")

            run_render_steps(steps, runner=runner)

            self.assertTrue((repo_root / "docs" / "diagrams" / "python-classes.puml").exists())
            self.assertTrue((repo_root / "docs" / "diagrams" / "python-packages.puml").exists())
            self.assertTrue((repo_root / "docs" / "diagrams" / "python-classes.puml.svg").exists())
            self.assertTrue((repo_root / "docs" / "diagrams" / "python-classes.puml.png").exists())
            self.assertTrue((repo_root / "docs" / "diagrams" / "python-packages.puml.svg").exists())
            self.assertTrue((repo_root / "docs" / "diagrams" / "python-packages.puml.png").exists())
            self.assertTrue((repo_root / "docs" / "diagrams" / "python-import-deps-src-demo.svg").exists())
            self.assertFalse((repo_root / "docs" / "diagrams" / "classes_demo.puml").exists())
            self.assertFalse((repo_root / "docs" / "diagrams" / "packages_demo.puml").exists())

    def test_run_render_steps_adds_low_signal_note_for_python_classes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "demo"
            (repo_root / "docs" / "diagrams").mkdir(parents=True)
            (repo_root / "pyproject.toml").write_text('[project]\nname = "demo"\n')
            (repo_root / "refresh.py").write_text(
                "def refresh() -> None:\n"
                "    pass\n",
            )
            tool_root = repo_root / "tool-home" / "tools" / "bin"
            tool_root.mkdir(parents=True)
            for tool_name in ("plantuml", "pydeps", "pyreverse"):
                (tool_root / tool_name).write_text("#!/usr/bin/env bash\n")

            steps = build_render_steps(repo_root, archility_root=repo_root / "tool-home")

            def runner(command: list[str], cwd: str | None) -> None:
                if command[0].endswith("pyreverse"):
                    (repo_root / "docs" / "diagrams" / "classes_demo.puml").write_text(
                        '@startuml classes_demo\nclass "refresh.RefreshJob" as refresh.RefreshJob\n@enduml\n'
                    )
                elif command[0].endswith("pydeps"):
                    (repo_root / "docs" / "diagrams" / "python-import-deps-refresh.svg").write_text("<svg />\n")
                elif "-tsvg" in command:
                    (repo_root / "docs" / "diagrams" / "classes_demo.svg").write_text("<svg />\n")
                elif "-tpng" in command:
                    (repo_root / "docs" / "diagrams" / "classes_demo.png").write_text("png\n")

            run_render_steps(steps, runner=runner)

            normalized = (repo_root / "docs" / "diagrams" / "python-classes.puml").read_text(encoding="utf-8")
            self.assertIn("Minimal class surface detected.", normalized)
            self.assertIn("Scanned 1 Python module.", normalized)
            self.assertIn("python-import-deps-refresh.svg", normalized)

    def test_run_render_steps_rewrites_package_diagram_with_package_summaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "demo"
            (repo_root / "docs" / "diagrams").mkdir(parents=True)
            (repo_root / "pyproject.toml").write_text('[project]\nname = "demo"\n')
            (repo_root / "src" / "demo").mkdir(parents=True)
            (repo_root / "src" / "demo" / "__init__.py").write_text("")
            (repo_root / "src" / "demo" / "cli.py").write_text("def main() -> None:\n    pass\n")
            (repo_root / "src" / "demo" / "core.py").write_text("VALUE = 1\n")
            tool_root = repo_root / "tool-home" / "tools" / "bin"
            tool_root.mkdir(parents=True)
            for tool_name in ("plantuml", "pydeps", "pyreverse"):
                (tool_root / tool_name).write_text("#!/usr/bin/env bash\n")

            steps = build_render_steps(repo_root, archility_root=repo_root / "tool-home")

            def runner(command: list[str], cwd: str | None) -> None:
                if command[0].endswith("pyreverse"):
                    (repo_root / "docs" / "diagrams" / "classes_demo.puml").write_text("@startuml\n@enduml\n")
                    (repo_root / "docs" / "diagrams" / "packages_demo.puml").write_text(
                        "@startuml packages_demo\n"
                        'package "demo" as demo {\n'
                        "}\n"
                        'package "demo.cli" as demo.cli {\n'
                        "}\n"
                        'package "demo.core" as demo.core {\n'
                        "}\n"
                        "demo --> demo.cli\n"
                        "demo --> demo.core\n"
                        "@enduml\n"
                    )
                elif command[0].endswith("pydeps"):
                    (repo_root / "docs" / "diagrams" / "python-import-deps-src-demo.svg").write_text("<svg />\n")
                elif "-tsvg" in command:
                    source_name = Path(command[-1]).name
                    if source_name == "python-classes.puml":
                        (repo_root / "docs" / "diagrams" / "classes_demo.svg").write_text("<svg />\n")
                    else:
                        (repo_root / "docs" / "diagrams" / "packages_demo.svg").write_text("<svg />\n")
                elif "-tpng" in command:
                    source_name = Path(command[-1]).name
                    if source_name == "python-classes.puml":
                        (repo_root / "docs" / "diagrams" / "classes_demo.png").write_text("png\n")
                    else:
                        (repo_root / "docs" / "diagrams" / "packages_demo.png").write_text("png\n")

            run_render_steps(steps, runner=runner)

            normalized = (repo_root / "docs" / "diagrams" / "python-packages.puml").read_text(encoding="utf-8")
            self.assertIn('rectangle "demo\\n0 child pkg, 2 modules\\n3 python files\\nexamples: cli, core" as demo', normalized)
            self.assertIn('rectangle "demo.cli\\n1 python file" as demo.cli', normalized)
            self.assertNotIn('package "demo" as demo {', normalized)

    def test_run_render_steps_rewrites_package_diagram_for_mixed_source_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "demo"
            (repo_root / "docs" / "diagrams").mkdir(parents=True)
            (repo_root / "pyproject.toml").write_text('[project]\nname = "demo"\n')
            (repo_root / "scripts").mkdir()
            (repo_root / "scripts" / "extract_education.py").write_text("def extract() -> None:\n    pass\n")
            (repo_root / "talkmap.py").write_text("def build_map() -> None:\n    pass\n")
            tool_root = repo_root / "tool-home" / "tools" / "bin"
            tool_root.mkdir(parents=True)
            for tool_name in ("plantuml", "pydeps", "pyreverse"):
                (tool_root / tool_name).write_text("#!/usr/bin/env bash\n")

            steps = build_render_steps(repo_root, archility_root=repo_root / "tool-home")

            def runner(command: list[str], cwd: str | None) -> None:
                if command[0].endswith("pyreverse"):
                    (repo_root / "docs" / "diagrams" / "classes_demo.puml").write_text("@startuml\n@enduml\n")
                    (repo_root / "docs" / "diagrams" / "packages_demo.puml").write_text(
                        "@startuml packages_demo\n"
                        'package "scripts.extract_education" as scripts.extract_education {\n'
                        "}\n"
                        'package "talkmap" as talkmap {\n'
                        "}\n"
                        "@enduml\n"
                    )
                elif command[0].endswith("pydeps"):
                    output = repo_root / command[command.index("-o") + 1]
                    output.write_text("<svg />\n")
                elif "-tsvg" in command:
                    source_name = Path(command[-1]).name
                    if source_name == "python-classes.puml":
                        (repo_root / "docs" / "diagrams" / "classes_demo.svg").write_text("<svg />\n")
                    else:
                        (repo_root / "docs" / "diagrams" / "packages_demo.svg").write_text("<svg />\n")
                elif "-tpng" in command:
                    source_name = Path(command[-1]).name
                    if source_name == "python-classes.puml":
                        (repo_root / "docs" / "diagrams" / "classes_demo.png").write_text("png\n")
                    else:
                        (repo_root / "docs" / "diagrams" / "packages_demo.png").write_text("png\n")

            run_render_steps(steps, runner=runner)

            normalized = (repo_root / "docs" / "diagrams" / "python-packages.puml").read_text(encoding="utf-8")
            self.assertIn('rectangle "scripts.extract_education\\n1 python file" as scripts.extract_education', normalized)
            self.assertIn('rectangle "talkmap\\n1 python file" as talkmap', normalized)


if __name__ == "__main__":
    unittest.main()
