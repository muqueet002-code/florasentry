"""Image validation and preprocessing (Phase 2).

Validation is fail-fast and never trusts the client: the declared Content-Type and the
filename are both ignored in favour of decoding the bytes.

Quality heuristics (blur, exposure) are RECORDED, not fatal. They are a signal for the
reviewing expert, and they deliberately do not attempt to decide whether the subject is
a plant - no such detector exists here, and inventing one would be a false claim.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings
from app.core.errors import ValidationError

# Pillow refuses images above this pixel count as a decompression-bomb guard.
Image.MAX_IMAGE_PIXELS = settings.IMAGE_MAX_EDGE_PX * settings.IMAGE_MAX_EDGE_PX

MIME_BY_FORMAT = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


@dataclass
class ValidatedImage:
    data: bytes  # normalised, EXIF-stripped, re-encoded JPEG
    thumbnail: bytes
    mime_type: str
    width: int
    height: int
    quality_flags: dict[str, Any] = field(default_factory=dict)
    exif_captured_at: str | None = None
    exif_latitude: float | None = None
    exif_longitude: float | None = None


def _invalid(message: str, key: str, issue: str) -> ValidationError:
    return ValidationError(
        message,
        code="IMAGE_INVALID",
        message_key=key,
        details=[{"field": "image", "issue": issue}],
    )


def _extract_exif(image: Image.Image) -> tuple[str | None, float | None, float | None]:
    """Pull capture time and GPS out of EXIF before it is stripped.

    These are kept as data-integrity signals (an EXIF/GPS mismatch is worth showing an
    expert); the rest of the EXIF block is discarded as a privacy measure.
    """
    try:
        exif = image.getexif()
        if not exif:
            return None, None, None

        captured = exif.get(306)  # DateTime
        gps = exif.get_ifd(0x8825)
        if not gps:
            return (str(captured) if captured else None), None, None

        def _dms(value: Any, ref: Any) -> float | None:
            try:
                degrees, minutes, seconds = (float(x) for x in value)
            except (TypeError, ValueError):
                return None
            result = degrees + minutes / 60 + seconds / 3600
            return -result if str(ref).upper() in {"S", "W"} else result

        lat = _dms(gps.get(2), gps.get(1)) if gps.get(2) else None
        lon = _dms(gps.get(4), gps.get(3)) if gps.get(4) else None
        return (str(captured) if captured else None), lat, lon
    except Exception:
        # Malformed EXIF must never fail an otherwise-valid upload.
        return None, None, None


def _quality_flags(image: Image.Image) -> dict[str, Any]:
    """Cheap blur and exposure heuristics.

    Blur uses the variance of a 3x3 Laplacian on a downscaled greyscale copy - the
    standard approach, computed on a small image so the cost stays negligible.
    """
    flags: dict[str, Any] = {}
    try:
        grey = ImageOps.grayscale(image.copy())
        grey.thumbnail((256, 256))
        pixels = list(grey.getdata())
        width, height = grey.size
        if width < 3 or height < 3:
            return flags

        mean = sum(pixels) / len(pixels)
        flags["mean_luminance"] = round(mean, 2)
        flags["too_dark"] = mean < 40
        flags["too_bright"] = mean > 225

        laplacian: list[float] = []
        for y in range(1, height - 1):
            row = y * width
            for x in range(1, width - 1):
                centre = pixels[row + x]
                value = (
                    4 * centre
                    - pixels[row + x - 1]
                    - pixels[row + x + 1]
                    - pixels[row - width + x]
                    - pixels[row + width + x]
                )
                laplacian.append(float(value))

        if laplacian:
            lap_mean = sum(laplacian) / len(laplacian)
            variance = sum((v - lap_mean) ** 2 for v in laplacian) / len(laplacian)
            flags["blur_score"] = round(variance, 2)
            # Threshold chosen as a practical starting point, not a validated constant.
            flags["too_blurry"] = variance < 100.0
    except Exception:
        flags["quality_check_failed"] = True
    return flags


def validate_and_prepare(raw: bytes, declared_mime: str | None = None) -> ValidatedImage:
    """Validate raw upload bytes and produce normalised storage + thumbnail images."""
    if not raw:
        raise _invalid("The uploaded file is empty.", "errors.image_empty", "empty")

    if len(raw) > settings.IMAGE_MAX_BYTES:
        raise ValidationError(
            f"Image exceeds the {settings.IMAGE_MAX_BYTES // (1024 * 1024)} MB limit.",
            code="IMAGE_TOO_LARGE",
            message_key="errors.image_too_large",
            details=[{"field": "image", "issue": "too_large"}],
        )

    # Decode to determine the real format. The declared MIME is not trusted.
    try:
        probe = Image.open(io.BytesIO(raw))
        probe.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise _invalid(
            "The file is not a readable image.", "errors.image_invalid", "undecodable"
        ) from exc

    detected_format = (probe.format or "").upper()
    detected_mime = MIME_BY_FORMAT.get(detected_format)
    if detected_mime is None or detected_mime not in settings.allowed_image_mimes:
        raise ValidationError(
            f"Unsupported image type: {detected_format or 'unknown'}.",
            code="UNSUPPORTED_MEDIA_TYPE",
            message_key="errors.image_unsupported_type",
            details=[{"field": "image", "issue": "unsupported_type"}],
        )

    # verify() consumes the file object, so reopen for actual work.
    image = Image.open(io.BytesIO(raw))
    image = ImageOps.exif_transpose(image) or image
    width, height = image.size

    if min(width, height) < settings.IMAGE_MIN_EDGE_PX:
        raise _invalid(
            f"Image is smaller than {settings.IMAGE_MIN_EDGE_PX}px on its shortest edge.",
            "errors.image_too_small",
            "too_small",
        )
    if max(width, height) > settings.IMAGE_MAX_EDGE_PX:
        raise _invalid(
            f"Image exceeds {settings.IMAGE_MAX_EDGE_PX}px on its longest edge.",
            "errors.image_too_large",
            "dimensions_too_large",
        )

    exif_time, exif_lat, exif_lon = _extract_exif(image)
    rgb = image.convert("RGB")
    flags = _quality_flags(rgb)

    # Re-encoding through Pillow strips metadata and any embedded payload.
    stored = rgb.copy()
    stored.thumbnail(
        (settings.IMAGE_STORE_MAX_EDGE_PX, settings.IMAGE_STORE_MAX_EDGE_PX),
        Image.Resampling.LANCZOS,
    )
    stored_buffer = io.BytesIO()
    stored.save(stored_buffer, format="JPEG", quality=85, optimize=True)

    thumb = rgb.copy()
    thumb.thumbnail(
        (settings.IMAGE_THUMBNAIL_EDGE_PX, settings.IMAGE_THUMBNAIL_EDGE_PX),
        Image.Resampling.LANCZOS,
    )
    thumb_buffer = io.BytesIO()
    thumb.save(thumb_buffer, format="JPEG", quality=80, optimize=True)

    return ValidatedImage(
        data=stored_buffer.getvalue(),
        thumbnail=thumb_buffer.getvalue(),
        mime_type="image/jpeg",
        width=stored.width,
        height=stored.height,
        quality_flags=flags,
        exif_captured_at=exif_time,
        exif_latitude=exif_lat,
        exif_longitude=exif_lon,
    )


def to_model_input(
    image_bytes: bytes, size: tuple[int, int], mean: tuple[float, ...], std: tuple[float, ...]
) -> list[list[list[float]]]:
    """Resize and normalise into CHW float lists.

    Returned as plain Python so this module never imports torch - the runner converts
    to a tensor. Keeps preprocessing testable without the ML stack installed.
    """
    image = (
        Image.open(io.BytesIO(image_bytes)).convert("RGB").resize(size, Image.Resampling.BILINEAR)
    )
    pixels = list(image.getdata())
    width, height = image.size

    channels: list[list[list[float]]] = []
    for channel_index in range(3):
        plane: list[list[float]] = []
        for y in range(height):
            row_start = y * width
            plane.append(
                [
                    (pixels[row_start + x][channel_index] / 255.0 - mean[channel_index])
                    / std[channel_index]
                    for x in range(width)
                ]
            )
        channels.append(plane)
    return channels


def softmax(scores: list[float]) -> list[float]:
    """Numerically stable softmax, for runners whose model emits raw logits."""
    if not scores:
        return []
    peak = max(scores)
    exponentials = [math.exp(s - peak) for s in scores]
    total = sum(exponentials)
    return [e / total for e in exponentials] if total else [0.0] * len(scores)
