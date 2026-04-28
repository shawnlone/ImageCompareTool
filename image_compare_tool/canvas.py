from PIL import Image

from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QFont, QGuiApplication, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from .constants import LABEL_STYLE_DEFAULTS
from .dnd import accept_drop_if_has_file, handle_drop_event
from .image_utils import pil_to_qimage, prepare_compare_images, to_grayscale_rgba

ZOOM_STEP = 1.1
MIN_ZOOM = 0.4 / ZOOM_STEP
MAX_ZOOM = 2.0 * ZOOM_STEP


class CompareCanvas(QWidget):
    def __init__(self, parent=None, compare_tab=None):
        super().__init__(parent)
        self.compare_tab = compare_tab
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAcceptDrops(True)

        self.img_a = None
        self.img_b = None
        self.pm_a = None
        self.pm_b = None

        self.src_img_a = None
        self.src_img_b = None
        self.grayscale_mode = False

        self.orig_w = 0
        self.orig_h = 0
        self.swapped = False

        self.zoom = None
        self.split = 0.0
        self.vp_x = 0.0
        self.vp_y = 0.0

        self.right_dragging = False
        self.right_dragged = False
        self.rpan_start = QPointF()
        self.rpan_vp_start = QPointF()

        self.left_dragging = False
        self.handle_y = None

        self.zoom_job = QTimer(self)
        self.zoom_job.setSingleShot(True)
        self.zoom_job.timeout.connect(self.finish_high_quality_render)

        self.drag_quality_job = QTimer(self)
        self.drag_quality_job.setSingleShot(True)
        self.drag_quality_job.timeout.connect(self.finish_high_quality_render)

        self.hq_mode = True

    def notify_status_changed(self):
        if self.compare_tab and self.compare_tab.main_window:
            self.compare_tab.main_window.update_compare_status()

    def get_effective_zoom(self):
        if self.pm_a is None or self.orig_w <= 0 or self.orig_h <= 0:
            return 1.0

        dpr = self.devicePixelRatioF()
        if dpr <= 0:
            dpr = 1.0

        if self.zoom is None:
            cw = max(self.width(), 1)
            ch = max(self.height(), 1)
            fit_zoom = min(cw / self.orig_w, ch / self.orig_h)
            return fit_zoom * dpr

        return self.zoom * dpr

    def get_status_text(self):
        if self.pm_a is None or self.pm_b is None or self.orig_w <= 0 or self.orig_h <= 0:
            return "未加载图片"

        scale_percent = self.get_effective_zoom() * 100
        return f"尺寸: {self.orig_w} × {self.orig_h}    缩放: {scale_percent:.0f}%"

    def render_compare_to_image(self, out_w=None, out_h=None):
        if self.pm_a is None or self.pm_b is None or self.orig_w <= 0 or self.orig_h <= 0:
            return QImage()

        target_w = int(out_w if out_w is not None else self.orig_w)
        target_h = int(out_h if out_h is not None else self.orig_h)

        if target_w <= 0 or target_h <= 0:
            return QImage()

        image = QImage(target_w, target_h, QImage.Format_RGBA8888)
        image.fill(QColor("#202020"))

        p = QPainter(image)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        z = target_w / self.orig_w
        img_left = 0.0
        img_top = 0.0
        img_w = float(target_w)
        img_h = float(target_h)
        img_rect = QRectF(img_left, img_top, img_w, img_h)

        sx = self.split * z
        sx = max(0.0, min(sx, float(target_w)))

        left_clip = QRectF(0, 0, sx, target_h)
        p.save()
        p.setClipRect(left_clip)
        p.drawPixmap(img_rect, self.pm_a, QRectF(0, 0, self.orig_w, self.orig_h))
        p.restore()

        right_clip = QRectF(sx, 0, float(target_w) - sx, target_h)
        p.save()
        p.setClipRect(right_clip)
        p.drawPixmap(img_rect, self.pm_b, QRectF(0, 0, self.orig_w, self.orig_h))
        p.restore()

        hide_split_line = self.compare_tab.label_style.get("hide_split_line", False) if self.compare_tab else False
        if not hide_split_line:
            p.setPen(QPen(QColor("#9A9A9A"), 1))
            p.drawLine(int(sx), 0, int(sx), target_h)
            handle_w = 8
            handle_h = 20
            if self.handle_y is None:
                handle_y = self.orig_h / 2
            else:
                handle_y = self.handle_y
            handle_center_y = handle_y * z
            handle_center_y = max(handle_h / 2, min(handle_center_y, target_h - handle_h / 2))
            handle_rect = QRectF(
                sx - handle_w / 2,
                handle_center_y - handle_h / 2,
                handle_w,
                handle_h
            )
            path = QPainterPath()
            path.addRoundedRect(handle_rect, 3, 3)
            p.fillPath(path, QColor("#DDDDDD"))
            p.setPen(QPen(QColor("#252525FF"), 1))
            p.drawPath(path)
            p.setPen(QColor("#808080"))
            font = QFont("Microsoft YaHei", 8)
            p.setFont(font)
            p.drawText(handle_rect, Qt.AlignCenter, "≡")

        self._draw_labels(p, img_left, img_top, img_w, img_h, sx, view_w=target_w, view_h=target_h)
        p.end()

        return image

    def copy_current_view_to_clipboard(self):
        qimg = self.render_compare_to_image(self.orig_w, self.orig_h)
        if qimg.isNull():
            return False
        QGuiApplication.clipboard().setImage(qimg)
        return True

    def load_images(self, pil_a: Image.Image, pil_b: Image.Image):
        src_a, src_b, w, h = prepare_compare_images(pil_a, pil_b)
        self.set_prepared_images(src_a, src_b, w, h)

    def set_prepared_images(self, src_a: Image.Image, src_b: Image.Image, w: int, h: int):
        self.src_img_a = src_a
        self.src_img_b = src_b
        if self.grayscale_mode:
            self.img_a = to_grayscale_rgba(self.src_img_a)
            self.img_b = to_grayscale_rgba(self.src_img_b)
        else:
            self.img_a = self.src_img_a
            self.img_b = self.src_img_b

        self.pm_a = QPixmap.fromImage(pil_to_qimage(self.img_a))
        self.pm_b = QPixmap.fromImage(pil_to_qimage(self.img_b))

        self.orig_w = w
        self.orig_h = h
        self.swapped = False
        self.handle_y = h / 2

        self.zoom = None
        self.split = w / 2
        self.vp_x = 0.0
        self.vp_y = 0.0
        self.hq_mode = True

        self.update()
        self.notify_status_changed()

    def swap_images(self):
        self.img_a, self.img_b = self.img_b, self.img_a
        self.pm_a, self.pm_b = self.pm_b, self.pm_a
        self.swapped = not self.swapped
        self.split = self.orig_w - self.split
        self.update()
        self.notify_status_changed()

    def fit_to_window(self):
        self.zoom = None
        self.hq_mode = True
        self.update()
        self.notify_status_changed()

    def original_size(self, pos=None):
        if self.pm_a is None:
            return

        cw = max(self.width(), 1)
        ch = max(self.height(), 1)

        if pos is None:
            mx, my = cw / 2, ch / 2
        else:
            mx, my = pos.x(), pos.y()

        if self.zoom is None:
            fit_zoom = min(cw / self.orig_w, ch / self.orig_h)
            fit_dw = self.orig_w * fit_zoom
            fit_dh = self.orig_h * fit_zoom
            fit_left = (cw - fit_dw) / 2
            fit_top = (ch - fit_dh) / 2
            wx = (mx - fit_left) / fit_zoom
            wy = (my - fit_top) / fit_zoom
        else:
            wx = self.vp_x + mx / self.zoom
            wy = self.vp_y + my / self.zoom

        dpr = self.devicePixelRatioF()
        if dpr <= 0:
            dpr = 1.0
        self.zoom = 1.0 / dpr
        self.vp_x = wx - mx / self.zoom
        self.vp_y = wy - my / self.zoom

        self.hq_mode = True
        self.update()
        self.notify_status_changed()

    def _ensure_fit_zoom(self):
        if self.zoom is None:
            cw = max(self.width(), 1)
            ch = max(self.height(), 1)
            self.zoom = min(cw / self.orig_w, ch / self.orig_h)
            dw = self.orig_w * self.zoom
            dh = self.orig_h * self.zoom
            self.vp_x = -(cw - dw) / (2 * self.zoom)
            self.vp_y = -(ch - dh) / (2 * self.zoom)

    def schedule_hq(self, delay=80):
        self.drag_quality_job.start(delay)

    def finish_high_quality_render(self):
        self.hq_mode = True
        self.update()

    def mousePressEvent(self, event):
        if self.pm_a is None:
            return

        self._ensure_fit_zoom()

        if event.button() == Qt.MiddleButton:
            self.original_size(event.position())
            return

        if event.button() == Qt.LeftButton:
            self.left_dragging = True
            z = self.zoom
            self.split = (event.position().x() + self.vp_x * z) / z
            self.split = max(0, min(self.split, self.orig_w))
            self.handle_y = (event.position().y() + self.vp_y * z) / z
            self.handle_y = max(0, min(self.handle_y, self.orig_h))
            self.update()

        elif event.button() == Qt.RightButton:
            self.right_dragging = True
            self.right_dragged = False
            self.rpan_start = event.position()
            self.rpan_vp_start = QPointF(self.vp_x, self.vp_y)

    def mouseMoveEvent(self, event):
        if self.pm_a is None:
            return

        if self.left_dragging:
            z = self.zoom
            self.split = (event.position().x() + self.vp_x * z) / z
            self.split = max(0, min(self.split, self.orig_w))
            self.handle_y = (event.position().y() + self.vp_y * z) / z
            self.handle_y = max(0, min(self.handle_y, self.orig_h))
            self.update()

        elif self.right_dragging:
            self.right_dragged = True
            z = self.zoom
            dx = event.position().x() - self.rpan_start.x()
            dy = event.position().y() - self.rpan_start.y()
            self.vp_x = self.rpan_vp_start.x() - dx / z
            self.vp_y = self.rpan_vp_start.y() - dy / z
            self.hq_mode = False
            self.update()
            self.schedule_hq()

    def mouseReleaseEvent(self, event):
        if self.pm_a is None:
            return

        if event.button() == Qt.LeftButton:
            self.left_dragging = False
            self.hq_mode = True
            self.update()

        elif event.button() == Qt.RightButton:
            self.right_dragging = False
            if not self.right_dragged:
                self.fit_to_window()
            else:
                self.hq_mode = True
                self.update()

    def wheelEvent(self, event):
        if self.pm_a is None:
            return

        self._ensure_fit_zoom()

        mx = event.position().x()
        my = event.position().y()
        wx = self.vp_x + mx / self.zoom
        wy = self.vp_y + my / self.zoom

        factor = ZOOM_STEP if event.angleDelta().y() > 0 else 1 / ZOOM_STEP
        self.zoom = max(MIN_ZOOM, min(self.zoom * factor, MAX_ZOOM))

        self.vp_x = wx - mx / self.zoom
        self.vp_y = wy - my / self.zoom

        self.hq_mode = False
        self.update()
        self.zoom_job.start(120)
        self.notify_status_changed()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor("#202020"))

        if self.pm_a is None or self.pm_b is None:
            p.end()
            return

        self._ensure_fit_zoom()

        cw = self.width()
        ch = self.height()
        z = self.zoom

        img_left = -self.vp_x * z
        img_top = -self.vp_y * z
        img_w = self.orig_w * z
        img_h = self.orig_h * z
        img_rect = QRectF(img_left, img_top, img_w, img_h)

        p.setRenderHint(QPainter.SmoothPixmapTransform, self.hq_mode)

        sx = self.split * z - self.vp_x * z
        sx = max(0.0, min(sx, float(cw)))

        left_clip = QRectF(0, 0, sx, ch)
        p.save()
        p.setClipRect(left_clip)
        p.drawPixmap(img_rect, self.pm_a, QRectF(0, 0, self.orig_w, self.orig_h))
        p.restore()

        right_clip = QRectF(sx, 0, float(cw) - sx, ch)
        p.save()
        p.setClipRect(right_clip)
        p.drawPixmap(img_rect, self.pm_b, QRectF(0, 0, self.orig_w, self.orig_h))
        p.restore()

        hide_split_line = self.compare_tab.label_style.get("hide_split_line", False) if self.compare_tab else False
        if not hide_split_line:
            p.setPen(QPen(QColor("#9A9A9A"), 1))
            line_top = max(0, int(img_top))
            line_bottom = min(ch, int(img_top + img_h))
            p.drawLine(int(sx), line_top, int(sx), line_bottom)
            handle_w = 8
            handle_h = 20
            if self.handle_y is None:
                self.handle_y = self.orig_h / 2
            handle_center_y = img_top + self.handle_y * z
            handle_center_y = max(img_top + handle_h / 2, min(handle_center_y, img_top + img_h - handle_h / 2))
            handle_rect = QRectF(
                sx - handle_w / 2,
                handle_center_y - handle_h / 2,
                handle_w,
                handle_h
            )
            path = QPainterPath()
            path.addRoundedRect(handle_rect, 3, 3)
            p.fillPath(path, QColor("#DDDDDD"))
            p.setPen(QPen(QColor("#252525FF"), 1))
            p.drawPath(path)
            p.setPen(QColor("#808080"))
            font = QFont("Microsoft YaHei", 8)
            p.setFont(font)
            p.drawText(handle_rect, Qt.AlignCenter, "≡")

        self._draw_labels(p, img_left, img_top, img_w, img_h, sx)
        p.end()

    def _draw_labels(self, p: QPainter, img_left, img_top, img_w, img_h, split_x, view_w=None, view_h=None):
        pad = 12
        vw = self.width() if view_w is None else view_w
        vh = self.height() if view_h is None else view_h

        img_right = img_left + img_w
        img_bottom = img_top + img_h

        clip_gap = 1.0
        left_visible_l = max(0, img_left)
        left_visible_r = min(vw, split_x - clip_gap)
        right_visible_l = max(0, split_x + clip_gap)
        right_visible_r = min(vw, img_right)

        left_visible = (left_visible_r - left_visible_l) > 1
        right_visible = (right_visible_r - right_visible_l) > 1

        cfg = self.compare_tab.label_style if self.compare_tab else LABEL_STYLE_DEFAULTS

        label_a = cfg["b_text"] if self.swapped else cfg["a_text"]
        label_b = cfg["a_text"] if self.swapped else cfg["b_text"]
        color_a = cfg["b_text_color"] if self.swapped else cfg["a_text_color"]
        color_b = cfg["a_text_color"] if self.swapped else cfg["b_text_color"]

        font = QFont("Microsoft YaHei", cfg["font_size"])
        font.setBold(True)
        p.setFont(font)

        fm = p.fontMetrics()

        def draw_one(text, x, y, text_color, align_right=False):
            tw = fm.horizontalAdvance(text)
            th = fm.height()
            rw = tw + 24
            rh = th + 12

            if align_right:
                rect = QRectF(x - rw, y, rw, rh)
            else:
                rect = QRectF(x, y, rw, rh)

            path = QPainterPath()
            path.addRoundedRect(rect, 6, 6)
            bg = QColor(cfg["bg_color"])
            bg.setAlpha(cfg.get("bg_alpha", 170))
            p.fillPath(path, bg)
            p.setPen(QColor(text_color))
            p.drawText(rect, Qt.AlignCenter, text)

        pos = cfg["position"]
        offset_x = cfg["offset_x"]
        offset_y = cfg["offset_y"]

        if pos == "top":
            ay = max(pad, img_top + pad) + offset_y
            by = max(pad, img_top + pad) + offset_y
        elif pos == "center":
            ay = img_top + (img_h - (fm.height() + 12)) / 2 + offset_y
            by = img_top + (img_h - (fm.height() + 12)) / 2 + offset_y
        else:
            ay = min(vh - pad - (fm.height() + 12), img_bottom - pad - (fm.height() + 12)) - offset_y
            by = min(vh - pad - (fm.height() + 12), img_bottom - pad - (fm.height() + 12)) - offset_y

        ax = max(pad, img_left + pad) + offset_x
        bx = min(vw - pad, img_right - pad) - offset_x

        if left_visible:
            p.save()
            p.setClipRect(QRectF(left_visible_l, 0, max(0.0, left_visible_r - left_visible_l), vh))
            draw_one(label_a, ax, ay, color_a, align_right=False)
            p.restore()

        if right_visible:
            p.save()
            p.setClipRect(QRectF(right_visible_l, 0, max(0.0, right_visible_r - right_visible_l), vh))
            draw_one(label_b, bx, by, color_b, align_right=True)
            p.restore()

    def dragEnterEvent(self, event: QDragEnterEvent):
        accept_drop_if_has_file(event)

    def dropEvent(self, event: QDropEvent):
        handle_drop_event(
            event,
            self.compare_tab,
            ask_replace=True,
            project_in_new_tab=True
        )

    def toggle_grayscale_mode(self):
        if self.src_img_a is None or self.src_img_b is None:
            return

        self.grayscale_mode = not self.grayscale_mode

        if self.grayscale_mode:
            self.img_a = to_grayscale_rgba(self.src_img_a)
            self.img_b = to_grayscale_rgba(self.src_img_b)
        else:
            self.img_a = self.src_img_a
            self.img_b = self.src_img_b

        self.pm_a = QPixmap.fromImage(pil_to_qimage(self.img_a))
        self.pm_b = QPixmap.fromImage(pil_to_qimage(self.img_b))

        self.update()
        self.notify_status_changed()

    def show_only_a(self):
        if self.pm_a is None:
            return
        self.split = self.orig_w
        self.update()
        self.notify_status_changed()

    def show_only_b(self):
        if self.pm_a is None:
            return
        self.split = 0
        self.update()
        self.notify_status_changed()
