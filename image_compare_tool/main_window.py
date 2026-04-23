import json
import os
import sys

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QAction, QCursor, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
    QMenu, QMessageBox, QPushButton, QScrollArea, QStackedLayout,
    QVBoxLayout, QWidget
)

from .constants import DEFAULT_TAB_TITLE, LABEL_STYLE_DEFAULTS, PROJECT_FILTER
from .image_utils import get_config_path, resource_path
from .tab import CompareTab
from .widgets import BottomTabBar, LabelStyleDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.base_title = "图片对比工具 1.6"
        self.always_on_top = True
        self.label_style_dialog = None
        self.global_label_style = self.load_label_style()

        self.tabs = []
        self.current_tab_index = -1

        self.update_window_title()
        self.setWindowIcon(QIcon(resource_path("app.ico")))
        self.resize(1400, 800)
        self.setMinimumSize(800, 500)

        self.tab_bar = BottomTabBar()
        self.tab_bar.current_changed.connect(self.switch_tab)
        self.tab_bar.add_requested.connect(self.add_new_tab)
        self.tab_bar.close_requested.connect(self.close_tab)

        self.help_button = QPushButton("≡")
        self.help_button.setFixedSize(28, 22)
        self.help_button.setCursor(Qt.PointingHandCursor)
        self.help_button.setFocusPolicy(Qt.NoFocus)
        self.help_button.setStyleSheet("""
            QPushButton {
                background: #1a1a1a;
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
        self.bottom_menu.setStyleSheet("""
            QMenu {
                background-color: #232323;
                color: #e8e8e8;
                border: 1px solid #3d3d3d;
                padding: 6px 0px;
            }
            QMenu::item {
                background-color: transparent;
                padding: 8px 20px 8px 18px;
            }
            QMenu::item:selected {
                background-color: #3a3a3a;
                color: white;
            }
            QMenu::item:disabled {
                color: #666666;
                background-color: transparent;
            }
        """)

        self.action_open_project = QAction("打开工程", self)
        self.action_save_project = QAction("保存工程", self)
        self.action_help_info = QAction("操作帮助", self)
        self.action_about = QAction("关于", self)

        self.action_open_project.triggered.connect(self.open_project_from_menu)
        self.action_save_project.triggered.connect(self.save_current_project)
        self.action_help_info.triggered.connect(self.toggle_help_popup)
        self.action_about.triggered.connect(self.show_about_dialog)

        self.bottom_menu.addAction(self.action_open_project)
        self.bottom_menu.addAction(self.action_save_project)
        self.bottom_menu.addSeparator()
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
        self.bottom_bar_widget.setFixedHeight(34)
        self.bottom_bar_widget.setStyleSheet("background:#1a1a1a;")

        bottom_layout = QHBoxLayout(self.bottom_bar_widget)
        bottom_layout.setContentsMargins(5, 3, 10, 3)
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
        root_layout = QVBoxLayout(self.root_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.central_stack_host, 1)
        root_layout.addWidget(self.bottom_bar_widget, 0)

        self.setCentralWidget(self.root_widget)

        self._apply_style()
        self._setup_actions()
        self.apply_always_on_top()

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        self.add_new_tab(set_current=True)

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #1e1e1e;
                color: white;
            }
            QFrame#DropPanel {
                background: #2a2a2a;
                border: none;
                border-radius: 0px;
            }
            QPushButton {
                background: #3a3a3a;
                color: #999;
                border: none;
                border-radius: 0px;
                font: bold 12pt "Microsoft YaHei";
                padding: 0px;
            }
            QPushButton:hover {
                background: #4a4a4a;
                color: white;
            }
            QScrollArea {
                border: none;
                background: #1a1a1a;
            }
        """)

    def _setup_actions(self):
        paste_action = QAction(self)
        paste_action.setShortcut(QKeySequence.Paste)
        paste_action.triggered.connect(self.on_paste)
        self.addAction(paste_action)

        copy_action = QAction(self)
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.triggered.connect(self.copy_current_view)
        self.addAction(copy_action)

        save_action = QAction(self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_current_project)
        self.addAction(save_action)

        close_tab_action = QAction(self)
        close_tab_action.setShortcut(QKeySequence("Ctrl+W"))
        close_tab_action.triggered.connect(self.close_current_tab)
        self.addAction(close_tab_action)

        new_tab_action = QAction(self)
        new_tab_action.setShortcut(QKeySequence("Ctrl+T"))
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
        if self.always_on_top:
            self.setWindowTitle(f"{self.base_title}   📌")
        else:
            self.setWindowTitle(self.base_title)

    def apply_always_on_top(self):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.always_on_top)
        self.show()
        self.update_window_title()

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
        self.help_button.setDown(True)

        menu_pos = self.bottom_bar_widget.mapToGlobal(
            self.help_button.geometry().topLeft()
        )
        menu_pos.setY(menu_pos.y() - self.bottom_menu.sizeHint().height() - 6)

        self.bottom_menu.exec(menu_pos)
        self.help_button.setDown(False)


    def show_about_dialog(self):
        box = QMessageBox(self)
        box.setWindowTitle("关于")
        box.setTextFormat(Qt.RichText)
        box.setIcon(QMessageBox.Information)
        box.setText(
            f"""
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
        box.setStandardButtons(QMessageBox.Ok)
        box.setStyleSheet("""
            QMessageBox {
                background-color: #1e1e1e;
                color: white;
            }
            QLabel {
                color: white;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px 12px;
                min-width: 80px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2f2f2f;
            }
        """)
        box.exec()

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
