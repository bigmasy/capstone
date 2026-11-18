"""Decoding and re-encoding of an uploaded profile photograph.

Nothing of the original file is stored. The picture is decoded, turned upright, cut to a centred
square, scaled down and written again as a JPEG, so metadata of the camera (including the place
where the picture was taken) and anything hidden after the image data never reach storage.
"""

import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from app.domain.photo import PHOTO_SIDE_PX, PhotoRejectedError

# A picture with more pixels than this is refused before it is decoded in full (a small file can
# describe an enormous image).
_MAX_PIXELS = 40_000_000
_ACCEPTED_FORMATS = ("JPEG", "PNG", "WEBP")
_JPEG_QUALITY = 84
_BACKGROUND = (255, 255, 255)


def normalise_photo(content: bytes) -> bytes:
    """Turn an uploaded picture into the stored form: a square JPEG without metadata.

    Blocking: call it from a worker thread.

    :param content: The uploaded file.
    :raises PhotoRejectedError: If the bytes are not a JPEG, PNG or WebP picture, or the picture
        is unreasonably large.
    :return: JPEG bytes of a square picture, ``PHOTO_SIDE_PX`` pixels on a side.
    """
    try:
        with warnings.catch_warnings():
            # Pillow warns about a suspiciously large picture before it raises; both mean no.
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content), formats=_ACCEPTED_FORMATS) as source:
                if source.width * source.height > _MAX_PIXELS:
                    raise PhotoRejectedError
                source.load()
                upright = ImageOps.exif_transpose(source)
                picture = upright.convert("RGBA")
    except PhotoRejectedError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Warning) as error:
        raise PhotoRejectedError from error
    # Transparent areas become white instead of black
    flat = Image.new("RGB", picture.size, _BACKGROUND)
    flat.paste(picture, mask=picture.getchannel("A"))
    square = ImageOps.fit(flat, (PHOTO_SIDE_PX, PHOTO_SIDE_PX), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    # A new file is written from the pixels alone: no EXIF block, no colour profile, no comments
    square.save(out, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
    return out.getvalue()
