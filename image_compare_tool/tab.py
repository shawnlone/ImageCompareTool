import os

from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox, QStackedLayout, QVBoxLayout, QWidget

from .canvas import CompareCanvas
from .constants import DEFAULT_TAB_TITLE, IMAGE_FILTER, LABEL_STYLE_DEFAULTS, PROJECT_EXT, PROJECT_FILTER
from .image_utils import pil_to_qimage, qimage_to_pil
from .pages import EmptyComparePage
from .project_io import load_project_file, save_project_file
from .widgets import HelpPopup, ToastPopup
from .workers import ComparePrepareWorker, ImageLoadWorker, WorkerSignals

class CompareTab(QWidget):
    def __init__(self, main_window, title=DEFAULT_TAB_TITLE):
        super().__init__()
        self.main_window = main_window
        self.tab_title = title
        self.status_message_prefix = ""

        self.label_style = self.main_window.load_global_label_style_copy()

        self.img_a = None
        self.img_b = None

        self.empty_page = EmptyComparePage(self)
        self.compare_canvas = CompareCanvas(compare_tab=self)

        self.worker_signals = WorkerSignals(self)
        self.worker_signals.image_loaded.connect(self._on_image_loaded)
        self.worker_signals.compare_ready.connect(self._on_compare_ready)
        self.worker_signals.error.connect(self._on_worker_error)
        self.thread_pool = QThreadPool.globalInstance()
        self._image_load_token = 0
        self._image_load_tokens = {"a": 0, "b": 0}
        self._compare_prepare_token = 0

        self.help_popup = HelpPopup(self)
        self.toast_popup = ToastPopup(self)

        self.content_stack_host = QWidget()
        self.content_stack = QStackedLayout(self.content_stack_host)
        self.content_stack.setContentsMargins(0, 0, 0, 0)
        self.content_stack.setSpacing(0)
        self.content_stack.addWidget(self.empty_page)
        self.content_stack.addWidget(self.compare_canvas)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.content_stack_host, 1)

        self.content_stack.setCurrentWidget(self.empty_page)

    def set_tab_title(self, title):
        self.tab_title = title or DEFAULT_TAB_TITLE
        self.main_window.refresh_tab_bar()

    def base_name_from_path(self, path):
        return os.path.splitext(os.path.basename(path))[0] or DEFAULT_TAB_TITLE


    def is_compare_mode(self):
        return self.content_stack.currentWidget() == self.compare_canvas

    def get_status_text(self):
        if self.img_a is None or self.img_b is None:
            return "请添加 A / B 图片"
        return self.compare_canvas.get_status_text()

    def update_compare_status(self):
        self.main_window.update_compare_status()

    def show_toast(self, text, duration_ms=2000):
        self.toast_popup.show_message(text, duration_ms)

    def start_image_load(self, side, path):
        self._image_load_token += 1
        token = self._image_load_token
        self._image_load_tokens[side] = token
        self.show_toast("正在载入图片...", 1200)
        self.thread_pool.start(ImageLoadWorker(token, side, path, self.worker_signals))

    def start_compare_prepare(self):
        if self.img_a is None or self.img_b is None:
            return
        self._compare_prepare_token += 1
        token = self._compare_prepare_token
        self.content_stack.setCurrentWidget(self.compare_canvas)
        self.show_toast("正在准备对比图...", 1200)
        self.thread_pool.start(ComparePrepareWorker(token, self.img_a, self.img_b, self.worker_signals))

    def _on_image_loaded(self, token, side, path, img):
        if token != self._image_load_tokens.get(side):
            return

        if side == "a":
            self.img_a = img
            self.empty_page.panel_a.set_preview(QPixmap.fromImage(pil_to_qimage(img)), "Before")
        else:
            self.img_b = img
            self.empty_page.panel_b.set_preview(QPixmap.fromImage(pil_to_qimage(img)), "After")

        self.set_tab_title(self.base_name_from_path(path))

        if self.img_a is not None and self.img_b is not None:
            self.start_compare_prepare()
        else:
            self.update_compare_status()

    def _on_compare_ready(self, token, src_a, src_b, w, h):
        if token != self._compare_prepare_token:
            return
        self.content_stack.setCurrentWidget(self.compare_canvas)
        self.compare_canvas.set_prepared_images(src_a, src_b, w, h)
        self.compare_canvas.setFocus()
        self.update_compare_status()
        self.help_popup.hide()

    def _on_worker_error(self, kind, token, side, title, message):
        if kind == "image" and token != self._image_load_tokens.get(side):
            return
        if kind == "compare" and token != self._compare_prepare_token:
            return
        self.show_toast(title, 2500)
        QMessageBox.warning(self, title, message)

    def toggle_help_popup(self):
        if self.help_popup.isVisible():
            self.help_popup.hide()
        else:
            self.position_help_popup()
            self.help_popup.show()
            self.help_popup.raise_()
            self.help_popup.setFocus()

    def position_help_popup(self):
        self.help_popup.adjustSize()

        left_margin = 25
        bottom_margin = 2

        popup_x = left_margin
        popup_y = self.height() - self.main_window.bottom_bar_widget.height() - self.help_popup.height() - bottom_margin

        self.help_popup.move(popup_x, max(10, popup_y))

    def ask_replace_side(self, title="替换图片", text="将图片放到哪一边？"):
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        left_btn = box.addButton("左边（A）", QMessageBox.AcceptRole)
        right_btn = box.addButton("右边（B）", QMessageBox.AcceptRole)
        box.addButton("取消", QMessageBox.RejectRole)
        box.setDefaultButton(left_btn)
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
                padding: 5px 10px;
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
        clicked = box.clickedButton()
        if clicked == left_btn:
            return "a"
        if clicked == right_btn:
            return "b"
        return None

    def open_file(self, side):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            IMAGE_FILTER
        )
        if path:
            self.place_image(side, path)

    def open_file_or_project(self, side, path):
        if path.lower().endswith(PROJECT_EXT):
            return self.open_project_file(path)
        self.place_image(side, path)
        return True

    def handle_dropped_paths(self, paths, target_side=None, ask_replace=False, project_in_new_tab=True):
        if not paths:
            return False

        first = paths[0]
        if len(paths) == 1 and first.lower().endswith(PROJECT_EXT):
            if project_in_new_tab:
                return self.main_window.open_project_file(first, in_new_tab=True)
            return self.open_project_file(first)

        if ask_replace:
            side = self.ask_replace_side("替换图片", "将拖入的图片放到哪一边？")
            if side is None:
                return False
            self.place_image(side, first)
            return True

        if len(paths) >= 2:
            self.img_a = None
            self.img_b = None
            self.place_image("a", paths[0])
            self.place_image("b", paths[1])
            return True

        if target_side is not None:
            self.place_image(target_side, first)
        else:
            self.place_image_auto(first)
        return True

    def place_image_auto(self, path):
        if path.lower().endswith(PROJECT_EXT):
            self.open_project_file(path)
            return

        if self.img_a is None:
            self.place_image("a", path)
        elif self.img_b is None:
            self.place_image("b", path)
        else:
            self.place_image("a", path)

    def place_image(self, side, path):
        if path.lower().endswith(PROJECT_EXT):
            self.open_project_file(path)
            return
        self.start_image_load(side, path)

    def on_paste(self):
        try:
            clip = QGuiApplication.clipboard()
            qimg = clip.image()
            if qimg.isNull():
                self.show_toast("剪贴板中没有图片", 1800)
                return
            pil_img = qimage_to_pil(qimg)
        except Exception as e:
            self.show_toast("读取剪贴板失败", 2200)
            QMessageBox.warning(self, "读取剪贴板失败", str(e))
            return

        if self.is_compare_mode() and self.img_a is not None and self.img_b is not None:
            side = self.ask_replace_side("粘贴图片", "将粘贴的图片放到哪一边？")
            if side is None:
                return

            if side == "a":
                self.img_a = pil_img
            else:
                self.img_b = pil_img

            self.start_compare_prepare()
            return

        if self.img_a is None:
            self.img_a = pil_img
            self.empty_page.panel_a.set_preview(
                QPixmap.fromImage(pil_to_qimage(pil_img)), "Before"
            )
        elif self.img_b is None:
            self.img_b = pil_img
            self.empty_page.panel_b.set_preview(
                QPixmap.fromImage(pil_to_qimage(pil_img)), "After"
            )
        else:
            self.img_a = pil_img
            self.empty_page.panel_a.set_preview(
                QPixmap.fromImage(pil_to_qimage(pil_img)), "Before"
            )

        if self.img_a is not None and self.img_b is not None:
            self.start_compare_prepare()
        else:
            self.update_compare_status()

    def enter_compare_mode(self):
        if self.img_a is None or self.img_b is None:
            self.content_stack.setCurrentWidget(self.empty_page)
            self.update_compare_status()
            return

        self.content_stack.setCurrentWidget(self.compare_canvas)
        self.start_compare_prepare()

    def reset_to_blank(self):
        self.img_a = None
        self.img_b = None
        self.label_style = self.main_window.load_global_label_style_copy()
        self.empty_page.reset()
        self.content_stack.setCurrentWidget(self.empty_page)
        self.help_popup.hide()
        self.set_tab_title(DEFAULT_TAB_TITLE)
        self.update_compare_status()

    def copy_current_view(self):
        if not self.is_compare_mode():
            return
        ok = self.compare_canvas.copy_current_view_to_clipboard()
        if ok:
            self.show_toast("✔️已复制对比图", 2000)

    def save_current_project(self):
        if self.img_a is None or self.img_b is None:
            QMessageBox.information(self, "提示", "当前没有可保存的对比内容。")
            return

        default_name = self.tab_title if self.tab_title else f"未命名{PROJECT_EXT}"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存对比工程",
            f"{default_name}{PROJECT_EXT}" if not default_name.lower().endswith(PROJECT_EXT) else default_name,
            PROJECT_FILTER
        )
        if not path:
            return

        try:
            save_project_file(path, self.img_a, self.img_b, self.label_style)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存工程文件失败：\n{e}")
            return

        self.set_tab_title(self.base_name_from_path(path))
        self.show_toast("✔️已保存对比工程", 2000)

    def open_project_file(self, path):
        try:
            img_a, img_b, project_style = load_project_file(path)
        except Exception as e:
            QMessageBox.critical(self, "打开失败", f"打开工程文件失败：\n{e}")
            return False

        self.img_a = img_a
        self.img_b = img_b
        self.label_style = LABEL_STYLE_DEFAULTS.copy()
        self.label_style.update(project_style)

        self.empty_page.panel_a.set_preview(QPixmap.fromImage(pil_to_qimage(img_a)), "Before")
        self.empty_page.panel_b.set_preview(QPixmap.fromImage(pil_to_qimage(img_b)), "After")

        self.set_tab_title(self.base_name_from_path(path))
        self.start_compare_prepare()

        if self.main_window.label_style_dialog is not None:
            self.main_window.label_style_dialog.close()
            self.main_window.label_style_dialog = None

        #self.show_temporary_status_prefix("✔️已打开对比工程", 3000)
        return True

    def update_label_style(self, cfg):
        self.label_style.update(cfg)
        self.compare_canvas.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.help_popup.isVisible():
            self.position_help_popup()
        if self.toast_popup.isVisible():
            self.toast_popup.reposition()
