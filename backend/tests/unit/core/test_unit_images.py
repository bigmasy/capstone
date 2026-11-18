"""Re-encoding of an uploaded photograph."""

import io

import pytest
from PIL import Image

from app.core.images import normalise_photo
from app.domain.photo import PHOTO_SIDE_PX, PhotoRejectedError


def encoded(image: Image.Image, fmt: str, **save: object) -> bytes:
    out = io.BytesIO()
    image.save(out, format=fmt, **save)
    return out.getvalue()


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_each_accepted_format_becomes_a_square_jpeg(fmt: str):
    stored = Image.open(
        io.BytesIO(normalise_photo(encoded(Image.new("RGB", (800, 500), "navy"), fmt)))
    )

    assert stored.format == "JPEG"
    assert stored.mode == "RGB"
    assert stored.size == (PHOTO_SIDE_PX, PHOTO_SIDE_PX)


def test_transparency_becomes_white_not_black():
    transparent = Image.new("RGBA", (400, 400), (0, 0, 0, 0))

    stored = Image.open(io.BytesIO(normalise_photo(encoded(transparent, "PNG"))))

    assert all(channel > 240 for channel in stored.getpixel((200, 200)))


def test_a_rotated_picture_is_turned_upright_before_the_note_is_dropped():
    # Left half red, right half blue, marked as "rotate 180 degrees to view"
    image = Image.new("RGB", (400, 400), "red")
    image.paste("blue", (200, 0, 400, 400))
    exif = Image.Exif()
    exif[0x0112] = 3

    stored = Image.open(io.BytesIO(normalise_photo(encoded(image, "JPEG", exif=exif))))

    left = stored.getpixel((40, 160))
    assert left[2] > left[0]
    assert not stored.getexif()


@pytest.mark.parametrize(
    "content",
    [b"", b"not a picture", b"GIF89a" + b"\x00" * 64, b"<svg xmlns='http://www.w3.org/2000/svg'/>"],
)
def test_anything_else_is_refused(content: bytes):
    with pytest.raises(PhotoRejectedError):
        normalise_photo(content)


def test_a_gif_is_refused_even_though_the_library_could_read_it():
    with pytest.raises(PhotoRejectedError):
        normalise_photo(encoded(Image.new("P", (10, 10)), "GIF"))
