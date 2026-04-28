import json
import os
import sys
import ctypes

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QTimer, Qt
from PySide6.QtGui import QAction, QColor, QCursor, QIcon, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMenu,
    QMessageBox, QPushButton, QScrollArea, QStackedLayout, QVBoxLayout, QWidget
)

from .constants import DEFAULT_TAB_TITLE, LABEL_STYLE_DEFAULTS, PROJECT_FILTER
from .image_utils import get_config_path, resource_path
from .tab import CompareTab
from .widgets import BottomTabBar, LabelStyleDialog, RoundedDialog


class WindowControlButton(QPushButton):
    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(30, 26)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCheckable(kind == "pin")
        self.setObjectName("CloseWindowButton" if kind == "close" else "WindowControlButton")

    def paintEvent(self, event):
        super().paintEvent(event)

        checked = self.isChecked()
        icon_color = QColor("#ffffff" if self.kind == "close" and self.underMouse() else "#d7dce2")

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(icon_color, 1.35, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        center = QRectF(self.rect()).center()
        cx = center.x()
        cy = center.y()

        if self.kind == "minimize":
            p.drawLine(QPointF(cx - 4, cy + 1), QPointF(cx + 4, cy + 1))
        elif self.kind == "maximize":
            if self.window().isMaximized():
                p.drawRect(QRectF(cx - 1.5, cy - 4.5, 7, 7))
                p.drawRect(QRectF(cx - 4.5, cy - 1.5, 7, 7))
            else:
                p.drawRect(QRectF(cx - 4, cy - 4, 8, 8))
        elif self.kind == "close":
            p.drawLine(QPointF(cx - 4, cy - 4), QPointF(cx + 4, cy + 4))
            p.drawLine(QPointF(cx + 4, cy - 4), QPointF(cx - 4, cy + 4))
        elif self.kind == "pin":
            p.drawLine(QPointF(cx, cy - 6), QPointF(cx, cy + 1))
            p.drawLine(QPointF(cx - 3, cy - 2), QPointF(cx, cy + 1))
            p.drawLine(QPointF(cx + 3, cy - 2), QPointF(cx, cy + 1))
            p.drawLine(QPointF(cx - 5, cy + 5), QPointF(cx + 5, cy + 5))


class TitleBar(QWidget):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.drag_start_global = None
        self.drag_start_frame = None
        self.setFixedHeight(34)
        self.setObjectName("TitleBar")

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(22, 22)
        icon = QIcon(resource_path("app.ico"))
        self.icon_label.setPixmap(icon.pixmap(18, 18))
        self.icon_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.title_label = QLabel(main_window.base_title)
        self.title_label.setObjectName("TitleText")
        self.title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.pin_button = WindowControlButton("pin")
        self.min_button = WindowControlButton("minimize")
        self.max_button = WindowControlButton("maximize")
        self.close_button = WindowControlButton("close")

        self.pin_button.setToolTip("置顶")
        self.min_button.setToolTip("最小化")
        self.max_button.setToolTip("最大化")
        self.close_button.setToolTip("关闭")

        self.pin_button.clicked.connect(main_window.toggle_always_on_top)
        self.min_button.clicked.connect(main_window.showMinimized)
        self.max_button.clicked.connect(self.toggle_max_restore)
        self.close_button.clicked.connect(main_window.close)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 4, 0)
        layout.setSpacing(3)
        layout.addWidget(self.icon_label, 0, Qt.AlignVCenter)
        layout.addWidget(self.title_label, 1)
        layout.addWidget(self.pin_button, 0)
        layout.addWidget(self.min_button, 0)
        layout.addWidget(self.max_button, 0)
        layout.addWidget(self.close_button, 0)

    def set_title(self, title):
        self.title_label.setText(title)

    def set_pinned(self, pinned):
        self.pin_button.setChecked(pinned)

    def refresh_window_state(self):
        if self.main_window.isMaximized():
            self.max_button.setToolTip("还原")
        else:
            self.max_button.setToolTip("最大化")
        self.max_button.update()

    def toggle_max_restore(self):
        if self.main_window.isMaximized():
            self.main_window.showNormal()
        else:
            self.main_window.showMaximized()
        self.refresh_window_state()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_max_restore()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            window_handle = self.main_window.windowHandle()
            if window_handle is not None and window_handle.startSystemMove():
                self.drag_start_global = None
                self.drag_start_frame = None
                event.accept()
                return
            self.drag_start_global = event.globalPosition().toPoint()
            self.drag_start_frame = self.main_window.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            event.buttons() & Qt.LeftButton
            and self.drag_start_global is not None
            and self.drag_start_frame is not None
            and not self.main_window.isMaximized()
        ):
            delta = event.globalPosition().toPoint() - self.drag_start_global
            self.main_window.move(self.drag_start_frame + delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_start_global = None
        self.drag_start_frame = None
        super().mouseReleaseEvent(event)


class ShadowHost(QWidget):
    def __init__(self):
        super().__init__()
        self._frame_widget = None
        self._shadow_enabled = True
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def set_frame_widget(self, widget):
        self._frame_widget = widget
        self.update()

    def set_shadow_enabled(self, enabled):
        self._shadow_enabled = enabled
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
        if self._shadow_enabled:
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.base_title = "图片对比工具 1.6"
        self.always_on_top = True
        self.label_style_dialog = None
        self.global_label_style = self.load_label_style()

        self.tabs = []
        self.current_tab_index = -1
        self._resize_margin = 4

        self.update_window_title()
        self.setWindowIcon(QIcon(resource_path("app.ico")))
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.resize(1400, 800)
        self.setMinimumSize(800, 500)

        self.tab_bar = BottomTabBar()
        self.tab_bar.current_changed.connect(self.switch_tab)
        self.tab_bar.add_requested.connect(self.add_new_tab)
        self.tab_bar.close_requested.connect(self.close_tab)

        self.help_button = QPushButton("≡")
        self.help_button.setFixedSize(24, 22)
        self.help_button.setFocusPolicy(Qt.NoFocus)
        self.help_button.setStyleSheet("""
            QPushButton {
                background: #202020;
                color: #bbbbbb;
                border-radius: 4px;
                font: 17pt "Microsoft YaHei";
                padding: 0;
            }
            QPushButton:hover {
                background: #454545;
                color: white;
            }
        """)
        self.help_button.pressed.connect(self.show_bottom_left_menu)
        self.bottom_menu = QMenu(self)
        self.bottom_menu.setFixedWidth(100)
        self.bottom_menu.setStyleSheet("""
            QMenu {
                background-color: #232323;
                color: #e8e8e8;
                border: 1px solid #3d3d3d;
                padding: 6px 0px;
            }
            QMenu::item {
                background-color: transparent;
                padding: 6px 10px 6px 18px;
            }
            QMenu::item:selected {
                background-color: #3a3a3a;
                color: white;
            }
            QMenu::item:disabled {
                color: #666666;
                background-color: transparent;
            }
            QMenu::separator {
                height: 1px;
                background: #303030;
                margin: 4px 6px;
            }
        """)

        self.action_open_project = QAction("打开工程", self)
        self.action_save_project = QAction("保存工程", self)
        self.action_compare_settings = QAction("对比设置", self)
        self.action_help_info = QAction("操作帮助", self)
        self.action_about = QAction("关于", self)

        self.action_open_project.triggered.connect(self.open_project_from_menu)
        self.action_save_project.triggered.connect(self.save_current_project)
        self.action_compare_settings.triggered.connect(self.open_label_style_dialog)
        self.action_help_info.triggered.connect(self.toggle_help_popup)
        self.action_about.triggered.connect(self.show_about_dialog)

        self.bottom_menu.addAction(self.action_open_project)
        self.bottom_menu.addAction(self.action_save_project)
        self.bottom_menu.addSeparator()
        self.bottom_menu.addAction(self.action_compare_settings)
        self.bottom_menu.addAction(self.action_help_info)
        self.bottom_menu.addAction(self.action_about)
        self.bottom_menu.aboutToHide.connect(lambda: self.help_button.setDown(False))

        self.status_label = QLabel("请添加 A / B 图片")
        self.status_label.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        self.status_label.setStyleSheet("color:#9a9a9a; padding-right:6px;")

        fm = self.status_label.fontMetrics()
        self.status_label.setFixedWidth(
            fm.horizontalAdvance("尺寸: 3840 × 2160    缩放: 999%") + 20
        )

        self.bottom_bar_widget = QWidget()
        self.bottom_bar_widget.setObjectName("BottomBar")
        self.bottom_bar_widget.setFixedHeight(34)
        self.bottom_bar_widget.setStyleSheet(
            "background:transparent; border:none;"
        )

        bottom_layout = QHBoxLayout(self.bottom_bar_widget)
        bottom_layout.setContentsMargins(10, 0, 10, 0)
        bottom_layout.setSpacing(6)
        bottom_layout.addWidget(self.help_button, 0)
        bottom_layout.addWidget(self.tab_bar, 1)
        bottom_layout.addWidget(self.status_label, 0)

        self.central_stack = QStackedLayout()
        self.central_stack.setContentsMargins(0, 0, 0, 0)
        self.central_stack.setSpacing(0)

        self.central_stack_host = QWidget()
        self.central_stack_host.setLayout(self.central_stack)

        self.root_widget = QWidget()
        self.root_widget.setObjectName("RootWidget")
        self.root_widget.setStyleSheet(
            "background:transparent; border:none;"
        )
        root_layout = QVBoxLayout(self.root_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.central_stack_host, 1)
        root_layout.addWidget(self.bottom_bar_widget, 0)

        self.title_bar = TitleBar(self)

        self.window_frame = QWidget()
        self.window_frame.setObjectName("WindowFrame")
        frame_layout = QVBoxLayout(self.window_frame)
        frame_layout.setContentsMargins(1, 1, 1, 1)
        frame_layout.setSpacing(0)
        frame_layout.addWidget(self.title_bar, 0)
        frame_layout.addWidget(self.root_widget, 1)

        self.window_host = ShadowHost()
        self.window_host.setObjectName("WindowHost")
        self.window_host.setMouseTracking(True)
        self.window_host_layout = QVBoxLayout(self.window_host)
        self.window_host_layout.setContentsMargins(14, 10, 14, 22)
        self.window_host_layout.setSpacing(0)
        self.window_host_layout.addWidget(self.window_frame)
        self.window_host.set_frame_widget(self.window_frame)

        self.setCentralWidget(self.window_host)

        self._apply_style()
        self._setup_actions()
        self.apply_always_on_top()
        self._update_window_chrome()

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        self.add_new_tab(set_current=True)

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background: transparent;
            }
            QWidget#WindowHost {
                background: transparent;
            }
            QWidget#WindowFrame {
                background: transparent;
                border: none;
                border-radius: 8px;
            }
            QWidget#TitleBar {
                background: transparent;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border-bottom: 1px solid #262626;
            }
            QWidget#RootWidget {
                background: transparent;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }
            QWidget#BottomBar {
                background: transparent;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }
            QLabel#TitleText {
                color: #edf1f7;
                font: 10pt "Microsoft YaHei UI";
            }
            QWidget {
                background: #202020;
                color: #f2f4f8;
            }
            QFrame#DropPanel {
                background: #2a2a2a;
                border: none;
                border-radius: 8px;
            }
            QPushButton {
                background: #303030;
                color: #c5ccd8;
                border: none;
                border-radius: 6px;
                font: bold 12pt "Microsoft YaHei";
                padding: 0px;
            }
            QPushButton:hover {
                background: #3a3a3a;
                color: white;
            }
            QPushButton:pressed {
                background: #262626;
            }
            QPushButton#WindowControlButton {
                background: transparent;
                border: none;
                border-radius: 5px;
                padding: 0px;
                font: 10pt "Microsoft YaHei UI";
            }
            QPushButton#WindowControlButton:hover {
                background: #343843;
            }
            QPushButton#WindowControlButton:pressed {
                background: #2a2d35;
            }
            QPushButton#WindowControlButton:checked {
                background: #2a2d35;
            }
            QPushButton#WindowControlButton:checked:hover {
                background: #343843;
            }
            QPushButton#CloseWindowButton {
                background: transparent;
                border: none;
                border-radius: 5px;
                padding: 0px;
            }
            QPushButton#CloseWindowButton:hover {
                background: #c42b1c;
            }
            QPushButton#CloseWindowButton:pressed {
                background: #9f2318;
            }
            QScrollArea {
                border: none;
                background: #202020;
            }
            QToolTip {
                background-color: #2a2d34;
                color: #f4f4f4;
                border: 1px solid #454a56;
                padding: 4px 7px;
                border-radius: 5px;
            }
        """)

    def _update_window_chrome(self):
        maximized = self.isMaximized()
        left = top = right = bottom = 0
        if not maximized:
            left, top, right, bottom = 14, 10, 14, 22
        radius = 0 if maximized else 8
        control_radius = 0 if maximized else 5
        self.window_host_layout.setContentsMargins(left, top, right, bottom)
        self.window_host.set_shadow_enabled(not maximized)
        self.window_frame.setStyleSheet(f"""
            QWidget#WindowFrame {{
                background: transparent;
                border: none;
                border-radius: {radius}px;
            }}
            QWidget#TitleBar {{
                background: transparent;
                border-bottom: 1px solid #262626;
                border-top-left-radius: {radius}px;
                border-top-right-radius: {radius}px;
            }}
            QWidget#RootWidget {{
                background: transparent;
                border-bottom-left-radius: {radius}px;
                border-bottom-right-radius: {radius}px;
            }}
            QWidget#BottomBar {{
                background: transparent;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }}
            QPushButton#WindowControlButton {{
                background: transparent;
                border: none;
                border-radius: {control_radius}px;
                padding: 0px;
            }}
            QPushButton#WindowControlButton:hover {{
                background: #343843;
            }}
            QPushButton#WindowControlButton:pressed {{
                background: #2a2d35;
            }}
            QPushButton#WindowControlButton:checked {{
                background: #2a2d35;
            }}
            QPushButton#WindowControlButton:checked:hover {{
                background: #343843;
            }}
            QPushButton#CloseWindowButton {{
                background: transparent;
                border: none;
                border-radius: {control_radius}px;
                padding: 0px;
            }}
            QPushButton#CloseWindowButton:hover {{
                background: #c42b1c;
            }}
            QPushButton#CloseWindowButton:pressed {{
                background: #9f2318;
            }}
        """)
        self.title_bar.refresh_window_state()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            self.unsetCursor()
            self._update_window_chrome()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "window_frame"):
            QTimer.singleShot(0, self._refresh_cursor_under_mouse)

    def _resize_edges_at(self, pos):
        if self.isMaximized():
            return Qt.Edges()

        border = self._resize_margin
        frame_rect = QRect(self.window_frame.mapTo(self, QPoint(0, 0)), self.window_frame.size())
        outer = frame_rect.adjusted(-border, -border, border, border)
        inner = frame_rect.adjusted(border, border, -border, -border)

        if not outer.contains(pos) or inner.contains(pos):
            return Qt.Edges()

        left = pos.x() <= frame_rect.left() + border
        right = pos.x() >= frame_rect.right() - border
        top = pos.y() <= frame_rect.top() + border
        bottom = pos.y() >= frame_rect.bottom() - border

        edges = Qt.Edges()
        if left:
            edges |= Qt.LeftEdge
        if right:
            edges |= Qt.RightEdge
        if top:
            edges |= Qt.TopEdge
        if bottom:
            edges |= Qt.BottomEdge
        return edges

    def _update_resize_cursor(self, pos):
        edges = self._resize_edges_at(pos)
        if edges in (Qt.LeftEdge | Qt.TopEdge, Qt.RightEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeFDiagCursor)
        elif edges in (Qt.RightEdge | Qt.TopEdge, Qt.LeftEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeBDiagCursor)
        elif edges & (Qt.LeftEdge | Qt.RightEdge):
            self.setCursor(Qt.SizeHorCursor)
        elif edges & (Qt.TopEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.unsetCursor()

    def _refresh_cursor_under_mouse(self):
        if not self.isVisible() or self.isMinimized():
            self.unsetCursor()
            return
        pos = self.mapFromGlobal(QCursor.pos())
        frame_rect = QRect(self.window_frame.mapTo(self, QPoint(0, 0)), self.window_frame.size())
        if frame_rect.adjusted(-self._resize_margin, -self._resize_margin, self._resize_margin, self._resize_margin).contains(pos):
            self._update_resize_cursor(pos)
        else:
            self.unsetCursor()

    def _handle_resize_mouse_event(self, event):
        if event.type() in (QEvent.Leave, QEvent.MouseButtonRelease):
            self.unsetCursor()
            return False

        if not hasattr(event, "position"):
            return False
        pos = self.mapFromGlobal(event.globalPosition().toPoint())
        edges = self._resize_edges_at(pos)

        if event.type() == QEvent.MouseMove:
            self._update_resize_cursor(pos)
            return False

        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton and edges:
            window_handle = self.windowHandle()
            if window_handle is not None and window_handle.startSystemResize(edges):
                return True
        return False

    def mouseMoveEvent(self, event):
        self._update_resize_cursor(event.position().toPoint())
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            edges = self._resize_edges_at(event.position().toPoint())
            if edges:
                window_handle = self.windowHandle()
                if window_handle is not None and window_handle.startSystemResize(edges):
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.unsetCursor()
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self.unsetCursor()
        super().leaveEvent(event)

    def _setup_actions(self):
        paste_action = QAction(self)
        paste_action.setShortcut(QKeySequence.Paste)
        paste_action.setShortcutContext(Qt.ApplicationShortcut)
        paste_action.triggered.connect(self.on_paste)
        self.addAction(paste_action)

        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.copy_shortcut.setContext(Qt.ApplicationShortcut)
        self.copy_shortcut.activated.connect(self.copy_current_view)

        save_action = QAction(self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.setShortcutContext(Qt.ApplicationShortcut)
        save_action.triggered.connect(self.save_current_project)
        self.addAction(save_action)

        close_tab_action = QAction(self)
        close_tab_action.setShortcut(QKeySequence("Ctrl+W"))
        close_tab_action.setShortcutContext(Qt.ApplicationShortcut)
        close_tab_action.triggered.connect(self.close_current_tab)
        self.addAction(close_tab_action)

        new_tab_action = QAction(self)
        new_tab_action.setShortcut(QKeySequence("Ctrl+T"))
        new_tab_action.setShortcutContext(Qt.ApplicationShortcut)
        new_tab_action.triggered.connect(self.add_new_tab)
        self.addAction(new_tab_action)

        self.swap_ab_shortcut = QShortcut(QKeySequence(Qt.Key_Tab), self)
        self.swap_ab_shortcut.setContext(Qt.ApplicationShortcut)
        self.swap_ab_shortcut.activated.connect(self.swap_current_tab_images)

    def load_global_label_style_copy(self):
        return self.global_label_style.copy()

    def current_tab(self):
        if 0 <= self.current_tab_index < len(self.tabs):
            return self.tabs[self.current_tab_index]
        return None

    def refresh_tab_bar(self):
        titles = [t.tab_title for t in self.tabs]
        self.tab_bar.rebuild(titles, self.current_tab_index)
        self.update_compare_status()

    def add_new_tab(self, set_current=True, title=DEFAULT_TAB_TITLE):
        tab = CompareTab(self, title=title)
        self.tabs.append(tab)
        self.central_stack.addWidget(tab)

        if set_current:
            self.current_tab_index = len(self.tabs) - 1
            self.central_stack.setCurrentWidget(tab)

        self.refresh_tab_bar()
        return tab

    def swap_current_tab_images(self):
        tab = self.current_tab()
        if tab is not None and tab.is_compare_mode():
            tab.compare_canvas.swap_images()

    def switch_tab(self, index):
        if not (0 <= index < len(self.tabs)):
            return

        self.current_tab_index = index
        tab = self.tabs[index]
        self.central_stack.setCurrentWidget(tab)
        self.tab_bar.update_active(index)
        self.update_compare_status()

        if self.label_style_dialog is not None and self.label_style_dialog.isVisible():
            self.label_style_dialog.close()
            self.label_style_dialog = None

    def close_tab(self, index):
        if not (0 <= index < len(self.tabs)):
            return

        if len(self.tabs) <= 1:
            self.tabs[0].reset_to_blank()
            self.current_tab_index = 0
            self.central_stack.setCurrentWidget(self.tabs[0])
            self.refresh_tab_bar()
            return

        tab = self.tabs.pop(index)

        if self.label_style_dialog is not None and self.label_style_dialog.isVisible():
            self.label_style_dialog.close()
            self.label_style_dialog = None

        self.central_stack.removeWidget(tab)
        tab.deleteLater()

        if self.current_tab_index >= len(self.tabs):
            self.current_tab_index = len(self.tabs) - 1
        elif index < self.current_tab_index:
            self.current_tab_index -= 1
        elif index == self.current_tab_index:
            self.current_tab_index = max(0, min(index, len(self.tabs) - 1))

        self.central_stack.setCurrentWidget(self.tabs[self.current_tab_index])
        self.refresh_tab_bar()

    def close_current_tab(self):
        self.close_tab(self.current_tab_index)

    def refresh_current_tab_title(self):
        self.refresh_tab_bar()

    def update_window_title(self):
        title = self.base_title
        self.setWindowTitle(title)
        if hasattr(self, "title_bar"):
            self.title_bar.set_title(title)
            self.title_bar.set_pinned(self.always_on_top)

    def apply_always_on_top(self):
        if sys.platform == "win32":
            hwnd = int(self.winId())
            hwnd_insert_after = -1 if self.always_on_top else -2  # HWND_TOPMOST / HWND_NOTOPMOST
            flags = 0x0001 | 0x0002  # SWP_NOSIZE | SWP_NOMOVE
            ok = ctypes.windll.user32.SetWindowPos(hwnd, hwnd_insert_after, 0, 0, 0, 0, flags)
            if not ok:
                self.setWindowFlag(Qt.WindowStaysOnTopHint, self.always_on_top)
                self.show()
        else:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, self.always_on_top)
            self.show()
        self.update_window_title()
        if hasattr(self, "title_bar"):
            self._update_window_chrome()

    def toggle_always_on_top(self):
        self.always_on_top = not self.always_on_top
        self.apply_always_on_top()

    def update_compare_status(self):
        tab = self.current_tab()
        if tab:
            self.status_label.setText(tab.get_status_text())
        else:
            self.status_label.setText("请添加 A / B 图片")

    def current_tab_can_save_project(self):
        tab = self.current_tab()
        if tab is None:
            return False
        return tab.img_a is not None and tab.img_b is not None and tab.is_compare_mode()

    def current_tab_can_open_compare_settings(self):
        tab = self.current_tab()
        return tab is not None and tab.is_compare_mode()

    def open_project_from_menu(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开对比工程",
            "",
            PROJECT_FILTER
        )
        if not path:
            return

        tab = self.current_tab()

        if tab is None:
            self.open_project_file(path, in_new_tab=True)
            return

        is_blank_tab = (tab.img_a is None and tab.img_b is None)

        if is_blank_tab:
            tab.open_project_file(path)
        else:
            self.open_project_file(path, in_new_tab=True)

    def show_bottom_left_menu(self):
        self.action_save_project.setEnabled(self.current_tab_can_save_project())
        self.action_compare_settings.setEnabled(self.current_tab_can_open_compare_settings())
        self.help_button.setDown(True)

        menu_pos = self.bottom_bar_widget.mapToGlobal(
            self.help_button.geometry().topLeft()
        )
        menu_pos.setY(menu_pos.y() - self.bottom_menu.sizeHint().height() - 6)

        self.bottom_menu.exec(menu_pos)
        self.help_button.setDown(False)


    def show_about_dialog(self):
        dialog = RoundedDialog("关于", self)
        dialog.setMinimumWidth(440)
        dialog.setMinimumHeight(210)
        dialog.content_layout.setContentsMargins(24, 22, 24, 22)

        content = QLabel(
            """
            <div style="line-height:1.7;">
                <div style="font-size:16px; font-weight:bold; color:#ffffff;">
                    图片对比工具
                </div>
                <div style="color:#cfcfcf;">
                    版本：1.6<br>
                    快速反馈：<a href="https://my.feishu.cn/share/base/form/shrcnu1BRg8IsfimXzWCCFhbSXd" style="color:#6aa9ff;">https://my.feishu.cn/share/base/form/shrcnu1BRg8IsfimXzWCCFhbSXd</a><br>
                    GitHub：<a href="https://github.com/shawnlone/ImageCompareTool" style="color:#6aa9ff;">https://github.com/shawnlone/ImageCompareTool</a>
                </div>
            </div>
            """
        )
        content.setTextFormat(Qt.RichText)
        content.setOpenExternalLinks(True)
        content.setWordWrap(True)
        dialog.content_layout.addWidget(content)
        dialog.exec()

    def toggle_help_popup(self):
        tab = self.current_tab()
        if tab:
            tab.toggle_help_popup()

    def copy_current_view(self):
        tab = self.current_tab()
        if tab:
            tab.copy_current_view()

    def save_current_project(self):
        tab = self.current_tab()
        if tab:
            tab.save_current_project()

    def on_paste(self):
        tab = self.current_tab()
        if tab:
            tab.on_paste()

    def open_project_file(self, path, in_new_tab=True):
        if in_new_tab:
            tab = self.add_new_tab(set_current=True)
        else:
            tab = self.current_tab()
            if tab is None:
                tab = self.add_new_tab(set_current=True)

        ok = tab.open_project_file(path)
        if not ok and in_new_tab and len(self.tabs) > 1:
            self.close_tab(self.tabs.index(tab))
        return ok

    def get_current_label_style(self):
        tab = self.current_tab()
        if tab:
            return tab.label_style
        return self.load_global_label_style_copy()

    def update_label_style(self, cfg):
        tab = self.current_tab()
        if tab:
            tab.update_label_style(cfg)
            self.global_label_style = tab.label_style.copy()
            self.save_label_style()

    def open_label_style_dialog(self):
        tab = self.current_tab()
        if tab is None:
            return
        if self.label_style_dialog is not None:
            self.label_style_dialog.close()
        self.label_style_dialog = LabelStyleDialog(self)
        self.label_style_dialog.show()
        self.label_style_dialog.raise_()
        self.label_style_dialog.activateWindow()

    def load_label_style(self):
        path = get_config_path()
        data = LABEL_STYLE_DEFAULTS.copy()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                data.update(saved)
            except Exception as e:
                print(f"读取配置失败: {e}", file=sys.stderr)
        return data

    def save_label_style(self):
        try:
            with open(get_config_path(), "w", encoding="utf-8") as f:
                json.dump(self.global_label_style, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}", file=sys.stderr)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.MouseButtonRelease, QEvent.WindowDeactivate, QEvent.ApplicationDeactivate):
            self.unsetCursor()

        if event.type() == QEvent.MouseMove:
            widget = obj if isinstance(obj, QWidget) else None
            if widget is not None and (widget == self or self.isAncestorOf(widget)):
                self._refresh_cursor_under_mouse()

        if obj in (self.window_host, self.window_frame) and self._handle_resize_mouse_event(event):
            return True

        tab = self.current_tab()
        if tab and tab.help_popup.isVisible():
            if event.type() in (QEvent.MouseButtonPress, QEvent.WindowDeactivate, QEvent.ApplicationDeactivate):
                w = QApplication.widgetAt(QCursor.pos())
                if w is not None:
                    inside_help = (w == tab.help_popup) or tab.help_popup.isAncestorOf(w)
                    on_help_btn = (w == self.help_button) or self.help_button.isAncestorOf(w)
                    if not inside_help and not on_help_btn:
                        tab.help_popup.hide()
                else:
                    tab.help_popup.hide()
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        tab = self.current_tab()

        if event.key() == Qt.Key_C and event.modifiers() == Qt.ControlModifier:
            self.copy_current_view()
            return

        if event.key() == Qt.Key_T and event.modifiers() != Qt.ControlModifier:
            self.toggle_always_on_top()
            return

        if tab is not None and tab.is_compare_mode():
            if event.key() == Qt.Key_Space:
                tab.compare_canvas.toggle_grayscale_mode()
                return
            if event.key() == Qt.Key_1:
                tab.compare_canvas.show_only_a()
                return
            if event.key() == Qt.Key_2:
                tab.compare_canvas.show_only_b()
                return
            if event.key() == Qt.Key_F:
                self.open_label_style_dialog()
                return

        super().keyPressEvent(event)
