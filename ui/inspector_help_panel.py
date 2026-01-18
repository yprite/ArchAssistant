from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from ui.colors import TEXT_SECONDARY


class InspectorHelpPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            scroll.horizontalScrollBarPolicy().ScrollBarAlwaysOff
        )

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(18, 18, 18, 18)
        content_layout.setSpacing(10)

        for title, body in _HELP_ITEMS:
            title_label = QLabel(title)
            title_label.setStyleSheet(
                "font-family: 'Gmarket Sans'; font-weight: 700;"
            )
            body_label = QLabel(body)
            body_label.setWordWrap(True)
            body_label.setStyleSheet(f"color: {TEXT_SECONDARY.name()};")
            content_layout.addWidget(title_label)
            content_layout.addWidget(body_label)
            divider = QFrame()
            divider.setFrameShape(QFrame.Shape.HLine)
            divider.setFrameShadow(QFrame.Shadow.Sunken)
            content_layout.addWidget(divider)

        content_layout.addStretch(1)
        scroll.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

        self.setStyleSheet("QLabel { font-size: 12px; }")


_HELP_ITEMS = [
    (
        "Name (이름)",
        "클래스/컴포넌트 이름입니다. 소스 코드 상의 실제 클래스명 또는 파일 이름을 의미합니다.",
    ),
    (
        "Layer (레이어)",
        "이 컴포넌트가 속한 DDD/헥사고날 레이어입니다. 예: Domain, Application, Inbound Port, "
        "Outbound Port, Inbound Adapter, Outbound Adapter, Unknown 등.",
    ),
    (
        "패키지 / 네임스페이스",
        "코드 구조 상에서 이 컴포넌트가 속한 패키지 또는 네임스페이스입니다. "
        "바운디드 컨텍스트 및 모듈 경계를 유추하는 기준으로 사용됩니다.",
    ),
    (
        "경로",
        "실제 소스 파일의 절대/상대 경로입니다. '파일 위치 열기' 버튼과 연결됩니다.",
    ),
    (
        "Annotations (어노테이션)",
        "이 클래스에 붙어 있는 프레임워크 어노테이션 목록입니다. "
        "예: @RestController, @Service, @Repository, @Entity 등. "
        "역할 추론, 레이어 판별, 스멜/규칙 검사에 사용됩니다.",
    ),
    (
        "Imports (의존성)",
        "이 컴포넌트가 import 하고 있는 외부 타입/패키지 목록입니다. "
        "컴포넌트 간 의존 관계, Event 후보, Cross-Aggregate 의존 등을 분석하는 데 사용됩니다.",
    ),
    (
        "Event Role (이벤트 역할)",
        "이 컴포넌트가 이벤트 관점에서 Producer, Consumer, Saga, Handler 중 어떤 역할을 "
        "하는지 표시합니다.",
    ),
    (
        "Aggregate / Entity Type (애그리게잇/엔티티)",
        "Domain 레이어에서 이 컴포넌트가 애그리게잇 루트인지, 값 객체인지 등을 나타냅니다.",
    ),
]
