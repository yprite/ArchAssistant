# Repository Guidelines

## Project Structure & Module Organization
- `analyzer/`: scanner, parser, classifier, and JSON exporter for Java/Spring analysis
- `ui/`: PySide6 desktop viewer (main window, scene, items, inspector)
- `core/`: shared configuration and JSON graph loader
- `examples/`: sample graph JSON and a small Java project for testing
- `dddvis.py`: CLI entry point for analyzer runs
- `pyproject.toml`: Python metadata and dependencies

## Build, Test, and Development Commands
- `python dddvis.py --project /path/to/java-project`: analyze and open the viewer in one step
- `python dddvis.py --project /path/to/java-project --no-ui`: analyze only and write `architecture.json`
- `python -m ui.main`: launch the Qt viewer
- `python -m ui.main` then File > Open Graph JSON...: load `examples/sample_graph.json`

Ubuntu 24.04 setup:
- `sudo apt update && sudo apt install -y python3 python3-venv python3-pip qt6-base-dev`
- `python3 -m venv .venv && source .venv/bin/activate && pip install -e .`

## Coding Style & Naming Conventions
- Python 3.10+, 4-space indentation, `snake_case` for functions and files, `PascalCase` for classes.
- Keep parsing and classification rules in `analyzer/` so they remain easy to extend.

## Testing Guidelines
- Testing is not yet set up. If tests are added, prefer `pytest` and place them under `tests/` using `test_*.py` naming.

## Commit & Pull Request Guidelines
- Commit messages: short, imperative summary (e.g., “Add classifier rules for adapters”).
- PRs: include a concise description and link any relevant issues or sample project output.

## Agent-Specific Instructions
- Update `examples/sample_graph.json` if the graph schema changes.
