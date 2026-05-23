from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import httpx

from ingestforge.core.config import FetchConfig, MediaConfig, SearchConfig
from ingestforge.core.errors import FetchError
from ingestforge.providers.fetch.safe_url import host_allowed, validate_public_url
from ingestforge.providers.media.image_hash import (
    content_hash_prefix,
    file_sha256,
    perceptual_hash_or_none,
)


@dataclass
class DownloadedMedia:
    source_url: str
    local_path: Path
    sha256: str
    content_hash_prefix: str
    perceptual_hash: str | None
    mime_type: str
    bytes_read: int
    width: int | None = None
    height: int | None = None


class MediaDownloader:
    def __init__(self, fetch: FetchConfig, media: MediaConfig, search: SearchConfig) -> None:
        self.fetch = fetch
        self.media = media
        self.search = search

    def _validate_media_url(self, url: str) -> str:
        safe = validate_public_url(
            url,
            deny_private_networks=self.fetch.deny_private_networks,
            require_https=self.fetch.require_https,
        )
        if not host_allowed(
            safe,
            self.search.allowed_domains,
            self.search.denied_domains,
            self.search.allow_subdomains,
        ):
            raise FetchError("media URL is not allowed by domain policy")
        return safe

    def _validate_image_file(self, path: Path) -> tuple[int | None, int | None]:
        try:
            from PIL import Image, ImageFile

            Image.MAX_IMAGE_PIXELS = 50_000_000
            ImageFile.LOAD_TRUNCATED_IMAGES = False
            with Image.open(path) as img:
                img.verify()
            with Image.open(path) as img:
                width, height = img.size
        except Exception as exc:
            raise FetchError("downloaded media is not a valid raster image") from exc
        if width < self.media.min_width or height < self.media.min_height:
            raise FetchError("image dimensions are below configured minimum")
        return width, height

    def download(self, url: str, out_dir: Path) -> DownloadedMedia:
        current = self._validate_media_url(url)
        out_dir.mkdir(parents=True, exist_ok=True)
        headers = {"User-Agent": self.fetch.user_agent, "Accept": "image/*,*/*;q=0.2"}
        with httpx.Client(timeout=self.fetch.timeout_seconds, follow_redirects=False) as client:
            for _ in range(self.fetch.max_redirects + 1):
                with client.stream("GET", current, headers=headers) as resp:
                    if resp.status_code in {301, 302, 303, 307, 308}:
                        loc = resp.headers.get("location")
                        if not loc:
                            raise FetchError("media redirect without Location header")
                        current = self._validate_media_url(urljoin(current, loc))
                        continue
                    if not (200 <= resp.status_code < 300):
                        raise FetchError(f"media HTTP status not successful: {resp.status_code}")
                    ctype = resp.headers.get("content-type", "")
                    lowered = ctype.lower()
                    if not lowered.startswith("image/") or "svg" in lowered:
                        raise FetchError(f"not an allowed raster image content type: {ctype}")
                    suffix = ".bin"
                    if "png" in lowered:
                        suffix = ".png"
                    elif "jpeg" in lowered or "jpg" in lowered:
                        suffix = ".jpg"
                    elif "webp" in lowered:
                        suffix = ".webp"
                    stable_name = hashlib.sha256(current.encode("utf-8")).hexdigest()[:20]
                    path = out_dir / f"asset_{stable_name}{suffix}"
                    total = 0
                    try:
                        with path.open("wb") as f:
                            for chunk in resp.iter_bytes():
                                total += len(chunk)
                                if total > self.media.max_image_bytes:
                                    raise FetchError("media response exceeded max_image_bytes")
                                f.write(chunk)
                        width, height = self._validate_image_file(path)
                    except Exception:
                        path.unlink(missing_ok=True)
                        raise
                    return DownloadedMedia(
                        source_url=current,
                        local_path=path,
                        sha256=file_sha256(path),
                        content_hash_prefix=content_hash_prefix(path),
                        perceptual_hash=perceptual_hash_or_none(path),
                        mime_type=ctype,
                        bytes_read=total,
                        width=width,
                        height=height,
                    )
            raise FetchError("too many media redirects")
