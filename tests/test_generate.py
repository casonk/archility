import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from archility.cli import main
from archility.generate import generate_repo


class GenerateTests(unittest.TestCase):
    def test_generate_repo_creates_standard_architecture_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            portfolio_root = Path(tmp) / "portfolio"
            archility_root = portfolio_root / "util-repos" / "archility"
            repo_root = portfolio_root / "demo-repo"
            archility_root.mkdir(parents=True)
            repo_root.mkdir()
            (repo_root / "README.md").write_text("# Demo\n")
            (repo_root / "src").mkdir()
            (repo_root / ".github" / "workflows").mkdir(parents=True)
            (repo_root / ".github" / "workflows" / "ci.yml").write_text("name: CI\n")

            result = generate_repo(repo_root, archility_root=archility_root)

            self.assertEqual(
                result.created,
                [
                    "docs/contributor-architecture-blueprint.md",
                    "docs/diagrams/repo-architecture.puml",
                    "docs/diagrams/repo-architecture.drawio",
                ],
            )
            blueprint = (repo_root / "docs" / "contributor-architecture-blueprint.md").read_text()
            plantuml = (repo_root / "docs" / "diagrams" / "repo-architecture.puml").read_text()
            drawio = (repo_root / "docs" / "diagrams" / "repo-architecture.drawio").read_text()

            self.assertIn("cd ../util-repos/archility", blueprint)
            self.assertIn("python3 -m archility render ../../demo-repo", blueprint)
            self.assertIn("Programmatic path", blueprint)
            self.assertIn("This path is deterministic.", blueprint)
            self.assertIn("This path is intentionally non-deterministic.", blueprint)
            self.assertIn("`src/`", blueprint)
            self.assertIn("title demo-repo Repository Architecture Starter", plantuml)
            self.assertIn("' Deterministic starter generated from repository structure by archility.", plantuml)
            self.assertIn('rectangle "src/" as root_1', plantuml)
            self.assertIn("demo-repo Architecture Starter", drawio)
            self.assertIn("Focus Root&#10;src/", drawio)

    def test_generate_repo_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            portfolio_root = Path(tmp) / "portfolio"
            archility_root = portfolio_root / "util-repos" / "archility"
            repo_root = portfolio_root / "demo-repo"
            archility_root.mkdir(parents=True)
            (repo_root / "docs" / "diagrams").mkdir(parents=True)
            existing_blueprint = repo_root / "docs" / "contributor-architecture-blueprint.md"
            existing_blueprint.write_text("existing blueprint\n")
            existing_puml = repo_root / "docs" / "diagrams" / "repo-architecture.puml"
            existing_puml.write_text("@startuml\nexisting\n@enduml\n")

            result = generate_repo(repo_root, archility_root=archility_root)

            self.assertEqual(
                result.skipped,
                [
                    "docs/contributor-architecture-blueprint.md",
                    "docs/diagrams/repo-architecture.puml",
                ],
            )
            self.assertEqual(existing_blueprint.read_text(), "existing blueprint\n")
            self.assertEqual(existing_puml.read_text(), "@startuml\nexisting\n@enduml\n")
            self.assertTrue((repo_root / "docs" / "diagrams" / "repo-architecture.drawio").exists())

    def test_generate_repo_groups_course_archive_taxonomy(self):
        with tempfile.TemporaryDirectory() as tmp:
            portfolio_root = Path(tmp) / "portfolio"
            archility_root = portfolio_root / "util-repos" / "archility"
            repo_root = portfolio_root / "course-archive"
            archility_root.mkdir(parents=True)
            repo_root.mkdir()
            (repo_root / "README.md").write_text("# Course Archive\n")
            for course_dir in [
                "CSC310-Human_Computer_Interaction",
                "CSC335-Computer_Networks",
                "ECN360-International_Economics",
                "MTH200-Proofs_and_Structures",
                "MTH357-Advanced_Calculus",
                "MTH372-Advanced_Probability",
                "CIS517-Social_Computing",
                "INB385-International_Business",
            ]:
                (repo_root / course_dir).mkdir(parents=True)
            (repo_root / ".github" / "workflows").mkdir(parents=True)
            (repo_root / ".github" / "workflows" / "ci.yml").write_text("name: CI\n")

            generate_repo(repo_root, archility_root=archility_root)

            blueprint = (repo_root / "docs" / "contributor-architecture-blueprint.md").read_text()
            plantuml = (repo_root / "docs" / "diagrams" / "repo-architecture.puml").read_text()
            drawio = (repo_root / "docs" / "diagrams" / "repo-architecture.drawio").read_text()

            self.assertIn("## Current Course Taxonomy", blueprint)
            self.assertIn("### `CSC/` — 2 course directories", blueprint)
            self.assertIn("### `MTH/` — 3 course directories", blueprint)
            self.assertIn("### `INB/` — 1 course directory", blueprint)
            self.assertIn("## Common Nested Deliverable Families", blueprint)
            self.assertIn('rectangle "Course Taxonomy\\n5 subject areas / 8 course directories" as taxonomy_summary', plantuml)
            self.assertIn('package "CSC (2 courses)" #EEF7FF {', plantuml)
            self.assertIn('package "INB (1 course)" #EEF7FF {', plantuml)
            self.assertIn('folder "MTH372-Advanced_Probability/" as mth_3', plantuml)
            self.assertIn("Course Taxonomy&#10;5 subject areas / 8 course directories", drawio)
            self.assertIn("Subject Area&#10;CSC (2 courses)", drawio)
            self.assertIn("Subject Area&#10;INB (1 course)", drawio)
            self.assertIn("MTH357-Advanced_Calculus", drawio)

    def test_cli_generate_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "demo-repo"
            repo_root.mkdir()
            (repo_root / "scripts").mkdir()

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = main(["generate", str(repo_root), "--json"])

            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]["path"], str(repo_root.resolve()))
            self.assertIn("docs/contributor-architecture-blueprint.md", payload[0]["created"])


if __name__ == "__main__":
    unittest.main()
