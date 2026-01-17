from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Component:
    id: str
    name: str
    path: str
    package: str
    layer: str
    annotations: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Dependency:
    source_id: str
    target_id: str
    kind: str


@dataclass
class Graph:
    components: List[Component] = field(default_factory=list)
    dependencies: List[Dependency] = field(default_factory=list)
