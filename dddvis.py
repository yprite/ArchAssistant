from __future__ import annotations

import argparse
from pathlib import Path

from cli.commands import analyze_command, open_ui


def main() -> int:
    parser = argparse.ArgumentParser(description="DDD architecture analyzer")
    parser.add_argument("--project", required=True, help="Project root path")
    parser.add_argument("--output", help="Output JSON path")
    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Only analyze and write JSON (skip opening the viewer)",
    )
    args = parser.parse_args()

    project_root = Path(args.project).resolve()
    output_path = Path(args.output).resolve() if args.output else None
    output_path, graph = analyze_command(project_root, output_path)
    print(f"Graph written to {output_path}")

    if args.no_ui:
        return 0

    return open_ui(graph, project_root, watch=True)


if __name__ == "__main__":
    raise SystemExit(main())
