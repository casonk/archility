"""Public package interface for archility."""

from .audit import RepoAudit, audit_repo, audit_repositories
from .generate import GenerateResult, generate_repo, generate_repositories
from .render import RenderStep, build_render_steps, run_render_steps

__all__ = [
    "GenerateResult",
    "RepoAudit",
    "RenderStep",
    "audit_repo",
    "audit_repositories",
    "build_render_steps",
    "generate_repo",
    "generate_repositories",
    "run_render_steps",
    "__version__",
]

__version__ = "0.1.0"
