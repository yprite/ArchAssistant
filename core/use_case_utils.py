from __future__ import annotations

from typing import List

from analyzer.model import Component, Graph


def is_use_case_entry(component: Component) -> bool:
    if component.layer == "inbound_port":
        return True
    if component.layer == "inbound_adapter" and "controller" in component.name.lower():
        return True
    return False


def find_use_case_entries(graph: Graph) -> List[Component]:
    return [component for component in graph.components if is_use_case_entry(component)]
