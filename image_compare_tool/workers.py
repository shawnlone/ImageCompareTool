from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from .image_utils import open_image_rgba, prepare_compare_images

class WorkerSignals(QObject):
    image_loaded = Signal(int, str, str, object)
    compare_ready = Signal(int, object, object, int, int)
    error = Signal(str, int, str, str, str)


class ImageLoadWorker(QRunnable):
    def __init__(self, token, side, path, signals):
        super().__init__()
        self.token = token
        self.side = side
        self.path = path
        self.signals = signals

    @Slot()
    def run(self):
        try:
            img = open_image_rgba(self.path)
        except Exception as e:
            self.signals.error.emit("image", self.token, self.side, "打开图片失败", f"{self.path}\n{e}")
            return
        self.signals.image_loaded.emit(self.token, self.side, self.path, img)


class ComparePrepareWorker(QRunnable):
    def __init__(self, token, pil_a, pil_b, signals):
        super().__init__()
        self.token = token
        self.pil_a = pil_a
        self.pil_b = pil_b
        self.signals = signals

    @Slot()
    def run(self):
        try:
            src_a, src_b, w, h = prepare_compare_images(self.pil_a, self.pil_b)
        except Exception as e:
            self.signals.error.emit("compare", self.token, "", "准备对比图失败", str(e))
            return
        self.signals.compare_ready.emit(self.token, src_a, src_b, w, h)
