from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class LayoutConfig:
    domain_radius: int = 140
    application_radius: int = 340
    ports_radius: int = 460
    adapter_radius: int = 600
    unknown_radius: int = 740
    node_radius: int = 18


LAYER_COLORS: Dict[str, str] = {
    "domain": "#4A74E0",
    "application": "#6BB8A6",
    "inbound_port": "#9A6BB8",
    "outbound_port": "#9A6BB8",
    "inbound_adapter": "#E39A7E",
    "outbound_adapter": "#E39A7E",
    "unknown": "#B5B5B5",
}
