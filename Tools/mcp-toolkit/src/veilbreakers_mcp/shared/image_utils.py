"""Image utilities for contact sheet composition and screenshot processing."""
import io
import math
from PIL import Image as PILImage

DEFAULT_CONTACT_ANGLES = [
    (0, 0),       # Front
    (90, 0),      # Right
    (180, 0),     # Back
    (270, 0),     # Left
    (0, 90),      # Top
    (45, 30),     # 3/4 View
]


def compose_contact_sheet(
    image_paths: list[str],
    cols: int = 3,
    bg_color: tuple[int, int, int] = (30, 30, 30),
    label_angles: list[str] | None = None,
) -> bytes:
    """Compose multiple render images into a single grid contact sheet."""
    if not image_paths:
        raise ValueError("No images to compose")

    images = [PILImage.open(p) for p in image_paths]
    w, h = images[0].size
    rows = math.ceil(len(images) / cols)
    sheet = PILImage.new("RGB", (w * cols, h * rows), bg_color)

    for i, img in enumerate(images):
        x = (i % cols) * w
        y = (i // cols) * h
        if img.size != (w, h):
            img = img.resize((w, h), PILImage.Resampling.LANCZOS)
        sheet.paste(img, (x, y))

    buf = io.BytesIO()
    sheet.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def resize_screenshot(
    image_bytes: bytes,
    max_size: int = 1024,
) -> bytes:
    """Resize a screenshot to fit within max_size while preserving aspect ratio."""
    img = PILImage.open(io.BytesIO(image_bytes))
    if max(img.size) <= max_size:
        return image_bytes

    ratio = max_size / max(img.size)
    new_size = (int(img.width * ratio), int(img.height * ratio))
    img = img.resize(new_size, PILImage.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
