# ArchAnalyzer

A minimal MVP for analyzing Java/Spring projects and visualizing DDD-style layers.

## Quick Start (Ubuntu 24.04 LTS)

Install system deps and PySide6:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip qt6-base-dev
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Analyze a project and open the viewer in one command:

```bash
python dddvis.py --project /path/to/java-project
```

Analyze only (skip UI):

```bash
python dddvis.py --project /path/to/java-project --no-ui
```

Launch the viewer (manual):

```bash
python -m ui.main
```

Load a sample graph:

```bash
python -m ui.main
# File > Open Graph JSON... -> examples/sample_graph.json
```

Analyze the bundled sample project:

```bash
python dddvis.py --project examples/sample_project
```

## Project Layout

- `analyzer/`: scanner, parser, classifier, and JSON exporter
- `ui/`: PySide6 desktop viewer
- `core/`: shared config and graph loader
- `examples/`: sample graph JSON

## Notes

- Source roots default to `src/main/java`.
- Analysis relies on package names, annotations, and imports (no deep AST parsing).
