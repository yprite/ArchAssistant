from __future__ import annotations

import math
from typing import Dict, Iterable, List

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsPolygonItem, QGraphicsScene

from analyzer.model import Component, Dependency, Graph
from core.config import LAYER_COLORS, LayoutConfig
from core.flow import FlowResult
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
        self.edge_lookup: Dict[tuple[str, str], EdgeItem] = {}
        self.active_component_id: str | None = None
        self.flow_active = False
        self.flow_token_pos: QPointF | None = None

    def load_graph(self, graph: Graph) -> None:
        self.clear()
        self.component_items.clear()
        self.layer_items.clear()
        self.layer_backgrounds.clear()
        self.component_edges.clear()
        self.component_edges_in.clear()
        self.component_edges_out.clear()
        self.edge_items.clear()
        self.edge_lookup.clear()
        self.active_component_id = None
        self.flow_active = False

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
        fill_item.setCacheMode(QGraphicsPolygonItem.CacheMode.DeviceCoordinateCache)
        self.addItem(fill_item)

        outline = QGraphicsPolygonItem(polygon)
        outline.setBrush(Qt.BrushStyle.NoBrush)
        outline.setPen(self._outline_pen(2.0))
        outline.setZValue(-90)
        outline.setCacheMode(QGraphicsPolygonItem.CacheMode.DeviceCoordinateCache)
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
        fill_item.setCacheMode(QGraphicsPathItem.CacheMode.DeviceCoordinateCache)
        self.addItem(fill_item)

        outer_outline = QGraphicsPolygonItem(outer)
        outer_outline.setBrush(Qt.BrushStyle.NoBrush)
        outer_outline.setPen(self._outline_pen(1.6))
        outer_outline.setZValue(-91)
        outer_outline.setCacheMode(QGraphicsPolygonItem.CacheMode.DeviceCoordinateCache)
        self._apply_hex_shadow(outer_outline)
        self.addItem(outer_outline)

        inner_outline = QGraphicsPolygonItem(inner)
        inner_outline.setBrush(Qt.BrushStyle.NoBrush)
        inner_outline.setPen(self._outline_pen(1.6))
        inner_outline.setZValue(-91)
        inner_outline.setCacheMode(QGraphicsPolygonItem.CacheMode.DeviceCoordinateCache)
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
        fill_item.setCacheMode(QGraphicsPathItem.CacheMode.DeviceCoordinateCache)
        self.addItem(fill_item)

        outer_outline = QGraphicsPolygonItem(outer)
        outer_outline.setBrush(Qt.BrushStyle.NoBrush)
        outer_outline.setPen(self._outline_pen(1.4))
        outer_outline.setZValue(-90.5)
        outer_outline.setCacheMode(QGraphicsPolygonItem.CacheMode.DeviceCoordinateCache)
        self._apply_hex_shadow(outer_outline)
        self.addItem(outer_outline)

        inner_outline = QGraphicsPolygonItem(inner)
        inner_outline.setBrush(Qt.BrushStyle.NoBrush)
        inner_outline.setPen(self._outline_pen(1.4))
        inner_outline.setZValue(-90.5)
        inner_outline.setCacheMode(QGraphicsPolygonItem.CacheMode.DeviceCoordinateCache)
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
        outline.setCacheMode(QGraphicsPolygonItem.CacheMode.DeviceCoordinateCache)
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
            item.setCacheMode(QGraphicsPolygonItem.CacheMode.DeviceCoordinateCache)
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
        fill_item.setCacheMode(QGraphicsPathItem.CacheMode.DeviceCoordinateCache)
        self.addItem(fill_item)

        outline = QGraphicsPolygonItem(outer)
        outline.setBrush(Qt.BrushStyle.NoBrush)
        outline.setPen(self._outline_pen(1.0))
        outline.setZValue(-93)
        outline.setCacheMode(QGraphicsPolygonItem.CacheMode.DeviceCoordinateCache)
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
        item.setCacheMode(QGraphicsPathItem.CacheMode.DeviceCoordinateCache)
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
            self.edge_lookup[(dep.source_id, dep.target_id)] = edge

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
        inner_radius = self.layout.domain_radius * 0.22
        outer_radius = self.layout.domain_radius - 18
        return self._layout_concentric_rings(
            components,
            inner_radius=inner_radius,
            outer_radius=outer_radius,
            ring_spacing=28.0,
            padding_x=12.0,
        )

    def layout_application_nodes(self, components: List[Component]) -> Dict[str, QPointF]:
        if not components:
            return {}
        inner_radius = self.layout.domain_radius + 40
        outer_radius = self.layout.application_radius
        inner_radius = inner_radius + 12
        outer_radius = outer_radius - 16
        return self._layout_concentric_rings(
            components,
            inner_radius=inner_radius,
            outer_radius=outer_radius,
            ring_spacing=30.0,
            padding_x=12.0,
        )

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
            self._place_on_arc_non_overlapping(
                inbound, mid_radius, math.radians(150), math.radians(330), min_radius=inner_radius + 10
            )
        )
        positions.update(
            self._place_on_arc_non_overlapping(
                outbound, mid_radius, math.radians(-40), math.radians(80), min_radius=inner_radius + 10
            )
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
        # 배치 업데이트: 개별 update() 호출 대신 일괄 상태 변경
        for edge in self.edge_items:
            edge._hover_highlight = False
            edge._dirty = True
        # Scene 전체의 단일 update로 처리
        self.update()

    def apply_flow(self, flow: FlowResult, start_id: str) -> None:
        node_ids = {component.id for component in flow.nodes}
        edge_ids = {(edge.source_id, edge.target_id) for edge in flow.edges}
        self.flow_active = True
        for component_id, item in self.component_items.items():
            in_flow = component_id in node_ids
            item.set_flow_state(in_flow, is_start=component_id == start_id)
            item.set_flow_visited(False)
            item.set_flow_active(False)
            item.setOpacity(1.0 if in_flow else 0.18)
        for edge in self.edge_items:
            in_flow = (
                edge.source_item.component.id,
                edge.target_item.component.id,
            ) in edge_ids
            edge.set_flow_state(in_flow)
            edge.set_flow_visited(False)
            edge.set_flow_active(False)
            edge.setOpacity(0.6 if in_flow else 0.15)
        for items in self.layer_backgrounds.values():
            for item in items:
                item.setOpacity(0.2)

    def clear_flow(self) -> None:
        self.flow_active = False
        self.flow_token_pos = None
        for item in self.component_items.values():
            item.set_flow_state(False, False)
            item.set_flow_visited(False)
            item.set_flow_active(False)
            item.setOpacity(1.0)
        for edge in self.edge_items:
            edge.set_flow_state(False)
            edge.set_flow_visited(False)
            edge.set_flow_active(False)
            edge.setOpacity(0.55)
        for items in self.layer_backgrounds.values():
            for item in items:
                item.setOpacity(1.0)

    def set_flow_token_position(self, pos: QPointF | None) -> None:
        self.flow_token_pos = pos

    def apply_rule_violations(self, violations) -> None:
        for edge in self.edge_items:
            edge.set_violation(None)
        for item in self.component_items.values():
            item.set_violation_active(False)
        for violation in violations:
            if not violation.target_component_id:
                continue
            key = (violation.source_component_id, violation.target_component_id)
            edge = self.edge_lookup.get(key)
            if not edge:
                edge = self.edge_lookup.get((violation.target_component_id, violation.source_component_id))
            if edge:
                edge.set_violation(violation.severity)

    def focus_on_violation(self, violation) -> None:
        for item in self.component_items.values():
            item.set_violation_active(False)
        source = self.component_items.get(violation.source_component_id)
        target = self.component_items.get(violation.target_component_id) if violation.target_component_id else None
        if source:
            source.set_violation_active(True)
        if target:
            target.set_violation_active(True)

    def clear_smell_highlights(self) -> None:
        for item in self.component_items.values():
            item.set_smell_active(None)

    def focus_on_smell(self, component_id: str, color) -> None:
        self.clear_smell_highlights()
        item = self.component_items.get(component_id)
        if item:
            item.set_smell_active(color)

    def set_bc_filter(self, component_ids: set[str] | None) -> None:
        if not component_ids:
            for item in self.component_items.values():
                item.setOpacity(1.0)
            for edge in self.edge_items:
                edge.setOpacity(0.55)
            return
        for component_id, item in self.component_items.items():
            item.setOpacity(1.0 if component_id in component_ids else 0.12)
        for edge in self.edge_items:
            source_id = edge.source_item.component.id
            target_id = edge.target_item.component.id
            in_bc = source_id in component_ids and target_id in component_ids
            edge.setOpacity(0.6 if in_bc else 0.08)

    def set_component_focus(self, component_ids: set[str] | None) -> None:
        if not component_ids:
            for item in self.component_items.values():
                item.setOpacity(1.0)
            for edge in self.edge_items:
                edge.setOpacity(0.55)
            return
        for component_id, item in self.component_items.items():
            item.setOpacity(1.0 if component_id in component_ids else 0.12)
        for edge in self.edge_items:
            source_id = edge.source_item.component.id
            target_id = edge.target_item.component.id
            in_focus = source_id in component_ids or target_id in component_ids
            edge.setOpacity(0.6 if in_focus else 0.08)

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
            positions.update(
                self._place_on_arc_non_overlapping(
                    items,
                    radius=radius,
                    start_angle=start_angle,
                    end_angle=end_angle,
                    min_radius=radius,
                    padding=12.0,
                )
            )
        return positions

    def _place_on_arc(
        self, components: List[Component], radius: float, start_angle: float, end_angle: float
    ) -> Dict[str, QPointF]:
        if not components:
            return {}
        positions: Dict[str, QPointF] = {}
        arc_span = end_angle - start_angle
        capacity = max(2, int(arc_span / self._min_angle(radius)))
        ring_gap = 26
        for idx, component in enumerate(components):
            ring = idx // capacity
            ring_radius = radius + ring * ring_gap
            ring_index = idx % capacity
            ring_items = min(capacity, len(components) - ring * capacity)
            if ring_items == 1:
                angle = (start_angle + end_angle) / 2
            else:
                angle = start_angle + arc_span * (ring_index / (ring_items - 1))
            x = math.cos(angle) * ring_radius
            y = math.sin(angle) * ring_radius
            positions[component.id] = QPointF(x, y)
        return positions

    def _place_on_arc_non_overlapping(
        self,
        components: List[Component],
        radius: float,
        start_angle: float,
        end_angle: float,
        min_radius: float,
        padding: float = 12.0,
    ) -> Dict[str, QPointF]:
        if not components:
            return {}
        span = end_angle - start_angle
        widths = []
        for component in components:
            item = self.component_items.get(component.id)
            width = item.boundingRect().width() if item else 80.0
            widths.append(width + padding)
        total_arc = sum(widths)
        required_radius = total_arc / max(span, 0.001)
        radius = max(radius, required_radius, min_radius)
        positions: Dict[str, QPointF] = {}
        angle = start_angle
        for component, arc_width in zip(components, widths):
            needed = arc_width / radius
            center_angle = angle + needed / 2.0
            x = math.cos(center_angle) * radius
            y = math.sin(center_angle) * radius
            positions[component.id] = QPointF(x, y)
            angle += needed
        return positions

    def _layout_on_rings(
        self, components: List[Component], base_radius: float, ring_gap: float
    ) -> Dict[str, QPointF]:
        positions: Dict[str, QPointF] = {}
        capacity = self._ring_capacity(base_radius)
        for idx, component in enumerate(components):
            ring = idx // capacity
            ring_radius = base_radius + ring * ring_gap
            ring_index = idx % capacity
            ring_items = min(capacity, len(components) - ring * capacity)
            sectors = max(ring_items, 6)
            angle_step = self._angle_step(ring_radius, sectors)
            angle = -math.pi / 2 + ring_index * angle_step
            x = math.cos(angle) * ring_radius
            y = math.sin(angle) * ring_radius
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
        # 성능 최적화: 배경 헥사곤에는 무거운 QGraphicsDropShadowEffect 대신
        # 시각적으로 충분한 그라데이션 배경만 사용
        pass

    def _min_angle(self, radius: float) -> float:
        estimated_width = 80.0
        return max(2 * math.pi / 12, estimated_width / max(radius, 1))

    def _angle_step(self, radius: float, sectors: int) -> float:
        return max(2 * math.pi / max(sectors, 6), self._min_angle(radius))

    def _ring_capacity(self, radius: float) -> int:
        return max(6, int((2 * math.pi) / self._min_angle(radius)))

    def _layout_concentric_rings(
        self,
        components: List[Component],
        inner_radius: float,
        outer_radius: float,
        ring_spacing: float,
        padding_x: float,
        angle_start: float = -math.pi,
        angle_end: float = math.pi,
    ) -> Dict[str, QPointF]:
        positions: Dict[str, QPointF] = {}
        if not components:
            return positions

        radii = []
        radius = inner_radius
        while radius <= outer_radius:
            radii.append(radius)
            radius += ring_spacing

        if not radii:
            radii = [inner_radius]

        avg_width = self._average_node_width(components)
        ring_caps = []
        for r in radii:
            circumference = 2 * math.pi * r
            max_nodes = max(1, int(circumference // (avg_width + padding_x)))
            ring_caps.append(max_nodes)

        assignments: Dict[int, List[Component]] = {i: [] for i in range(len(radii))}
        ring_index = 0
        for component in components:
            while ring_index < len(radii) and len(assignments[ring_index]) >= ring_caps[ring_index]:
                ring_index += 1
            if ring_index >= len(radii):
                ring_index = len(radii) - 1
            assignments[ring_index].append(component)

        for idx, nodes_on_ring in assignments.items():
            if not nodes_on_ring:
                continue
            radius = radii[idx]
            arc_lengths = []
            total_arc = 0.0
            for component in nodes_on_ring:
                item = self.component_items.get(component.id)
                width = item.boundingRect().width() if item else avg_width
                arc = width + padding_x
                arc_lengths.append(arc)
                total_arc += arc
            available = max(0.001, (angle_end - angle_start) * radius)
            if total_arc > available:
                scale = available / total_arc
                arc_lengths = [arc * scale for arc in arc_lengths]
                total_arc = sum(arc_lengths)
            angle = angle_start + ((angle_end - angle_start) - total_arc / radius) / 2.0
            for component, arc in zip(nodes_on_ring, arc_lengths):
                angle_span = arc / radius
                center_angle = angle + angle_span / 2.0
                x = math.cos(center_angle) * radius
                y = math.sin(center_angle) * radius
                positions[component.id] = QPointF(x, y)
                angle += angle_span

        return positions

    def _average_node_width(self, components: List[Component]) -> float:
        widths = []
        for component in components:
            item = self.component_items.get(component.id)
            if item:
                widths.append(item.boundingRect().width())
        return sum(widths) / len(widths) if widths else 80.0

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
