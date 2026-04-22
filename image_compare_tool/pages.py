from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .dnd import accept_drop_if_has_file, handle_drop_event
from .widgets import DropPanel


class EmptyComparePage(QWidget):
    def __init__(self, compare_tab):
        super().__init__()
        self.compare_tab = compare_tab
        self.setAcceptDrops(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        row = QHBoxLayout()
        row.setSpacing(12)

        self.panel_a = DropPanel("A", "a", self.compare_tab)
        self.panel_b = DropPanel("B", "b", self.compare_tab)

        row.addWidget(self.panel_a, 1)
        row.addWidget(self.panel_b, 1)

        wrap = QWidget()
        wrap.setLayout(row)
        root.addWidget(wrap)

        self.hint = QLabel("添加图片：支持通过载入、拖拽、粘贴的方式添加到当前标签页")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setStyleSheet("color:#666; padding-top:8px;")
        root.addWidget(self.hint)

    def dragEnterEvent(self, event: QDragEnterEvent):
        accept_drop_if_has_file(event)

    def dropEvent(self, event: QDropEvent):
        handle_drop_event(event, self.compare_tab, project_in_new_tab=True)

    def reset(self):
        self.panel_a.reset()
        self.panel_b.reset()
