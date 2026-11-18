"""Rules of the profile photograph: what may be uploaded and what is stored."""

from app.domain.errors import DomainError

# Largest upload the API reads; the client resizes a picture before sending, so a real one is
# far smaller.
PHOTO_MAX_UPLOAD_BYTES = 2 * 1024 * 1024
# Side of the stored square picture, in pixels.
PHOTO_SIDE_PX = 320
# The only stored format; every upload is decoded and encoded again into it.
PHOTO_MEDIA_TYPE = "image/jpeg"
PHOTO_ACCEPTED_MEDIA_TYPES = ("image/jpeg", "image/png", "image/webp")

PHOTO_INVALID_MESSAGE = "The file is not a JPEG, PNG or WebP picture"
PHOTO_TOO_LARGE_MESSAGE = "The picture is larger than 2 MB"
PHOTO_INVALID_CODE = "photo_invalid"
PHOTO_TOO_LARGE_CODE = "photo_too_large"


class PhotoRejectedError(DomainError):
    """An uploaded file cannot be used as a profile photograph (HTTP 422).

    The message is fixed and repeats nothing of the upload.

    :param code: Machine-readable reason, ``photo_invalid`` or ``photo_too_large``.
    """

    def __init__(self, code: str = PHOTO_INVALID_CODE) -> None:
        """Keep the code and use the fixed message that belongs to it."""
        self.code = code
        super().__init__(
            PHOTO_TOO_LARGE_MESSAGE if code == PHOTO_TOO_LARGE_CODE else PHOTO_INVALID_MESSAGE
        )
