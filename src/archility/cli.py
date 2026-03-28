"""CLI entry point for archility."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .audit import audit_repositories, format_text_report
from .generate import format_generate_report, generate_repositories
from .render import build_render_steps, format_render_plan, run_render_steps


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='archility',
        description=(
            'Audit repositories for architecture artifacts, generate deterministic starter diagrams, '
            'and render both programmatic and agent-authored architecture sources.'
        ),
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    audit_parser = subparsers.add_parser(
        'audit',
        help='Audit one or more repositories for architecture-related baseline artifacts.',
    )
    audit_parser.add_argument(
        'paths',
        nargs='*',
        default=['.'],
        help='Repository paths to inspect. Defaults to the current directory.',
    )
    audit_parser.add_argument(
        '--json',
        action='store_true',
        dest='json_output',
        help='Emit machine-readable JSON instead of text output.',
    )
    audit_parser.set_defaults(handler=handle_audit)

    generate_parser = subparsers.add_parser(
        'generate',
        help=(
            'Programmatically scaffold the deterministic starter architecture blueprint and '
            'diagram-source layout for one or more repositories.'
        ),
    )
    generate_parser.add_argument(
        'paths',
        nargs='*',
        default=['.'],
        help='Repository paths to scaffold. Defaults to the current directory.',
    )
    generate_parser.add_argument(
        '--json',
        action='store_true',
        dest='json_output',
        help='Emit machine-readable JSON instead of text output.',
    )
    generate_parser.add_argument(
        '--render',
        action='store_true',
        help='Render the generated or existing diagram sources after scaffolding.',
    )
    generate_parser.set_defaults(handler=handle_generate)

    render_parser = subparsers.add_parser(
        'render',
        help='Render PlantUML and draw.io diagrams in a target repository using archility-managed tools.',
    )
    render_parser.add_argument(
        'repo_path',
        help='Repository path whose docs/diagrams sources should be rendered.',
    )
    render_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print the planned render commands without executing them.',
    )
    render_parser.set_defaults(handler=handle_render)
    return parser


def handle_audit(args: argparse.Namespace) -> int:
    results = audit_repositories(args.paths)
    if args.json_output:
        payload = [result.to_dict() for result in results]
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(format_text_report(results))
    return 0


def handle_generate(args: argparse.Namespace) -> int:
    results = generate_repositories(args.paths, render=args.render)
    if args.json_output:
        payload = [result.to_dict() for result in results]
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(format_generate_report(results))
    return 0


def handle_render(args: argparse.Namespace) -> int:
    steps = build_render_steps(args.repo_path)
    if args.dry_run:
        print(format_render_plan(args.repo_path, steps))
        return 0
    if not steps:
        print(format_render_plan(args.repo_path, steps))
        return 0
    run_render_steps(steps)
    print(format_render_plan(args.repo_path, steps))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == '__main__':
    raise SystemExit(main())
