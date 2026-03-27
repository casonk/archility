import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from archility.audit import audit_repo
from archility.cli import main


class AuditTests(unittest.TestCase):
    def test_audit_repo_detects_code_like_blueprint_and_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'AGENTS.md').write_text('agents\n')
            (root / 'LESSONSLEARNED.md').write_text('lessons\n')
            (root / 'pyproject.toml').write_text('[project]\nname = "demo"\n')
            (root / 'src').mkdir()
            (root / 'docs').mkdir()
            (root / 'docs' / 'contributor-architecture-blueprint.md').write_text('blueprint\n')
            (root / 'docs' / 'repo-architecture.puml').write_text('@startuml\n@enduml\n')
            (root / '.github' / 'workflows').mkdir(parents=True)
            (root / '.github' / 'workflows' / 'ci.yml').write_text('name: CI\n')

            result = audit_repo(root)

            self.assertTrue(result.code_like)
            self.assertTrue(result.has_agents)
            self.assertTrue(result.has_lessons)
            self.assertTrue(result.has_blueprint)
            self.assertEqual(result.workflow_count, 1)
            self.assertEqual(result.diagram_count, 1)
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


if __name__ == '__main__':
    unittest.main()
