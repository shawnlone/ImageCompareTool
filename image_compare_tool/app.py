import os
import sys
import ctypes

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox

from .constants import PROJECT_EXT
from .image_utils import open_image_rgba, pil_to_qimage, resource_path
from .main_window import MainWindow


def set_windows_app_id():
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "shawnlone.ImageCompareTool"
        )
    except Exception:
        pass


def main():
    set_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName("图片对比工具")
    app.setWindowIcon(QIcon(resource_path("app.ico")))

    win = MainWindow()

    if len(sys.argv) == 2:
        p = sys.argv[1]
        if os.path.exists(p) and p.lower().endswith(PROJECT_EXT):
            QTimer.singleShot(100, lambda: win.open_project_file(p, in_new_tab=False))

    elif len(sys.argv) == 3:
        a, b = sys.argv[1], sys.argv[2]
        if os.path.exists(a) and os.path.exists(b):
            def load_two():
                tab = win.current_tab()
                if tab is None:
                    tab = win.add_new_tab(set_current=True)
                try:
                    tab.img_a = open_image_rgba(a)
                    tab.img_b = open_image_rgba(b)
                    tab.empty_page.panel_a.set_preview(QPixmap.fromImage(pil_to_qimage(tab.img_a)), "Before")
                    tab.empty_page.panel_b.set_preview(QPixmap.fromImage(pil_to_qimage(tab.img_b)), "After")
                    tab.start_compare_prepare()
                except Exception as e:
                    QMessageBox.warning(win, "打开图片失败", f"{a}\n{b}\n{e}")
            QTimer.singleShot(100, load_two)

    win.show()
    sys.exit(app.exec())
if __name__ == "__main__":
    main()
