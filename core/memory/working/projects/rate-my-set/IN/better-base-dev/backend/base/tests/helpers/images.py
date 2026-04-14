from __future__ import annotations

from io import BytesIO

from django.core.files.images import ImageFile
from PIL import Image

from backend.base.tests.shared import random


def create_test_image(
    filename: str,
    *,
    r: int | None = None,
    g: int | None = None,
    b: int | None = None,
    size_x: int = 128,
    size_y: int = 128,
) -> ImageFile:
    """
    Thanks to
    https://wildfish.com/blog/2014/02/27/generating-in-memory-image-for-tests-python for
    the initial inspiration. The code below used that as a starting point and then
    changed it to at least some extent.
    """
    assert filename and filename.count(".") == 1, "Current Pre-condition"
    _name, extension = filename.rsplit(".", 1)
    extension_lower = (extension or "").casefold()

    if r is not None:
        assert 0 <= r <= 255, "Current Pre-condition"
    if g is not None:
        assert 0 <= g <= 255, "Current Pre-condition"
    if b is not None:
        assert 0 <= b <= 255, "Current Pre-condition"

    final_r = random.randint(0, 255) if r is None else r
    final_g = random.randint(0, 255) if g is None else g
    final_b = random.randint(0, 255) if b is None else b

    bytes_io = BytesIO()
    bytes_io.name = filename
    image = Image.new("RGBA", size=(size_x, size_y), color=(final_r, final_g, final_b))
    if "jpg" in extension_lower or "jpeg" in extension_lower:
        image = image.convert("RGB")
    image.save(bytes_io)
    bytes_io.seek(0)

    return ImageFile(bytes_io, name=filename)
