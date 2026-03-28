import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from archility.cli import main
from archility.render import build_render_steps, format_render_plan, run_render_steps


class RenderTests(unittest.TestCase):
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
            (repo_root / "pyproject.toml").write_text('[project]\nname = "demo-repo"\n')
            (repo_root / "src" / "demo").mkdir(parents=True)
            (repo_root / "src" / "demo" / "__init__.py").write_text("")
            (repo_root / "src" / "demo" / "core.py").write_text("from . import __init__\n")

            steps = build_render_steps(repo_root, archility_root=Path("/tool-home"))

            self.assertEqual(len(steps), 6)
            self.assertEqual(steps[0].tool, "pyreverse")
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


if __name__ == "__main__":
    unittest.main()
