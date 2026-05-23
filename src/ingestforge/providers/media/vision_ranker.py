from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VisionRank:
    is_relevant: bool
    image_type: str = "unknown"
    contains_useful_text: bool = False
    quality_score: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "is_relevant": self.is_relevant,
            "image_type": self.image_type,
            "contains_useful_text": self.contains_useful_text,
            "quality_score": self.quality_score,
            "risk_flags": self.risk_flags,
            "reason": self.reason,
        }


class LocalVisionRanker:
    name = "local_heuristic"

    def rank(self, *, filename: str = "", alt_text: str = "", nearby_text: str = "") -> dict:
        text = " ".join([filename, alt_text, nearby_text]).lower()
        bad = any(k in text for k in ["logo", "avatar", "icon", "banner", "pixel"])
        score = 0.2 if bad else 0.65
        return VisionRank(
            is_relevant=not bad,
            image_type="unknown",
            contains_useful_text=False,
            quality_score=score,
            risk_flags=["local_heuristic_only"],
            reason="local heuristic",
        ).as_dict()


def vision_ranker(name: str):
    if name in {"local", "local_heuristic"}:
        return LocalVisionRanker()
    raise RuntimeError(
        f"AI vision provider '{name}' is experimental in this alpha; use local_heuristic"
    )
