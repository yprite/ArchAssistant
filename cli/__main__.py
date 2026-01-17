from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cli.commands import analyze_command, load_graph_command, open_ui


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DDD architecture analyzer")
    subparsers = parser.add_subparsers(dest="command")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a project and write JSON")
    analyze_parser.add_argument("project_path", help="Project root path")
    analyze_parser.add_argument("-o", "--output", help="Output JSON path")
    analyze_parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Only analyze and write JSON (skip opening the viewer)",
    )

    open_parser = subparsers.add_parser("open", help="Open a graph JSON in the viewer")
    open_parser.add_argument("graph_path", help="Path to architecture.json")

    args = parser.parse_args(argv)
    if args.command == "analyze":
        output_path, graph = analyze_command(
            Path(args.project_path), Path(args.output) if args.output else None
        )
        print(f"Graph written to {output_path}")
        if args.no_ui:
            return 0
        return open_ui(graph, Path(args.project_path))

    if args.command == "open":
        graph_path = Path(args.graph_path).resolve()
        graph = load_graph_command(graph_path)
        return open_ui(graph, graph_path.parent)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
