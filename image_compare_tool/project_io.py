import json
import zipfile
from io import BytesIO

from PIL import Image

from .constants import LABEL_STYLE_DEFAULTS, PROJECT_EXT

def save_project_file(path, pil_a: Image.Image, pil_b: Image.Image, label_style: dict):
    if pil_a is None or pil_b is None:
        raise ValueError("缺少图片，无法保存工程文件")

    if not path.lower().endswith(PROJECT_EXT):
        path += PROJECT_EXT

    buf_a = BytesIO()
    buf_b = BytesIO()

    pil_a.convert("RGBA").save(buf_a, format="PNG")
    pil_b.convert("RGBA").save(buf_b, format="PNG")

    project_data = {
        "version": 1,
        "type": "image_compare_project",
        "label_style": label_style,
    }

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("a.png", buf_a.getvalue())
        zf.writestr("b.png", buf_b.getvalue())
        zf.writestr(
            "project.json",
            json.dumps(project_data, ensure_ascii=False, indent=2).encode("utf-8")
        )

    return path


def load_project_file(path):
    with zipfile.ZipFile(path, "r") as zf:
        names = set(zf.namelist())
        required = {"a.png", "b.png", "project.json"}
        if not required.issubset(names):
            raise ValueError("不是有效的 icp 工程文件，缺少必要内容")

        with zf.open("a.png") as fa:
            img_a = Image.open(BytesIO(fa.read())).convert("RGBA")

        with zf.open("b.png") as fb:
            img_b = Image.open(BytesIO(fb.read())).convert("RGBA")

        with zf.open("project.json") as fp:
            project_data = json.loads(fp.read().decode("utf-8"))

    label_style = LABEL_STYLE_DEFAULTS.copy()
    if isinstance(project_data, dict):
        saved_style = project_data.get("label_style", {})
        if isinstance(saved_style, dict):
            label_style.update(saved_style)

    return img_a, img_b, label_style
