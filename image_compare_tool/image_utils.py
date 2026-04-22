import os
import sys
import tempfile

from PIL import Image
from PySide6.QtGui import QImage

def get_config_path():
    base_dir = os.path.join(tempfile.gettempdir(), "image_compare_tool")
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, "label_style.json")


def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def pil_to_qimage(pil_img: Image.Image) -> QImage:
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")

    data = pil_img.tobytes("raw", "RGBA")
    qimg = QImage(
        data,
        pil_img.width,
        pil_img.height,
        pil_img.width * 4,
        QImage.Format_RGBA8888
    ).copy()
    qimg.setDevicePixelRatio(1.0)
    return qimg


def qimage_to_pil(qimg: QImage) -> Image.Image:
    qimg = qimg.convertToFormat(QImage.Format_RGBA8888)
    width = qimg.width()
    height = qimg.height()
    ptr = qimg.bits()
    data = ptr.tobytes()
    return Image.frombytes("RGBA", (width, height), data)


def to_grayscale_rgba(pil_img: Image.Image) -> Image.Image:
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")
    gray = pil_img.convert("L")
    return Image.merge("RGBA", (gray, gray, gray, pil_img.getchannel("A")))


def open_image_rgba(path):
    with Image.open(path) as img:
        return img.convert("RGBA")


def prepare_compare_images(pil_a: Image.Image, pil_b: Image.Image):
    w = min(pil_a.width, pil_b.width)
    h = min(pil_a.height, pil_b.height)
    if w <= 0 or h <= 0:
        raise ValueError("图片尺寸无效")
    return (
        pil_a.resize((w, h), Image.LANCZOS).convert("RGBA"),
        pil_b.resize((w, h), Image.LANCZOS).convert("RGBA"),
        w,
        h,
    )
