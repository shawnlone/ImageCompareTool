from PySide6.QtCore import QTimer, QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QSlider,
    QSpinBox, QVBoxLayout, QWidget
)

from .constants import DEFAULT_TAB_TITLE, LABEL_STYLE_DEFAULTS
from .dnd import accept_drop_if_has_file, handle_drop_event

class ColorButton(QPushButton):
    color_changed = Signal(str)

    def __init__(self, color="#ffffffff", parent=None):
        super().__init__(parent)
        self._color = color
        self._preview_color = color
        self._dlg = None
        self.setFixedSize(48, 24)
        self.clicked.connect(self.choose_color)
        self.refresh_style()

    def refresh_style(self):
        self.setText("")
        self.setStyleSheet(f"""
            QPushButton {{
                background:{self._preview_color};
                border:1px solid #555;
                border-radius:3px;
            }}
            QPushButton:hover {{
                border:1px solid #888;
            }}
        """)

    def set_preview_color(self, color):
        self._preview_color = color
        self.refresh_style()

    def choose_color(self):
        self._dlg = QColorDialog(QColor(self._color), self)
        self._dlg.setOption(QColorDialog.ShowAlphaChannel, True)
        self._dlg.setOption(QColorDialog.DontUseNativeDialog, True)
        self._dlg.setStyleSheet("""
            QWidget {
                background:#2b2b2b;
                color:white;
            }
            QPushButton {
                background:#3a3a3a;
                color:white;
                border:1px solid #555;
                padding:4px 10px;
            }
            QPushButton:hover {
                background:#4a4a4a;
            }
        """)
        self._dlg.currentColorChanged.connect(self._on_live_color_changed)
        self._dlg.colorSelected.connect(self._on_final_color_selected)
        self._dlg.open()

    def _on_live_color_changed(self, color):
        if color.isValid():
            self.set_color(color.name(QColor.HexArgb))

    def _on_final_color_selected(self, color):
        if color.isValid():
            self.set_color(color.name(QColor.HexArgb))

    def set_color(self, color):
        self._color = color
        self._preview_color = color
        self.refresh_style()
        self.color_changed.emit(color)

    def color(self):
        return self._color


class DialogCloseButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 28)
        self.setFocusPolicy(Qt.NoFocus)
        self.setObjectName("DialogCloseButton")

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(QColor("#f2f2f2"), 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        c = self.rect().center()
        cx = c.x()
        cy = c.y() + 1
        p.drawLine(cx - 4, cy - 4, cx + 4, cy + 4)
        p.drawLine(cx + 4, cy - 4, cx - 4, cy + 4)


class DialogTitleBar(QWidget):
    def __init__(self, title, dialog):
        super().__init__(dialog)
        self.dialog = dialog
        self.setFixedHeight(34)
        self.setObjectName("DialogTitleBar")

        self.title_label = QLabel(title)
        self.title_label.setObjectName("DialogTitleText")
        self.title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.close_button = DialogCloseButton()
        self.close_button.clicked.connect(dialog.close)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 4, 0)
        layout.setSpacing(0)
        layout.addWidget(self.title_label, 1)
        layout.addWidget(self.close_button, 0)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            window_handle = self.dialog.windowHandle()
            if window_handle is not None and window_handle.startSystemMove():
                event.accept()
                return
        super().mousePressEvent(event)


class DialogShadowHost(QWidget):
    def __init__(self):
        super().__init__()
        self._frame_widget = None
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def set_frame_widget(self, widget):
        self._frame_widget = widget
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._frame_widget is None:
            return

        frame_rect = self._frame_widget.geometry()
        if frame_rect.isEmpty():
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        for i in range(5, 0, -1):
            alpha = max(0, 12 - i * 2)
            if alpha <= 0:
                continue
            rect = frame_rect.adjusted(-i, -i, i, i + 2)
            p.setBrush(QColor(0, 0, 0, alpha))
            p.drawRoundedRect(rect, 8 + i, 8 + i)

        bg_rect = QRectF(frame_rect).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(QColor("#202020"))
        p.drawRoundedRect(bg_rect, 8, 8)
        p.setPen(QPen(QColor("#303030"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(bg_rect, 8, 8)


class RoundedDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.host = DialogShadowHost()
        outer.addWidget(self.host)

        host_layout = QVBoxLayout(self.host)
        host_layout.setContentsMargins(12, 10, 12, 16)
        host_layout.setSpacing(0)

        self.frame = QWidget()
        self.frame.setObjectName("DialogFrame")
        host_layout.addWidget(self.frame)
        self.host.set_frame_widget(self.frame)

        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(1, 1, 1, 1)
        frame_layout.setSpacing(0)

        self.title_bar = DialogTitleBar(title, self)
        frame_layout.addWidget(self.title_bar)

        self.content_widget = QWidget()
        self.content_widget.setObjectName("DialogContent")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(16, 20, 16, 20)
        self.content_layout.setSpacing(0)
        frame_layout.addWidget(self.content_widget)

        self.setStyleSheet("""
            QWidget#DialogFrame {
                background-color: transparent;
                border: none;
                border-radius: 8px;
            }
            QWidget#DialogTitleBar {
                background-color: transparent;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border-bottom: 1px solid #2a2a2a;
            }
            QLabel#DialogTitleText {
                color: white;
                font: 10pt "Microsoft YaHei UI";
            }
            QWidget#DialogContent {
                background-color: transparent;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }
            QLabel {
                color: white;
            }
            QLineEdit {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 6px;
                selection-background-color: #4a90e2;
            }
            QLineEdit:focus {
                border: 1px solid #4a90e2;
            }
            QSpinBox, QComboBox {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 6px;
            }
            QSpinBox:focus, QComboBox:focus {
                border: 1px solid #4a90e2;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2f2f2f;
            }
            QSlider::groove:horizontal {
                border: 1px solid #444;
                height: 6px;
                background: #2b2b2b;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #4a90e2;
                border-radius: 3px;
            }
            QSlider::add-page:horizontal {
                background: #3a3a3a;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #6f6f6f;
                border: 1px solid #555;
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #8a8a8a;
                border: 1px solid #4a90e2;
            }
            QCheckBox {
                color: white;
                spacing: 6px;
            }
            QPushButton#DialogCloseButton {
                background: transparent;
                border: none;
                border-radius: 5px;
                padding: 0px;
            }
            QPushButton#DialogCloseButton:hover {
                background: #c42b1c;
            }
            QPushButton#DialogCloseButton:pressed {
                background: #9f2318;
            }
        """)


class LabelStyleDialog(RoundedDialog):
    def __init__(self, main_window):
        super().__init__("对比设置", main_window)

        self.main_window = main_window
        self.setMinimumWidth(380)

        cfg = self.main_window.get_current_label_style()

        root = self.content_layout

        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(9)
        root.addLayout(form)

        def add_gap(height=2):
            spacer = QWidget()
            spacer.setFixedHeight(height)
            form.addRow(spacer)

        self.a_text = QLineEdit(cfg["a_text"])
        self.a_color = ColorButton(cfg["a_text_color"])
        form.addRow("A标题", self.a_text)
        form.addRow("A标题颜色", self.a_color)

        add_gap()

        self.b_text = QLineEdit(cfg["b_text"])
        self.b_color = ColorButton(cfg["b_text_color"])
        form.addRow("B标题", self.b_text)
        form.addRow("B标题颜色", self.b_color)

        add_gap()

        self.font_size = QSpinBox()
        self.font_size.setRange(8, 72)
        self.font_size.setValue(cfg["font_size"])

        self.bg_color = ColorButton(cfg["bg_color"])

        self.bg_alpha = QSlider(Qt.Horizontal)
        self.bg_alpha.setRange(0, 255)
        self.bg_alpha.setValue(cfg.get("bg_alpha", 170))

        self.position = QComboBox()
        self.position.addItems(["左/右上", "中间", "左/右下"])
        pos_map = {"top": "左/右上", "center": "中间", "bottom": "左/右下"}
        self.position.setCurrentText(pos_map.get(cfg["position"], "左/右上"))

        self.offset_x = QSlider(Qt.Horizontal)
        self.offset_x.setRange(0, 300)
        self.offset_x.setValue(cfg["offset_x"])

        self.offset_y = QSlider(Qt.Horizontal)
        self.offset_y.setRange(0, 300)
        self.offset_y.setValue(cfg["offset_y"])

        form.addRow("文本尺寸", self.font_size)
        form.addRow("背景颜色", self.bg_color)
        form.addRow("背景透明度", self.bg_alpha)

        add_gap()

        form.addRow("显示位置", self.position)
        form.addRow("X偏移", self.offset_x)
        form.addRow("Y偏移", self.offset_y)

        root.addSpacing(18)

        self.hide_split_line = QCheckBox("隐藏对比分割线")
        self.hide_split_line.setChecked(cfg.get("hide_split_line", False))

        btn_row = QHBoxLayout()
        root.addLayout(btn_row)

        btn_row.addWidget(self.hide_split_line)
        btn_row.addStretch(1)

        self.reset_btn = QPushButton("重置默认")
        btn_row.addWidget(self.reset_btn)

        self.a_text.textChanged.connect(self.apply_changes)
        self.a_color.color_changed.connect(self.apply_changes)
        self.b_text.textChanged.connect(self.apply_changes)
        self.b_color.color_changed.connect(self.apply_changes)
        self.font_size.valueChanged.connect(self.apply_changes)

        self.bg_color.color_changed.connect(self._on_bg_color_changed)
        self.bg_alpha.valueChanged.connect(self._on_bg_alpha_changed)

        self.position.currentIndexChanged.connect(self.apply_changes)
        self.offset_x.valueChanged.connect(self.apply_changes)
        self.offset_y.valueChanged.connect(self.apply_changes)
        self.hide_split_line.toggled.connect(self.apply_changes)
        self.reset_btn.clicked.connect(self.reset_defaults)

        self.sync_bg_button_preview()

    def sync_bg_button_preview(self):
        c = QColor(self.bg_color.color())
        c.setAlpha(self.bg_alpha.value())
        self.bg_color.set_preview_color(c.name(QColor.HexArgb))

    def _on_bg_alpha_changed(self, value):
        self.sync_bg_button_preview()
        self.apply_changes()

    def _on_bg_color_changed(self, color):
        self.sync_bg_button_preview()
        self.apply_changes()

    def reset_defaults(self):
        d = LABEL_STYLE_DEFAULTS
        self.a_text.setText(d["a_text"])
        self.a_color.set_color(d["a_text_color"])
        self.b_text.setText(d["b_text"])
        self.b_color.set_color(d["b_text_color"])
        self.font_size.setValue(d["font_size"])
        self.bg_color.set_color(d["bg_color"])
        self.bg_alpha.setValue(d.get("bg_alpha", 170))
        self.position.setCurrentText("左/右上")
        self.offset_x.setValue(d["offset_x"])
        self.offset_y.setValue(d["offset_y"])
        self.hide_split_line.setChecked(d.get("hide_split_line", False))
        self.sync_bg_button_preview()
        self.apply_changes()

    def apply_changes(self, *args):
        text_to_pos = {
            "左/右上": "top",
            "中间": "center",
            "左/右下": "bottom",
        }
        cfg = {
            "a_text": self.a_text.text(),
            "a_text_color": self.a_color.color(),
            "b_text": self.b_text.text(),
            "b_text_color": self.b_color.color(),
            "font_size": self.font_size.value(),
            "bg_color": QColor(self.bg_color.color()).name(QColor.HexRgb),
            "bg_alpha": self.bg_alpha.value(),
            "position": text_to_pos[self.position.currentText()],
            "offset_x": self.offset_x.value(),
            "offset_y": self.offset_y.value(),
            "hide_split_line": self.hide_split_line.isChecked(),
        }
        self.main_window.update_label_style(cfg)


class TabButton(QWidget):
    clicked = Signal()
    close_requested = Signal()

    def __init__(self, title=DEFAULT_TAB_TITLE, is_add=False, parent=None):
        super().__init__(parent)
        self.title = title
        self.is_add = is_add
        self.active = False
        self.hovered = False
        self.close_hovered = False
        self._pressed = False

        self.setMouseTracking(True)
        self.setFixedHeight(22)
        if self.is_add:
            self.setFixedWidth(32)
        else:
            self.setMinimumWidth(120)

    def set_title(self, title):
        self.title = title
        self.updateGeometry()
        self.update()

    def set_active(self, active):
        self.active = active
        self.update()

    def sizeHint(self):
        if self.is_add:
            return QSize(28, 22)
        fm = self.fontMetrics()
        width = max(120, fm.horizontalAdvance(self.title) + 38)
        return QSize(width, 22)

    def close_rect(self):
        r = self.rect()
        return QRectF(r.right() - 20, r.center().y() - 6, 14, 14)

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.close_hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        close_hovered = self.hovered and not self.is_add and self.close_rect().contains(event.position())
        if close_hovered != self.close_hovered:
            self.close_hovered = close_hovered
            self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)

        self._pressed = True
        event.accept()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        r = QRectF(self.rect()).adjusted(1, 0, -1, 0)

        if self.is_add:
            bg = QColor("#2f2f2f00") if not self.hovered else QColor("#3a3a3a")
            border = QColor("#25252500")
            path = QPainterPath()
            path.addRoundedRect(r, 2, 2)
            p.fillPath(path, bg)
            p.setPen(QPen(border, 1))
            p.drawPath(path)
            p.setPen(QColor("#aaaaaa"))
            f = QFont("Microsoft YaHei", 11)
            f.setBold(True)
            p.setFont(f)
            p.drawText(r, Qt.AlignCenter, "+")
            return

        bg = QColor("#1F1F1F") if not self.active else QColor("#353535")
        if self.hovered and not self.active:
            bg = QColor("#2d2d2d")
        border = QColor("#39393900") if self.active else QColor("#40404000")

        path = QPainterPath()
        path.addRoundedRect(r, 2, 2)

        p.fillPath(path, bg)
        p.setPen(QPen(border, 1))
        p.drawPath(path)

        text_right = r.right() - 10
        if self.hovered:
            text_right = self.close_rect().left() - 6

        text_rect = QRectF(r.left() + 12, r.top(), max(20.0, text_right - (r.left() + 12)), r.height())
        p.setPen(QColor("#ffffff") if self.active else QColor("#c3c3c3"))
        f = QFont("Microsoft YaHei", 9)
        p.setFont(f)
        p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.title)

        if self.hovered:
            cr = self.close_rect()
            if self.close_hovered:
                close_path = QPainterPath()
                close_path.addRoundedRect(cr, 3, 3)
                p.fillPath(close_path, QColor("#4a4a4a"))

            p.setPen(QPen(QColor("#efefef"), 1.4))
            pad = 4
            p.drawLine(cr.left() + pad, cr.top() + pad, cr.right() - pad, cr.bottom() - pad)
            p.drawLine(cr.right() - pad, cr.top() + pad, cr.left() + pad, cr.bottom() - pad)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mouseReleaseEvent(event)

        if not self._pressed:
            return

        self._pressed = False

        if not self.rect().contains(event.position().toPoint()):
            return

        if self.is_add:
            self.clicked.emit()
            return

        if self.hovered and self.close_rect().contains(event.position()):
            self.close_requested.emit()
            return

        self.clicked.emit()

class BottomTabBar(QWidget):
    current_changed = Signal(int)
    add_requested = Signal()
    close_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.buttons = []
        self.current_index = -1

        self.setFixedHeight(34)
        self.setStyleSheet("background:#202020;")

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(False)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("background:#202020; border:none;")

        self.inner = QWidget()
        self.inner.setStyleSheet("background:#202020;")
        self.inner_layout = QHBoxLayout(self.inner)
        self.inner_layout.setContentsMargins(6, 0, 6, 0)
        self.inner_layout.setSpacing(3)
        self.scroll.setWidget(self.inner)

        self.left_arrow = QPushButton("◀", self)
        self.left_arrow.setFixedSize(22, 22)
        self.left_arrow.setFocusPolicy(Qt.NoFocus)

        self.right_arrow = QPushButton("▶", self)
        self.right_arrow.setFixedSize(22, 22)
        self.right_arrow.setFocusPolicy(Qt.NoFocus)

        tool_btn_style = """
            QPushButton {
                background: #2a2a2a;
                color: #aaaaaa;
                border: none;
                border-radius: 2px;
                font: bold 10pt "Microsoft YaHei";
                padding: 0;
            }
            QPushButton:hover {
                background: #404040;
                color: white;
            }
            QPushButton:pressed {
                background: #1f1f1f;
                color: white;
            }
            QPushButton:disabled {
                background: #222222;
                color: #666666;
            }
        """


        self.left_arrow.setStyleSheet(tool_btn_style)
        self.right_arrow.setStyleSheet(tool_btn_style)
        
        self.add_button = QPushButton("+", self)
        self.add_button.setFixedSize(22, 22)
        self.add_button.setStyleSheet(tool_btn_style)
        self.add_button.setFocusPolicy(Qt.NoFocus)
        
        self.add_button.clicked.connect(self.add_requested.emit)

        self.left_arrow.clicked.connect(self.scroll_tabs_left)
        self.right_arrow.clicked.connect(self.scroll_tabs_right)

        self.left_arrow.hide()
        self.right_arrow.hide()

        self.scroll.horizontalScrollBar().valueChanged.connect(self.update_tool_buttons)

    def rebuild(self, titles, current_index):
        self.current_index = current_index
        self.buttons.clear()

        while self.inner_layout.count():
            item = self.inner_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        total_width = 6

        for i, title in enumerate(titles):
            btn = TabButton(title=title, is_add=False)
            btn.set_active(i == current_index)
            btn.clicked.connect(lambda checked=False, idx=i: self.current_changed.emit(idx))
            btn.close_requested.connect(lambda idx=i: self.close_requested.emit(idx))
            self.inner_layout.addWidget(btn, 0)
            self.buttons.append(btn)
            total_width += btn.sizeHint().width() + self.inner_layout.spacing()

        total_width += 6
        self.inner.resize(total_width, self.height())

        QTimer.singleShot(0, self.relayout)

    def update_active(self, current_index):
        self.current_index = current_index
        for i, btn in enumerate(self.buttons):
            btn.set_active(i == current_index)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.relayout()

    def relayout(self):
        h = self.height()
        margin_left = 6
        margin_right = 6
        spacing = 4
        y_offset = 0

        arrow_w = self.left_arrow.width()
        add_w = self.add_button.width()

        content_width = self.inner.sizeHint().width()
        available_width = max(0, self.width() - margin_left - margin_right)

        scroll_bar = self.scroll.horizontalScrollBar()
        overflow = content_width + add_w > available_width

        if overflow:
            tools_width = arrow_w * 2 + spacing * 2 + add_w
            scroll_width = max(0, available_width - tools_width)

            self.scroll.setGeometry(margin_left, 0, scroll_width, h)

            tools_x = margin_left + scroll_width + spacing
            center_y = (h - self.add_button.height()) // 2 + y_offset

            self.left_arrow.show()
            self.right_arrow.show()

            self.left_arrow.move(
                tools_x,
                (h - self.left_arrow.height()) // 2 + y_offset
            )
            self.right_arrow.move(
                tools_x + arrow_w + spacing,
                (h - self.right_arrow.height()) // 2 + y_offset
            )
            self.add_button.move(
                tools_x + arrow_w * 2 + spacing * 2,
                center_y
            )

            self.inner.resize(max(content_width, scroll_width), h)

        else:
            self.left_arrow.hide()
            self.right_arrow.hide()

            max_add_x = self.width() - margin_right - add_w
            add_x = min(margin_left + content_width, max_add_x)
            center_y = (h - self.add_button.height()) // 2 + y_offset

            self.scroll.setGeometry(margin_left, 0, max(0, add_x - margin_left), h)
            self.add_button.move(add_x, center_y)

            self.inner.resize(content_width, h)
            scroll_bar.setValue(0)

        self.update_tool_buttons()

    def update_tool_buttons(self):
        bar = self.scroll.horizontalScrollBar()
        if self.left_arrow.isVisible():
            self.left_arrow.setEnabled(bar.value() > 0)
            self.right_arrow.setEnabled(bar.value() < bar.maximum())

    def scroll_tabs_left(self):
        bar = self.scroll.horizontalScrollBar()
        step = max(120, self.scroll.viewport().width() // 2)
        bar.setValue(bar.value() - step)

    def scroll_tabs_right(self):
        bar = self.scroll.horizontalScrollBar()
        step = max(120, self.scroll.viewport().width() // 2)
        bar.setValue(bar.value() + step)


class DropPanel(QFrame):
    def __init__(self, text, side, compare_tab):
        super().__init__()
        self.side = side
        self.compare_tab = compare_tab
        self.setAcceptDrops(True)
        self.setObjectName("DropPanel")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._original_pixmap = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background:#2a2a2a; border:none; border-radius:6px;")
        layout.addWidget(self.preview, 1)

        self.button = QPushButton(text, self.preview)
        self.button.setFixedSize(96, 96)
        self.button.setStyleSheet("""
            QPushButton {
                background: #303030;
                color: white;
                border: none;
                border-radius: 10px;
                font: bold 18pt "Microsoft YaHei";
                padding: 0px;
            }
            QPushButton:hover {
                background: #3a3a3a;
            }
            QPushButton:pressed {
                background: #262626;
            }
        """)
        self.button.clicked.connect(lambda: self.compare_tab.open_file(self.side))
        self.button.raise_()

    def set_preview(self, pixmap: QPixmap, label_text: str = ""):
        if pixmap.isNull():
            return
        self._original_pixmap = pixmap
        scaled = pixmap.scaled(
            self.preview.size() * 0.95,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.preview.setPixmap(scaled)
        self.preview.setText("")
        self.button.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)

        button_size = max(58, min(96, int(min(self.preview.width(), self.preview.height()) * 0.36)))
        if self.button.width() != button_size:
            self.button.setFixedSize(button_size, button_size)

        bx = (self.preview.width() - self.button.width()) // 2
        by = (self.preview.height() - self.button.height()) // 2
        self.button.move(max(0, bx), max(0, by))

        if self._original_pixmap and not self._original_pixmap.isNull():
            scaled = self._original_pixmap.scaled(
                self.preview.size() * 0.95,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.preview.setPixmap(scaled)

    def dragEnterEvent(self, event: QDragEnterEvent):
        accept_drop_if_has_file(event)

    def dropEvent(self, event: QDropEvent):
        handle_drop_event(
            event,
            self.compare_tab,
            target_side=self.side,
            project_in_new_tab=True
        )

    def reset(self):
        self._original_pixmap = None
        self.preview.clear()
        self.preview.setPixmap(QPixmap())
        self.preview.setText("")
        self.button.show()


class HelpPopup(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HelpPopup")
        self.setWindowFlags(Qt.SubWindow)
        self.hide()

        self.setFocusPolicy(Qt.StrongFocus)

        self.setStyleSheet("""
            QFrame#HelpPopup {
                background-color: rgba(20, 20, 20, 210);
                border: 1px solid rgba(255, 255, 255, 35);
                border-radius: 8px;
            }
            QLabel {
                color: #d0d0d0;
                background: transparent;
                font: 10pt "Microsoft YaHei";
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        groups = [
            ("视图操作", [
                "左键点击: 拖动对比",
                "右键按下: 拖动画面",
                "右键单击: 画面适配窗口",
                "滚轮: 缩放画面",
                "中键单击: 显示原比例",
            ]),
            ("图像切换", [
                "1/2/3键: A/B/AB",
                "空格键: 切换黑白/彩色",
                "Tab键: 交换A/B位置",
            ]),
            ("其他功能", [
                "F键: 打开标题设置",
                "T键: 切换窗口置顶",
                "Ctrl+C: 复制对比图",
                "Ctrl+S: 保存对比工程",
            ]),
        ]
        for group_title, items in groups:
            title_lbl = QLabel(group_title)
            title_lbl.setStyleSheet('color:#B4C3CC; font: bold 10pt "Microsoft YaHei"; margin-top:4px;')
            root.addWidget(title_lbl)
            for t in items:
                lbl = QLabel(f"• {t}")
                lbl.setStyleSheet('color:#d0d0d0;')
                root.addWidget(lbl)

        self.adjustSize()

    def focusOutEvent(self, event):
        self.hide()
        super().focusOutEvent(event)

class ToastPopup(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ToastPopup")
        self.setWindowFlags(Qt.SubWindow)
        self.hide()

        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.setStyleSheet("""
            QFrame#ToastPopup {
                background-color: rgba(20, 20, 20, 210);
                border-radius: 10px;
            }
            QLabel {
                color: #f2f2f2;
                background: transparent;
                font: 10pt "Microsoft YaHei";
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(0)

        self.label = QLabel("")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def reposition(self):
        if self.parent() is not None:
            parent = self.parent()
            x = (parent.width() - self.width()) // 2
            y = parent.height() - self.height() - 60
            self.move(max(0, x), max(0, y))

    def show_message(self, text, duration=2000):
        self.label.setText(text)
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self.timer.start(duration)
