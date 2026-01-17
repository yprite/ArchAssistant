from __future__ import annotations

from dataclasses import dataclass
from typing import List

from PySide6.QtCore import QEasingCurve, QObject, QPropertyAnimation, QSequentialAnimationGroup

from ui.event_token_item import EventTokenItem


@dataclass(frozen=True)
class FlowStep:
    index: int
    source_item: object
    target_item: object
    edge_item: object
    duration_ms: int


class FlowAnimationController(QObject):
    def __init__(self, scene, steps: List[FlowStep]) -> None:
        super().__init__()
        self._scene = scene
        self._steps = steps
        self._group = QSequentialAnimationGroup(self)
        self._token = EventTokenItem()
        self._token.setVisible(False)
        self._scene.addItem(self._token)
        self._build_group()
        self._group.currentAnimationChanged.connect(self._on_step_changed)
        self._group.finished.connect(self.stop)

    def play(self) -> None:
        if not self._steps:
            return
        if self._group.state() == QSequentialAnimationGroup.State.Paused:
            self._group.resume()
            return
        if self._group.state() == QSequentialAnimationGroup.State.Stopped:
            self._group.start()
            return

    def pause(self) -> None:
        if self._group.state() == QSequentialAnimationGroup.State.Running:
            self._group.pause()

    def restart(self) -> None:
        self._group.stop()
        self._group.setCurrentTime(0)
        self._group.start()

    def stop(self) -> None:
        for step in self._steps:
            step.edge_item.set_animation_active(False)
            step.target_item.set_animation_active(False)
        if self._steps:
            self._steps[0].source_item.set_animation_active(False)
        self._token.setVisible(False)
        if self._group.state() != QSequentialAnimationGroup.State.Stopped:
            self._group.stop()

    def _build_group(self) -> None:
        self._group.clear()
        for step in self._steps:
            source_center = step.source_item.sceneBoundingRect().center()
            target_center = step.target_item.sceneBoundingRect().center()
            anim = QPropertyAnimation(self._token, b"pos")
            anim.setDuration(step.duration_ms)
            anim.setStartValue(source_center)
            anim.setEndValue(target_center)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            self._group.addAnimation(anim)
        if self._steps:
            self._steps[0].source_item.set_animation_active(True)

    def _on_step_changed(self, animation) -> None:
        if animation is None:
            return
        index = self._group.indexOfAnimation(animation)
        if index < 0:
            return
        for step in self._steps:
            step.edge_item.set_animation_active(False)
            step.target_item.set_animation_active(False)
        step = self._steps[index]
        self._token.setVisible(True)
        self._token.setPos(step.source_item.sceneBoundingRect().center())
        step.edge_item.set_animation_active(True)
        step.target_item.set_animation_active(True)
