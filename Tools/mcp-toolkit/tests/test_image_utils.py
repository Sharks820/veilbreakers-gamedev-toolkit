import io
import os
import tempfile
from PIL import Image as PILImage
from veilbreakers_mcp.shared.image_utils import compose_contact_sheet, resize_screenshot


def test_compose_contact_sheet():
    paths = []
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255), (255, 0, 255)]
    for i, color in enumerate(colors):
        img = PILImage.new("RGB", (64, 64), color)
        path = os.path.join(tempfile.gettempdir(), f"test_contact_{i}.png")
        img.save(path)
        paths.append(path)

    sheet_bytes = compose_contact_sheet(paths, cols=3)
    sheet = PILImage.open(io.BytesIO(sheet_bytes))
    assert sheet.size == (192, 128)


def test_resize_screenshot():
    img = PILImage.new("RGB", (2048, 1024), (128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    original_bytes = buf.getvalue()

    resized = resize_screenshot(original_bytes, max_size=512)
    result = PILImage.open(io.BytesIO(resized))
    assert max(result.size) == 512
    assert result.size == (512, 256)


def test_resize_noop_small_image():
    img = PILImage.new("RGB", (256, 256), (128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    original_bytes = buf.getvalue()

    resized = resize_screenshot(original_bytes, max_size=1024)
    assert resized == original_bytes
