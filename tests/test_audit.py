import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from archility.audit import audit_repo
from archility.cli import main


class AuditTests(unittest.TestCase):
    def test_audit_repo_detects_code_like_blueprint_workflow_and_toolchains(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'AGENTS.md').write_text('agents\n')
            (root / 'LESSONSLEARNED.md').write_text('lessons\n')
            (root / 'pyproject.toml').write_text('[project]\nname = "demo"\n')
            (root / 'src').mkdir()
            (root / 'docs' / 'diagrams').mkdir(parents=True)
            (root / 'docs' / 'contributor-architecture-blueprint.md').write_text('blueprint\n')
            (root / 'docs' / 'diagrams' / 'repo-architecture.puml').write_text('@startuml\n@enduml\n')
            (root / 'docs' / 'diagrams' / 'repo-architecture.drawio').write_text('<mxfile />\n')
            (root / 'docs' / 'diagrams' / 'repo-architecture.puml.svg').write_text('<svg />\n')
            (root / 'README.md').write_text('Open in draw.io or diagrams.net.\n')
            (root / 'setup.sh').write_text('inkscape repo-architecture.drawio.svg --export-type=png\n')
            (root / '.github' / 'workflows').mkdir(parents=True)
            (root / '.github' / 'workflows' / 'ci.yml').write_text('name: CI\n')

            result = audit_repo(root)

            self.assertTrue(result.code_like)
            self.assertTrue(result.has_agents)
            self.assertTrue(result.has_lessons)
            self.assertTrue(result.has_blueprint)
            self.assertEqual(result.workflow_count, 1)
            self.assertEqual(result.diagram_count, 3)
            self.assertEqual(result.diagram_source_count, 2)
            self.assertEqual(result.render_artifact_count, 1)
            self.assertEqual(result.diagram_formats, ['.drawio', '.puml', '.svg'])
            self.assertEqual(result.toolchains, ['plantuml', 'drawio', 'inkscape'])
            self.assertEqual(result.recommendations, [])

    def test_audit_repo_recommends_missing_blueprint_for_code_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'AGENTS.md').write_text('agents\n')
            (root / 'LESSONSLEARNED.md').write_text('lessons\n')
            (root / 'src').mkdir()
            (root / 'tests').mkdir()

            result = audit_repo(root)

            self.assertTrue(result.code_like)
            self.assertIn(
                'Add docs/contributor-architecture-blueprint.md for contributor-facing architecture context.',
                result.recommendations,
            )
            self.assertIn('src', result.source_roots)
            self.assertIn('tests', result.source_roots)

    def test_audit_repo_recommends_documenting_toolchain_for_render_only_diagrams(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'AGENTS.md').write_text('agents\n')
            (root / 'LESSONSLEARNED.md').write_text('lessons\n')
            (root / 'docs' / 'diagrams').mkdir(parents=True)
            (root / 'docs' / 'diagrams' / 'repo-architecture.svg').write_text('<svg />\n')

            result = audit_repo(root)

            self.assertEqual(result.diagram_count, 1)
            self.assertEqual(result.diagram_source_count, 0)
            self.assertEqual(result.render_artifact_count, 1)
            self.assertEqual(result.toolchains, [])
            self.assertIn(
                'Document the local architecture-diagram toolchain in README.md or docs/contributor-architecture-blueprint.md so contributors can regenerate the artifacts.',
                result.recommendations,
            )

    def test_cli_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'AGENTS.md').write_text('agents\n')
            (root / 'LESSONSLEARNED.md').write_text('lessons\n')

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = main(['audit', str(root), '--json'])

            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]['path'], str(root.resolve()))
            self.assertFalse(payload[0]['code_like'])
            self.assertEqual(payload[0]['toolchains'], [])
            self.assertEqual(payload[0]['diagram_formats'], [])


if __name__ == '__main__':
    unittest.main()
