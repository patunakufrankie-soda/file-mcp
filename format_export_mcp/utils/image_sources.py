from __future__ import annotations

import base64
import binascii
import mimetypes
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


@dataclass(slots=True)
class ImageAsset:
    data: bytes
    name: str

    def open_bytes(self) -> BytesIO:
        return BytesIO(self.data)


def load_image_assets(images: list[str]) -> list[ImageAsset]:
    assets: list[ImageAsset] = []
    for index, image_ref in enumerate(images, start=1):
        stripped_ref = image_ref.strip()
        if not stripped_ref:
            raise ValueError("Image entries must not be empty")
        if stripped_ref.startswith("data:image/"):
            assets.append(_load_data_url(stripped_ref, index))
            continue
        if _looks_like_remote_image_ref(stripped_ref):
            assets.append(_load_remote_file(stripped_ref, index))
            continue
        assets.append(_load_local_file(stripped_ref))
    return assets


def _load_data_url(image_ref: str, index: int) -> ImageAsset:
    header, encoded = image_ref.split(",", 1)
    if ";base64" not in header:
        raise ValueError("Only base64 data URLs are supported for images")

    mime_type = header[5:].split(";", 1)[0]
    extension = mime_type.split("/", 1)[1] if "/" in mime_type else "bin"
    try:
        data = base64.b64decode(encoded, validate=True)
    except binascii.Error as exc:
        raise ValueError("Invalid base64 image data") from exc

    return ImageAsset(data=data, name=f"image-{index}.{extension}")


def _load_local_file(image_ref: str) -> ImageAsset:
    image_path = Path(image_ref).expanduser()
    try:
        resolved_path = image_path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"Image file not found: {image_ref}") from exc

    return ImageAsset(data=resolved_path.read_bytes(), name=resolved_path.name)


def _looks_like_remote_image_ref(image_ref: str) -> bool:
    parsed = urlparse(image_ref)
    if parsed.scheme in {"http", "https"}:
        return True
    return image_ref.startswith("/api/") or image_ref.startswith("api/")


def _get_image_source_base_url() -> str:
    return os.getenv("FORMAT_EXPORT_IMAGE_SOURCE_BASE_URL", "").strip().rstrip("/")


def _get_image_fetch_timeout_seconds() -> float:
    raw_value = os.getenv("FORMAT_EXPORT_IMAGE_FETCH_TIMEOUT_SECONDS", "10")
    try:
        timeout = float(raw_value)
    except ValueError as exc:
        raise ValueError("FORMAT_EXPORT_IMAGE_FETCH_TIMEOUT_SECONDS must be a number") from exc
    return max(0.1, timeout)


def _resolve_remote_image_url(image_ref: str) -> str:
    parsed = urlparse(image_ref)
    if parsed.scheme in {"http", "https"}:
        return image_ref

    base_url = _get_image_source_base_url()
    if not base_url:
        raise ValueError(
            "Relative image URLs require FORMAT_EXPORT_IMAGE_SOURCE_BASE_URL to be set"
        )
    return urljoin(f"{base_url}/", image_ref.lstrip("/"))


def _guess_extension(content_type: str | None, fallback_name: str) -> str:
    if content_type:
        guessed_extension = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
        if guessed_extension:
            return guessed_extension.lstrip(".")

    suffix = Path(urlparse(fallback_name).path).suffix.lstrip(".")
    return suffix or "bin"


def _load_remote_file(image_ref: str, index: int) -> ImageAsset:
    resolved_url = _resolve_remote_image_url(image_ref)
    request = Request(resolved_url, headers={"User-Agent": "Format-Export-MCP/1.0"})

    try:
        with urlopen(request, timeout=_get_image_fetch_timeout_seconds()) as response:
            data = response.read()
            content_type = response.headers.get("Content-Type")
    except HTTPError as exc:
        raise ValueError(f"Failed to fetch image: {resolved_url} (HTTP {exc.code})") from exc
    except URLError as exc:
        raise ValueError(f"Failed to fetch image: {resolved_url}") from exc

    extension = _guess_extension(content_type, resolved_url)
    file_name = Path(urlparse(resolved_url).path).name or f"image-{index}.{extension}"
    if "." not in file_name:
        file_name = f"{file_name}.{extension}"

    return ImageAsset(data=data, name=file_name)
