from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow

FONT_FILES = [
    "Pretendard-Regular.ttf",
    "Pretendard-SemiBold.ttf",
    "GmarketSans-Bold.ttf",
]


def main() -> int:
    app = QApplication(sys.argv)
    font_dir = Path(__file__).resolve().parent / "assets" / "fonts"
    for filename in FONT_FILES:
        font_path = font_dir / filename
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))

    font = QFont("Pretendard")
    font.setStyleHint(QFont.StyleHint.SansSerif)
    font.setPointSize(11)
    app.setFont(font)
    app.setStyleSheet(
        "QWidget { font-family: 'Pretendard', 'SUIT', 'Noto Sans KR',"
        " 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; }"
    )
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
