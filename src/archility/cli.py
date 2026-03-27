"""CLI entry point for archility."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .audit import audit_repositories, format_text_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='archility',
        description='Audit repositories for architecture documents, workflows, and related baseline artifacts.',
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
    return parser


def handle_audit(args: argparse.Namespace) -> int:
    results = audit_repositories(args.paths)
    if args.json_output:
        payload = [result.to_dict() for result in results]
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(format_text_report(results))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == '__main__':
    raise SystemExit(main())
