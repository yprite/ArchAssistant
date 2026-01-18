from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from enum import Enum


class Theme(Enum):
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True)
class ThemeColors:
    """Theme-specific color definitions"""
    background: str
    surface: str
    stroke: str
    text_primary: str
    text_secondary: str
    edge: str
    edge_highlight: str


# Light theme (current default)
LIGHT_THEME = ThemeColors(
    background="#F5F5F7",
    surface="#FFFFFF",
    stroke="#4A4A4A",
    text_primary="#2F2F2F",
    text_secondary="#5A5A5A",
    edge="#8A8A8A",
    edge_highlight="#4A74E0",
)

# Dark theme (new)
DARK_THEME = ThemeColors(
    background="#1E1E2E",
    surface="#2D2D3D",
    stroke="#6B6B7B",
    text_primary="#E4E4E7",
    text_secondary="#A1A1AA",
    edge="#71717A",
    edge_highlight="#60A5FA",
)


@dataclass(frozen=True)
class LayoutConfig:
    domain_radius: int = 140
    application_radius: int = 340
    ports_radius: int = 460
    adapter_radius: int = 600
    unknown_radius: int = 740
    node_radius: int = 18


# Layer colors (work with both themes) - 더 구분되는 색상
LAYER_COLORS: Dict[str, str] = {
    "domain": "#3B5DC9",        # 진한 파랑 (핵심)
    "application": "#2E9E83",   # 청록색
    "inbound_port": "#8B5CF6",  # 보라색 (인바운드)
    "outbound_port": "#EC4899", # 분홍색 (아웃바운드)
    "inbound_adapter": "#F59E0B",  # 주황색 (인바운드)
    "outbound_adapter": "#EF4444", # 빨간색 (아웃바운드)
    "unknown": "#6B7280",       # 회색
}

# Dark theme layer colors (더 밝은 톤)
LAYER_COLORS_DARK: Dict[str, str] = {
    "domain": "#6B8FE8",        # 밝은 파랑
    "application": "#5EEAD4",   # 밝은 청록
    "inbound_port": "#A78BFA",  # 밝은 보라
    "outbound_port": "#F472B6", # 밝은 분홍
    "inbound_adapter": "#FBBF24",  # 밝은 주황
    "outbound_adapter": "#F87171", # 밝은 빨강
    "unknown": "#9CA3AF",       # 밝은 회색
}


class ThemeManager:
    """Singleton theme manager for the application"""
    _instance = None
    _current_theme: Theme = Theme.LIGHT
    _listeners: list = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_theme(cls) -> Theme:
        return cls._current_theme

    @classmethod
    def set_theme(cls, theme: Theme) -> None:
        if cls._current_theme != theme:
            cls._current_theme = theme
            for listener in cls._listeners:
                listener(theme)

    @classmethod
    def toggle_theme(cls) -> Theme:
        new_theme = Theme.DARK if cls._current_theme == Theme.LIGHT else Theme.LIGHT
        cls.set_theme(new_theme)
        return new_theme

    @classmethod
    def add_listener(cls, callback) -> None:
        cls._listeners.append(callback)

    @classmethod
    def remove_listener(cls, callback) -> None:
        if callback in cls._listeners:
            cls._listeners.remove(callback)

    @classmethod
    def get_colors(cls) -> ThemeColors:
        return DARK_THEME if cls._current_theme == Theme.DARK else LIGHT_THEME

    @classmethod
    def get_layer_colors(cls) -> Dict[str, str]:
        return LAYER_COLORS_DARK if cls._current_theme == Theme.DARK else LAYER_COLORS
