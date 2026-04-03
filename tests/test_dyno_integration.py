"""Integration tests for archility using dyno-lab utilities."""

import subprocess
import unittest
from pathlib import Path

from dyno_lab.cli import capture_cli
from dyno_lab.fs import TempWorkdir
from dyno_lab.proc import ProcessRecorder, SubprocessPatch

from archility.audit import audit_repo
from archility.cli import main
from archility.generate import generate_repo
from archility.render import (
    build_render_steps,
    ensure_tools_available,
    format_render_plan,
    run_render_steps,
)


class AuditTempWorkdirTests(unittest.TestCase):
    """audit_repo through a TempWorkdir — no manual cleanup needed."""

    def test_audit_docs_only_repo_has_no_code_like_flag(self):
        with TempWorkdir() as tmp:
            tmp.write("AGENTS.md", "agents\n")
            tmp.write("LESSONSLEARNED.md", "lessons\n")
            tmp.write("README.md", "# Docs only\n")

            result = audit_repo(tmp.path)

        self.assertFalse(result.code_like)
        self.assertEqual(result.source_roots, [])

    def test_audit_recommends_blueprint_when_src_exists_and_blueprint_missing(self):
        with TempWorkdir() as tmp:
            tmp.mkdir("src/mypkg")
            tmp.write("src/mypkg/__init__.py", "")

            result = audit_repo(tmp.path)

        self.assertTrue(result.code_like)
        self.assertIn(
            "Add docs/contributor-architecture-blueprint.md for contributor-facing architecture context.",
            result.recommendations,
        )

    def test_audit_counts_multiple_workflows(self):
        with TempWorkdir() as tmp:
            tmp.mkdir(".github/workflows")
            tmp.write(".github/workflows/ci.yml", "name: CI\n")
            tmp.write(".github/workflows/release.yml", "name: Release\n")
            tmp.write("AGENTS.md", "agents\n")

            result = audit_repo(tmp.path)

        self.assertEqual(result.workflow_count, 2)


class GenerateTempWorkdirTests(unittest.TestCase):
    """generate_repo through a TempWorkdir."""

    def test_generate_creates_three_architecture_files(self):
        with TempWorkdir() as tmp:
            tmp.mkdir("util-repos/archility")
            tmp.mkdir("my-project/src")
            repo_root = tmp.path / "my-project"

            result = generate_repo(
                repo_root, archility_root=tmp.path / "util-repos" / "archility"
            )

        self.assertEqual(len(result.created), 3)
        self.assertIn("docs/contributor-architecture-blueprint.md", result.created)
        self.assertIn("docs/diagrams/repo-architecture.puml", result.created)
        self.assertIn("docs/diagrams/repo-architecture.drawio", result.created)

    def test_generate_skips_existing_files_and_reports_them(self):
        with TempWorkdir() as tmp:
            tmp.mkdir("util-repos/archility")
            tmp.mkdir("my-project/docs/diagrams")
            tmp.write(
                "my-project/docs/contributor-architecture-blueprint.md",
                "# existing\n",
            )
            tmp.write(
                "my-project/docs/diagrams/repo-architecture.puml",
                "@startuml\nexisting\n@enduml\n",
            )
            repo_root = tmp.path / "my-project"

            result = generate_repo(
                repo_root, archility_root=tmp.path / "util-repos" / "archility"
            )

        self.assertNotIn("docs/contributor-architecture-blueprint.md", result.created)
        self.assertNotIn("docs/diagrams/repo-architecture.puml", result.created)
        self.assertIn("docs/diagrams/repo-architecture.drawio", result.created)


class SubprocessPatchRenderTests(unittest.TestCase):
    """render pipeline tested with SubprocessPatch so no real tools are needed."""

    def _make_archility_root_with_tools(self, tmp_path: Path) -> Path:
        """Create a fake archility root with stub tool executables."""
        archility_root = tmp_path / "archility"
        bin_dir = archility_root / "tools" / "bin"
        bin_dir.mkdir(parents=True)
        for name in ("plantuml", "drawio", "inkscape"):
            stub = bin_dir / name
            stub.write_text("#!/bin/sh\necho ok\n")
            stub.chmod(0o755)
        return archility_root

    def test_default_runner_invokes_subprocess_run(self):
        """_default_runner forwards its arguments to subprocess.run."""
        from archility.render import _default_runner

        recorder = ProcessRecorder(default_returncode=0, default_stdout="")

        with SubprocessPatch(recorder, target="archility.render.subprocess.run"):
            _default_runner(["plantuml", "-tsvg", "diagram.puml"], None)

        self.assertEqual(len(recorder.calls), 1)
        self.assertEqual(recorder.calls[0].args[0], "plantuml")

    def test_run_render_steps_subprocess_called_for_puml(self):
        """Patching subprocess.run captures plantuml invocations end-to-end."""
        with TempWorkdir() as tmp:
            archility_root = self._make_archility_root_with_tools(tmp.path)
            repo_root = tmp.path / "demo"
            diag_dir = repo_root / "docs" / "diagrams"
            diag_dir.mkdir(parents=True)
            puml = diag_dir / "repo-architecture.puml"
            puml.write_text("@startuml\n@enduml\n")

            steps = build_render_steps(repo_root, archility_root=archility_root)
            puml_steps = [s for s in steps if s.tool == "plantuml"][:1]

            called: list[list[str]] = []

            def fake_run(args, **kwargs):
                called.append(list(args))
                # Create the expected SVG so _ensure_step_output passes.
                Path(puml_steps[0].produced_outputs[0]).write_text("<svg/>")
                return subprocess.CompletedProcess(args, 0, b"", b"")

            with SubprocessPatch(fake_run, target="archility.render.subprocess.run"):
                run_render_steps(puml_steps)

        self.assertEqual(len(called), 1)
        self.assertIn("plantuml", str(called[0]))

    def test_ensure_tools_available_raises_when_tools_absent(self):
        """ensure_tools_available raises FileNotFoundError for missing binaries."""
        with TempWorkdir() as tmp:
            archility_root = tmp.path / "archility"
            archility_root.mkdir(parents=True)  # tools/bin intentionally absent
            repo_root = tmp.path / "demo"
            (repo_root / "docs" / "diagrams").mkdir(parents=True)
            (repo_root / "docs" / "diagrams" / "repo-architecture.puml").write_text(
                "@startuml\n@enduml\n"
            )

            steps = build_render_steps(repo_root, archility_root=archility_root)
            external = [s for s in steps if not s.is_internal]

        with self.assertRaises(FileNotFoundError):
            ensure_tools_available(external)


class FormatRenderPlanTests(unittest.TestCase):
    def test_format_plan_empty_when_no_diagrams(self):
        with TempWorkdir() as tmp:
            tmp.mkdir("demo/docs/diagrams")
            repo_root = tmp.path / "demo"
            archility_root = tmp.path / "archility"

            steps = build_render_steps(repo_root, archility_root=archility_root)
            plan_text = format_render_plan(repo_root, steps)

        self.assertIn("no diagram source files found", plan_text)

    def test_format_plan_lists_puml_step(self):
        with TempWorkdir() as tmp:
            tmp.mkdir("demo/docs/diagrams")
            tmp.write(
                "demo/docs/diagrams/repo-architecture.puml", "@startuml\n@enduml\n"
            )
            repo_root = tmp.path / "demo"
            archility_root = tmp.path / "archility"

            steps = build_render_steps(repo_root, archility_root=archility_root)
            plan_text = format_render_plan(repo_root, steps)

        self.assertIn("plantuml", plan_text)
        self.assertIn("repo-architecture.puml", plan_text)


class CaptureCLITests(unittest.TestCase):
    def test_capture_cli_audit_text_reports_repo_path(self):
        with TempWorkdir() as tmp:
            tmp.write("AGENTS.md", "agents\n")

            rc, out, err = capture_cli(main, ["audit", str(tmp.path)])

        self.assertEqual(rc, 0)
        self.assertIn(str(tmp.path.resolve()), out)

    def test_capture_cli_audit_json_is_valid(self):
        import json

        with TempWorkdir() as tmp:
            tmp.write("README.md", "# hi\n")

            rc, out, err = capture_cli(main, ["audit", str(tmp.path), "--json"])

        self.assertEqual(rc, 0)
        payload = json.loads(out)
        self.assertIsInstance(payload, list)
        self.assertEqual(len(payload), 1)
        self.assertIn("toolchains", payload[0])


if __name__ == "__main__":
    unittest.main()
