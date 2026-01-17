from __future__ import annotations

import math
from typing import Dict, Iterable, List

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsPolygonItem, QGraphicsScene

from analyzer.model import Component, Dependency, Graph
from core.config import LAYER_COLORS, LayoutConfig
from ui.component_item import ComponentItem
from ui.edge_item import EdgeItem
from ui.colors import STROKE_COLOR


class ArchitectureScene(QGraphicsScene):
    def __init__(self, layout: LayoutConfig | None = None) -> None:
        super().__init__()
        self.layout = layout or LayoutConfig()
        self.component_items: Dict[str, ComponentItem] = {}
        self.layer_items: Dict[str, List[ComponentItem]] = {}
        self.layer_backgrounds: Dict[str, List[QGraphicsPolygonItem | QGraphicsPathItem]] = {}
        self.component_edges: Dict[str, List[EdgeItem]] = {}
        self.component_edges_in: Dict[str, List[EdgeItem]] = {}
        self.component_edges_out: Dict[str, List[EdgeItem]] = {}
        self.edge_items: List[EdgeItem] = []
        self.active_component_id: str | None = None

    def load_graph(self, graph: Graph) -> None:
        self.clear()
        self.component_items.clear()
        self.layer_items.clear()
        self.layer_backgrounds.clear()
        self.component_edges.clear()
        self.component_edges_in.clear()
        self.component_edges_out.clear()
        self.edge_items.clear()
        self.active_component_id = None

        self.draw_layer_backgrounds()
        self._create_nodes(graph.components)
        self._create_edges(graph.dependencies)

    def set_layer_visible(self, layer: str, visible: bool) -> None:
        for item in self.layer_items.get(layer, []):
            item.setVisible(visible)
        for item in self.layer_backgrounds.get(layer, []):
            item.setVisible(visible)

    def set_layer_opacity(self, layer: str, opacity: float) -> None:
        for item in self.layer_items.get(layer, []):
            item.setOpacity(opacity)
        for item in self.layer_backgrounds.get(layer, []):
            item.setOpacity(opacity)

    def draw_layer_backgrounds(self) -> None:
        scene_radius = self.layout.unknown_radius + 220
        self.setSceneRect(-scene_radius, -scene_radius, scene_radius * 2, scene_radius * 2)

        self.create_domain_hexagon()
        self.create_application_hex_ring()
        self.create_ports_hex_ring()
        self.create_adapter_sectors()
        self._create_unknown_ring()
        self._create_unknown_cluster()

    def graph_bounds(self):
        return self.itemsBoundingRect()

    def create_domain_hexagon(self) -> None:
        radius = self.layout.domain_radius
        polygon = self._hex_polygon(QPointF(0, 0), radius)
        fill_item = QGraphicsPolygonItem(polygon)
        fill_item.setBrush(self._layer_gradient(LAYER_COLORS["domain"], radius))
        fill_item.setPen(Qt.PenStyle.NoPen)
        fill_item.setZValue(-100)
        self.addItem(fill_item)

        outline = QGraphicsPolygonItem(polygon)
        outline.setBrush(Qt.BrushStyle.NoBrush)
        outline.setPen(self._outline_pen(2.0))
        outline.setZValue(-90)
        self._apply_hex_shadow(outline)
        self.addItem(outline)
        self.layer_backgrounds.setdefault("domain", []).extend([fill_item, outline])

    def create_application_hex_ring(self) -> None:
        inner_radius = self.layout.domain_radius + 40
        outer_radius = self.layout.application_radius
        inner = self._hex_polygon(QPointF(0, 0), inner_radius)
        outer = self._hex_polygon(QPointF(0, 0), outer_radius)

        path = QPainterPath()
        path.addPolygon(outer)
        path.addPolygon(inner)
        path.setFillRule(Qt.FillRule.OddEvenFill)

        fill_item = QGraphicsPathItem(path)
        fill_item.setBrush(self._layer_gradient(LAYER_COLORS["application"], outer_radius))
        fill_item.setPen(Qt.PenStyle.NoPen)
        fill_item.setZValue(-99)
        self.addItem(fill_item)

        outer_outline = QGraphicsPolygonItem(outer)
        outer_outline.setBrush(Qt.BrushStyle.NoBrush)
        outer_outline.setPen(self._outline_pen(1.6))
        outer_outline.setZValue(-91)
        self._apply_hex_shadow(outer_outline)
        self.addItem(outer_outline)

        inner_outline = QGraphicsPolygonItem(inner)
        inner_outline.setBrush(Qt.BrushStyle.NoBrush)
        inner_outline.setPen(self._outline_pen(1.6))
        inner_outline.setZValue(-91)
        self._apply_hex_shadow(inner_outline)
        self.addItem(inner_outline)
        self.layer_backgrounds.setdefault("application", []).extend(
            [fill_item, outer_outline, inner_outline]
        )

    def create_ports_hex_ring(self) -> None:
        inner_radius = self.layout.application_radius + 30
        outer_radius = self.layout.ports_radius
        inner = self._hex_polygon(QPointF(0, 0), inner_radius)
        outer = self._hex_polygon(QPointF(0, 0), outer_radius)

        path = QPainterPath()
        path.addPolygon(outer)
        path.addPolygon(inner)
        path.setFillRule(Qt.FillRule.OddEvenFill)

        fill_item = QGraphicsPathItem(path)
        fill_item.setBrush(self._layer_gradient(LAYER_COLORS["inbound_port"], outer_radius))
        fill_item.setPen(Qt.PenStyle.NoPen)
        fill_item.setZValue(-98.8)
        self.addItem(fill_item)

        outer_outline = QGraphicsPolygonItem(outer)
        outer_outline.setBrush(Qt.BrushStyle.NoBrush)
        outer_outline.setPen(self._outline_pen(1.4))
        outer_outline.setZValue(-90.5)
        self._apply_hex_shadow(outer_outline)
        self.addItem(outer_outline)

        inner_outline = QGraphicsPolygonItem(inner)
        inner_outline.setBrush(Qt.BrushStyle.NoBrush)
        inner_outline.setPen(self._outline_pen(1.4))
        inner_outline.setZValue(-90.5)
        self._apply_hex_shadow(inner_outline)
        self.addItem(inner_outline)
        self.layer_backgrounds.setdefault("ports", []).extend(
            [fill_item, outer_outline, inner_outline]
        )

    def create_adapter_sectors(self) -> None:
        inner_radius = self.layout.ports_radius + 30
        outer_radius = self.layout.adapter_radius
        inner = self._hex_points(QPointF(0, 0), inner_radius)
        outer = self._hex_points(QPointF(0, 0), outer_radius)

        inbound_color = QColor(LAYER_COLORS["inbound_adapter"])
        outbound_color = QColor(LAYER_COLORS["outbound_adapter"])
        neutral_color = QColor(LAYER_COLORS["unknown"])

        outline = QGraphicsPolygonItem(self._hex_polygon(QPointF(0, 0), outer_radius))
        outline.setBrush(Qt.BrushStyle.NoBrush)
        outline.setPen(self._outline_pen(1.2))
        outline.setZValue(-92)
        self._apply_hex_shadow(outline)
        self.addItem(outline)
        self.layer_backgrounds.setdefault("adapter_zone", []).append(outline)

        for side in range(6):
            polygon = self._sector_polygon(inner, outer, side)
            item = QGraphicsPolygonItem(polygon)
            if side in (2, 3):
                color = inbound_color
            elif side in (0, 5):
                color = outbound_color
            else:
                color = neutral_color
            item.setBrush(self._with_alpha(color, 0.04))
            pen = QPen(STROKE_COLOR)
            pen.setWidthF(0.9)
            pen.setCosmetic(True)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            item.setPen(pen)
            item.setZValue(-98)
            self.addItem(item)
            if side in (2, 3):
                layer_key = "inbound_adapter"
            elif side in (0, 5):
                layer_key = "outbound_adapter"
            else:
                layer_key = "adapter_zone"
            self.layer_backgrounds.setdefault(layer_key, []).append(item)

    def _create_unknown_ring(self) -> None:
        inner_radius = self.layout.adapter_radius + 40
        outer_radius = self.layout.unknown_radius
        inner = self._hex_polygon(QPointF(0, 0), inner_radius)
        outer = self._hex_polygon(QPointF(0, 0), outer_radius)

        path = QPainterPath()
        path.addPolygon(outer)
        path.addPolygon(inner)
        path.setFillRule(Qt.FillRule.OddEvenFill)

        fill_item = QGraphicsPathItem(path)
        fill_item.setBrush(self._layer_gradient(LAYER_COLORS["unknown"], outer_radius))
        fill_item.setPen(Qt.PenStyle.NoPen)
        fill_item.setZValue(-97)
        self.addItem(fill_item)

        outline = QGraphicsPolygonItem(outer)
        outline.setBrush(Qt.BrushStyle.NoBrush)
        outline.setPen(self._outline_pen(1.0))
        outline.setZValue(-93)
        self._apply_hex_shadow(outline)
        self.addItem(outline)
        self.layer_backgrounds.setdefault("unknown", []).extend([fill_item, outline])

    def _create_unknown_cluster(self) -> None:
        radius = self.layout.unknown_radius + 80
        path = QPainterPath()
        center = QPointF(0, radius)
        path.addEllipse(center, 120, 60)
        item = QGraphicsPathItem(path)
        item.setBrush(self._with_alpha(LAYER_COLORS["unknown"], 0.08))
        pen = QPen(STROKE_COLOR)
        pen.setWidthF(0.8)
        pen.setCosmetic(True)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        item.setPen(pen)
        item.setZValue(-96)
        self.addItem(item)
        self.layer_backgrounds.setdefault("unknown", []).append(item)

    def _create_nodes(self, components: List[Component]) -> None:
        positions = self._layout_nodes_by_layer(components)
        for component in components:
            item = ComponentItem(component, self.layout)
            item.setPos(positions.get(component.id, QPointF(0, 0)))
            item.setZValue(10)
            self.addItem(item)
            self.component_items[component.id] = item
            self.layer_items.setdefault(component.layer, []).append(item)
            item.hovered.connect(self._handle_component_hover)

    def _create_edges(self, dependencies: Iterable[Dependency]) -> None:
        for dep in dependencies:
            source_item = self.component_items.get(dep.source_id)
            target_item = self.component_items.get(dep.target_id)
            if not source_item or not target_item:
                continue
            edge = EdgeItem(source_item, target_item)
            edge.setZValue(0)
            self.addItem(edge)
            self.component_edges.setdefault(dep.source_id, []).append(edge)
            self.component_edges.setdefault(dep.target_id, []).append(edge)
            self.component_edges_out.setdefault(dep.source_id, []).append(edge)
            self.component_edges_in.setdefault(dep.target_id, []).append(edge)
            self.edge_items.append(edge)

    def _layout_nodes_by_layer(self, components: List[Component]) -> Dict[str, QPointF]:
        layers: Dict[str, List[Component]] = {}
        for component in components:
            layers.setdefault(component.layer, []).append(component)

        positions: Dict[str, QPointF] = {}
        positions.update(self.layout_domain_nodes(layers.get("domain", [])))
        positions.update(self.layout_application_nodes(layers.get("application", [])))
        positions.update(
            self.layout_port_nodes(
                layers.get("inbound_port", []), layers.get("outbound_port", [])
            )
        )
        positions.update(
            self.layout_adapter_nodes(
                layers.get("inbound_adapter", []), layers.get("outbound_adapter", [])
            )
        )
        positions.update(self.layout_unknown_nodes(layers.get("unknown", [])))
        return positions

    def layout_domain_nodes(self, components: List[Component]) -> Dict[str, QPointF]:
        if not components:
            return {}
        positions: Dict[str, QPointF] = {}
        base_radius = self.layout.domain_radius * 0.35
        ring_gap = 26
        for idx, component in enumerate(components):
            ring = idx // 6
            ring_radius = base_radius + ring * ring_gap
            ring_items = min(6, len(components) - ring * 6)
            sectors = max(ring_items, 6)
            angle = -math.pi / 2 + (idx % 6) * (2 * math.pi / sectors)
            x = math.cos(angle) * ring_radius
            y = math.sin(angle) * ring_radius
            positions[component.id] = QPointF(x, y)
        return positions

    def layout_application_nodes(self, components: List[Component]) -> Dict[str, QPointF]:
        if not components:
            return {}
        inner_radius = self.layout.domain_radius + 40
        outer_radius = self.layout.application_radius
        mid_radius = (inner_radius + outer_radius) / 2
        positions: Dict[str, QPointF] = {}
        sectors = max(len(components), 6)
        angle_step = 2 * math.pi / sectors
        for idx, component in enumerate(components):
            angle = -math.pi / 2 + idx * angle_step
            x = math.cos(angle) * mid_radius
            y = math.sin(angle) * mid_radius
            positions[component.id] = QPointF(x, y)
        return positions

    def layout_adapter_nodes(
        self, inbound: List[Component], outbound: List[Component]
    ) -> Dict[str, QPointF]:
        positions: Dict[str, QPointF] = {}
        inner_radius = self.layout.ports_radius + 30
        outer_radius = self.layout.adapter_radius - 20
        mid_radius = (inner_radius + outer_radius) / 2

        positions.update(self._place_on_side_arcs(inbound, mid_radius, sides=[2, 3]))
        positions.update(self._place_on_side_arcs(outbound, mid_radius, sides=[0, 5]))
        return positions

    def layout_unknown_nodes(self, components: List[Component]) -> Dict[str, QPointF]:
        if not components:
            return {}
        radius = self.layout.unknown_radius + 90
        positions: Dict[str, QPointF] = {}
        angle_start = math.radians(210)
        angle_span = math.radians(120)
        count = len(components)
        for idx, component in enumerate(components):
            if count == 1:
                angle = angle_start + angle_span / 2
            else:
                angle = angle_start + (angle_span / (count - 1)) * idx
            x = math.cos(angle) * radius
            y = math.sin(angle) * radius
            positions[component.id] = QPointF(x, y)
        return positions

    def layout_port_nodes(
        self, inbound: List[Component], outbound: List[Component]
    ) -> Dict[str, QPointF]:
        positions: Dict[str, QPointF] = {}
        inner_radius = self.layout.application_radius + 30
        outer_radius = self.layout.ports_radius
        mid_radius = (inner_radius + outer_radius) / 2
        positions.update(
            self._place_on_arc(inbound, mid_radius, math.radians(150), math.radians(330))
        )
        positions.update(
            self._place_on_arc(outbound, mid_radius, math.radians(-30), math.radians(150))
        )
        return positions

    def _handle_component_hover(self, component: Component, hovered: bool) -> None:
        if hovered:
            self._reset_edge_highlights()
            self._highlight_edges_for(component.id)
        else:
            self._reset_edge_highlights()
            if self.active_component_id:
                self._highlight_edges_for(self.active_component_id)

    def set_active_component(self, component_id: str | None) -> None:
        if self.active_component_id == component_id:
            return
        if self.active_component_id and self.active_component_id in self.component_items:
            self.component_items[self.active_component_id].set_active(False)
        self.active_component_id = component_id
        self._reset_edge_highlights()
        if component_id and component_id in self.component_items:
            self.component_items[component_id].set_active(True)
            self._highlight_edges_for(component_id)

    def _highlight_edges_for(self, component_id: str) -> None:
        edges = set(self.component_edges_in.get(component_id, []))
        edges.update(self.component_edges_out.get(component_id, []))
        for edge in edges:
            edge.set_highlighted(True)

    def _reset_edge_highlights(self) -> None:
        for edge in self.edge_items:
            edge.set_highlighted(False)

    def _place_on_side_arcs(
        self, components: List[Component], radius: float, sides: List[int]
    ) -> Dict[str, QPointF]:
        if not components:
            return {}
        positions: Dict[str, QPointF] = {}
        buckets: Dict[int, List[Component]] = {side: [] for side in sides}
        for idx, component in enumerate(components):
            buckets[sides[idx % len(sides)]].append(component)

        for side in sides:
            items = buckets.get(side, [])
            if not items:
                continue
            start_angle = math.radians(side * 60 - 30)
            end_angle = math.radians(side * 60 + 30)
            for idx, component in enumerate(items):
                if len(items) == 1:
                    angle = (start_angle + end_angle) / 2
                else:
                    angle = start_angle + (end_angle - start_angle) * (idx / (len(items) - 1))
                x = math.cos(angle) * radius
                y = math.sin(angle) * radius
                positions[component.id] = QPointF(x, y)
        return positions

    def _place_on_arc(
        self, components: List[Component], radius: float, start_angle: float, end_angle: float
    ) -> Dict[str, QPointF]:
        if not components:
            return {}
        positions: Dict[str, QPointF] = {}
        count = len(components)
        for idx, component in enumerate(components):
            if count == 1:
                angle = (start_angle + end_angle) / 2
            else:
                angle = start_angle + (end_angle - start_angle) * (idx / (count - 1))
            x = math.cos(angle) * radius
            y = math.sin(angle) * radius
            positions[component.id] = QPointF(x, y)
        return positions

    def _hex_points(self, center: QPointF, radius: float) -> List[QPointF]:
        points: List[QPointF] = []
        for i in range(6):
            angle = math.radians(60 * i - 30)
            points.append(
                QPointF(
                    center.x() + math.cos(angle) * radius,
                    center.y() + math.sin(angle) * radius,
                )
            )
        return points

    def _outline_pen(self, width: float) -> QPen:
        pen = QPen(STROKE_COLOR)
        pen.setWidthF(width)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return pen

    def _layer_gradient(self, color: str, radius: float) -> QLinearGradient:
        base = QColor(color)
        gradient = QLinearGradient(0, -radius, 0, radius)
        top = QColor(base)
        top.setAlphaF(0.06)
        bottom = QColor(base)
        bottom.setAlphaF(0.02)
        gradient.setColorAt(0, top)
        gradient.setColorAt(1, bottom)
        return gradient

    def _apply_hex_shadow(self, item: QGraphicsPolygonItem) -> None:
        effect = item.graphicsEffect()
        if effect is not None:
            return
        from PySide6.QtWidgets import QGraphicsDropShadowEffect

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(4)
        shadow.setOffset(0, 1)
        shadow_color = QColor("#000000")
        shadow_color.setAlphaF(0.12)
        shadow.setColor(shadow_color)
        item.setGraphicsEffect(shadow)

    def _hex_polygon(self, center: QPointF, radius: float) -> QPolygonF:
        return QPolygonF(self._hex_points(center, radius))

    def _sector_polygon(
        self, inner: List[QPointF], outer: List[QPointF], side: int
    ) -> QPolygonF:
        return QPolygonF(
            [
                outer[side],
                outer[(side + 1) % 6],
                inner[(side + 1) % 6],
                inner[side],
            ]
        )

    def _hex_grid_points(self, radius: float, spacing: float) -> List[QPointF]:
        points: List[QPointF] = []
        extent = radius
        polygon = self._hex_points(QPointF(0, 0), radius)
        for x in self._frange(-extent, extent, spacing):
            for y in self._frange(-extent, extent, spacing):
                point = QPointF(x, y)
                if self._point_in_polygon(point, polygon):
                    points.append(point)
        if not points:
            points.append(QPointF(0, 0))
        return points

    def _point_in_polygon(self, point: QPointF, polygon: List[QPointF]) -> bool:
        inside = False
        j = len(polygon) - 1
        for i in range(len(polygon)):
            xi, yi = polygon[i].x(), polygon[i].y()
            xj, yj = polygon[j].x(), polygon[j].y()
            if ((yi > point.y()) != (yj > point.y())) and (
                point.x()
                < (xj - xi) * (point.y() - yi) / (yj - yi + 1e-6) + xi
            ):
                inside = not inside
            j = i
        return inside

    def _frange(self, start: float, stop: float, step: float) -> Iterable[float]:
        value = start
        while value <= stop:
            yield value
            value += step

    def _lerp_point(self, a: QPointF, b: QPointF, t: float) -> QPointF:
        return QPointF(a.x() + (b.x() - a.x()) * t, a.y() + (b.y() - a.y()) * t)

    def _spread_t(self, idx: int, count: int) -> float:
        if count <= 1:
            return 0.5
        return 0.2 + 0.6 * (idx / (count - 1))

    def _with_alpha(self, color: str | QColor, alpha: float) -> QColor:
        base = QColor(color) if isinstance(color, str) else QColor(color)
        base.setAlphaF(alpha)
        return base
