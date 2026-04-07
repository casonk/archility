import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from archility.audit import (
    audit_repo,
    collect_python_diagram_targets,
    collect_shell_diagram_targets,
    collect_sql_diagram_targets,
    collect_tooling_diagram_targets,
    write_backlog_items,
)
from archility.cli import main


class AuditTests(unittest.TestCase):
    def test_audit_repo_detects_code_like_blueprint_workflow_and_toolchains(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("agents\n")
            (root / "LESSONSLEARNED.md").write_text("lessons\n")
            (root / "pyproject.toml").write_text('[project]\nname = "demo"\n')
            (root / "src").mkdir()
            (root / "docs" / "diagrams").mkdir(parents=True)
            (root / "docs" / "contributor-architecture-blueprint.md").write_text("blueprint\n")
            (root / "docs" / "diagrams" / "repo-architecture.puml").write_text(
                "@startuml\n@enduml\n"
            )
            (root / "docs" / "diagrams" / "repo-architecture.drawio").write_text("<mxfile />\n")
            (root / "docs" / "diagrams" / "repo-architecture.puml.svg").write_text("<svg />\n")
            (root / "README.md").write_text("Open in draw.io or diagrams.net.\n")
            (root / "setup.sh").write_text(
                "inkscape repo-architecture.drawio.svg --export-type=png\n"
            )
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "workflows" / "ci.yml").write_text("name: CI\n")

            result = audit_repo(root)

            self.assertTrue(result.code_like)
            self.assertTrue(result.has_agents)
            self.assertTrue(result.has_lessons)
            self.assertTrue(result.has_blueprint)
            self.assertEqual(result.workflow_count, 1)
            self.assertEqual(result.diagram_count, 3)
            self.assertEqual(result.diagram_source_count, 2)
            self.assertEqual(result.render_artifact_count, 1)
            self.assertEqual(result.diagram_formats, [".drawio", ".puml", ".svg"])
            self.assertEqual(result.toolchains, ["plantuml", "drawio", "inkscape"])
            self.assertEqual(result.recommendations, [])

    def test_audit_repo_recommends_missing_blueprint_for_code_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("agents\n")
            (root / "LESSONSLEARNED.md").write_text("lessons\n")
            (root / "src").mkdir()
            (root / "tests").mkdir()

            result = audit_repo(root)

            self.assertTrue(result.code_like)
            self.assertIn(
                "Add docs/contributor-architecture-blueprint.md for contributor-facing architecture context.",
                result.recommendations,
            )
            self.assertIn("src", result.source_roots)
            self.assertIn("tests", result.source_roots)

    def test_audit_repo_recommends_documenting_toolchain_for_render_only_diagrams(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("agents\n")
            (root / "LESSONSLEARNED.md").write_text("lessons\n")
            (root / "docs" / "diagrams").mkdir(parents=True)
            (root / "docs" / "diagrams" / "repo-architecture.svg").write_text("<svg />\n")

            result = audit_repo(root)

            self.assertEqual(result.diagram_count, 1)
            self.assertEqual(result.diagram_source_count, 0)
            self.assertEqual(result.render_artifact_count, 1)
            self.assertEqual(result.toolchains, [])
            self.assertIn(
                "Document the local architecture-diagram toolchain in README.md or docs/contributor-architecture-blueprint.md so contributors can regenerate the artifacts.",
                result.recommendations,
            )

    def test_audit_repo_detects_pydeps_and_pyreverse_toolchain_hints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "Use pydeps for import graphs and pyreverse for UML diagrams.\n"
            )
            (root / "setup.sh").write_text("python3 -m pip install pydeps pylint\n")

            result = audit_repo(root)

            self.assertEqual(result.toolchains, ["pydeps", "pyreverse"])

    def test_collect_python_diagram_targets_excludes_tests_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text('[project]\nname = "demo"\n')
            (root / "src" / "demo").mkdir(parents=True)
            (root / "src" / "demo" / "__init__.py").write_text("")
            (root / "src" / "demo" / "core.py").write_text("VALUE = 1\n")
            (root / "tests").mkdir()
            (root / "tests" / "__init__.py").write_text("")
            (root / "tests" / "test_demo.py").write_text("def test_value() -> None:\n    pass\n")

            targets = collect_python_diagram_targets(root)

            self.assertEqual(
                [target.relative_to(root).as_posix() for target in targets],
                ["src/demo"],
            )

    def test_collect_shell_sql_and_tooling_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "deploy.sh").write_text(
                "#!/usr/bin/env bash\ncurl https://example.com\n"
            )
            (root / "db").mkdir()
            (root / "db" / "schema.sql").write_text(
                "CREATE TABLE users (id INTEGER PRIMARY KEY);\n"
            )
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "workflows" / "ci.yml").write_text(
                "jobs:\n  test:\n    steps:\n      - uses: actions/checkout@v4\n"
            )
            (root / "Dockerfile").write_text(
                "FROM python:3.12\nRUN pip install -r requirements.txt\n"
            )

            self.assertEqual(
                [
                    target.relative_to(root).as_posix()
                    for target in collect_shell_diagram_targets(root)
                ],
                ["scripts/deploy.sh"],
            )
            self.assertEqual(
                [
                    target.relative_to(root).as_posix()
                    for target in collect_sql_diagram_targets(root)
                ],
                ["db/schema.sql"],
            )
            self.assertEqual(
                [
                    target.relative_to(root).as_posix()
                    for target in collect_tooling_diagram_targets(root)
                ],
                [".github/workflows/ci.yml", "scripts/deploy.sh", "Dockerfile"],
            )

    def test_cli_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("agents\n")
            (root / "LESSONSLEARNED.md").write_text("lessons\n")

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = main(["audit", str(root), "--json"])

            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]["path"], str(root.resolve()))
            self.assertFalse(payload[0]["code_like"])
            self.assertEqual(payload[0]["toolchains"], [])
            self.assertEqual(payload[0]["diagram_formats"], [])


class WriteBacklogTests(unittest.TestCase):
    def test_creates_backlog_with_recommendations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recs = ["Add AGENTS.md.", "Add LESSONSLEARNED.md."]
            written = write_backlog_items(root, recs, source="archility", date="2026-04-07")

            self.assertEqual(written, 2)
            content = (root / "BACKLOG.md").read_text()
            self.assertIn("- [ ] [archility:2026-04-07] Add AGENTS.md.", content)
            self.assertIn("- [ ] [archility:2026-04-07] Add LESSONSLEARNED.md.", content)

    def test_skips_duplicate_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recs = ["Add AGENTS.md."]
            write_backlog_items(root, recs, source="archility", date="2026-04-01")
            # Re-run with same recommendation — should not duplicate
            written = write_backlog_items(root, recs, source="archility", date="2026-04-07")

            self.assertEqual(written, 0)
            content = (root / "BACKLOG.md").read_text()
            self.assertEqual(content.count("Add AGENTS.md."), 1)

    def test_appends_to_existing_backlog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "BACKLOG.md").write_text(
                "# BACKLOG.md\n\n## Pending\n\n- [ ] [manual:2026-01-01] Existing item.\n\n## Done\n"
            )
            written = write_backlog_items(
                root, ["New item."], source="archility", date="2026-04-07"
            )

            self.assertEqual(written, 1)
            content = (root / "BACKLOG.md").read_text()
            self.assertIn("Existing item.", content)
            self.assertIn("[archility:2026-04-07] New item.", content)
            # New item should appear before Done section
            pending_idx = content.index("## Pending")
            new_idx = content.index("New item.")
            done_idx = content.index("## Done")
            self.assertGreater(new_idx, pending_idx)
            self.assertLess(new_idx, done_idx)

    def test_returns_zero_for_empty_recommendations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            written = write_backlog_items(root, [], source="archility", date="2026-04-07")
            self.assertEqual(written, 0)
            self.assertFalse((root / "BACKLOG.md").exists())

    def test_cli_write_backlog_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # A code-like repo missing blueprint/workflow triggers recommendations
            (root / "pyproject.toml").write_text('[project]\nname = "demo"\n')
            (root / "AGENTS.md").write_text("agents\n")
            (root / "LESSONSLEARNED.md").write_text("lessons\n")

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = main(["audit", str(root), "--write-backlog"])

            self.assertEqual(exit_code, 0)
            self.assertTrue((root / "BACKLOG.md").exists())
            content = (root / "BACKLOG.md").read_text()
            self.assertIn("- [ ] [archility:", content)


if __name__ == "__main__":
    unittest.main()
