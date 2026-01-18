from __future__ import annotations

from PySide6.QtGui import QColor

from core.config import LAYER_COLORS, ThemeManager


def get_stroke_color() -> QColor:
    return QColor(ThemeManager.get_colors().stroke)


def get_edge_color() -> QColor:
    return QColor(ThemeManager.get_colors().edge)


def get_text_primary() -> QColor:
    return QColor(ThemeManager.get_colors().text_primary)


def get_text_secondary() -> QColor:
    return QColor(ThemeManager.get_colors().text_secondary)


def get_background_color() -> QColor:
    return QColor(ThemeManager.get_colors().background)


# Static colors (legacy compatibility)
STROKE_COLOR = QColor("#4A4A4A")
EDGE_COLOR = QColor("#8A8A8A")
EDGE_HIGHLIGHT = QColor(LAYER_COLORS["domain"])
TEXT_PRIMARY = QColor("#2F2F2F")
TEXT_SECONDARY = QColor("#5A5A5A")

# Flow colors (consistent across themes)
FLOW_ACTIVE = QColor("#3B82F6")
FLOW_VISITED = QColor("#60A5FA")
FLOW_IN = QColor("#93C5FD")
FLOW_DIM = QColor("#CBD5E1")

# Smell colors (consistent across themes)
SMELL_COLORS = {
    "anemic_domain": QColor("#F97316"),
    "god_service": QColor("#EF4444"),
    "repository_leak": QColor("#2563EB"),
    "cross_aggregate_coupling": QColor("#8B5CF6"),
}
