from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ingestforge.core.errors import OptionalDependencyError


@dataclass
class OCRResult:
    text: str = ""
    confidence: float | None = None
    engine: str = "noop"
    status: str = "disabled"
    error: str | None = None


class NoopOCRProvider:
    name = "noop"

    def extract_text(self, image_path: Path, languages: list[str]) -> OCRResult:
        return OCRResult(status="disabled")


class TesseractOCRProvider:
    name = "tesseract"

    def extract_text(self, image_path: Path, languages: list[str]) -> OCRResult:
        try:
            import pytesseract
            from PIL import Image
        except Exception as exc:
            raise OptionalDependencyError(
                "OCR requested but pytesseract/Pillow is unavailable"
            ) from exc
        text = pytesseract.image_to_string(Image.open(image_path), lang="+".join(languages))
        return OCRResult(
            text=text,
            confidence=None,
            engine="tesseract",
            status="ok" if text.strip() else "empty",
        )


def ocr_provider(name: str):
    if name == "noop":
        return NoopOCRProvider()
    if name == "tesseract":
        return TesseractOCRProvider()
    raise OptionalDependencyError(f"unknown OCR provider: {name}")
