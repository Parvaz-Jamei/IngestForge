from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from importlib import resources
from string import Formatter
from typing import Any

from ingestforge.core.errors import ConfigError

_PROMPT_VERSION_RE = re.compile(r"^(?P<name>[a-z][a-z0-9_]*?)\.v(?P<version>[1-9][0-9]*)$")
_SAFE_FIELD_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@dataclass(frozen=True)
class PromptTemplate:
    """Packaged prompt template resolved from a config-level prompt version."""

    version: str
    template_name: str
    resource_name: str
    text: str
    sha256: str

    def render(self, **values: Any) -> str:
        """Render simple `{name}` placeholders without adding a Jinja dependency.

        Prompt files use a `.j2` extension because they can later be moved to a
        full Jinja renderer, but the alpha core keeps runtime dependencies small.
        Only direct identifier placeholders are accepted so malformed prompt
        files fail clearly during tests and doctor checks.
        """
        formatter = Formatter()
        for _, field_name, _, _ in formatter.parse(self.text):
            if field_name is None:
                continue
            if not _SAFE_FIELD_RE.fullmatch(field_name):
                raise ConfigError(
                    f"unsupported prompt placeholder {field_name!r} in {self.version!r}"
                )
            if field_name not in values:
                raise ConfigError(
                    f"missing prompt placeholder value {field_name!r} for {self.version!r}"
                )
        return self.text.format_map(_StrictFormatMap(values))


class _StrictFormatMap(dict[str, Any]):
    def __missing__(self, key: str) -> Any:  # pragma: no cover - guarded before format_map
        raise ConfigError(f"missing prompt placeholder value {key!r}")


class PromptRegistry:
    """Resolve profile `ai.prompt_version` values to packaged prompt files."""

    def __init__(self, package: str = "ingestforge.prompts") -> None:
        self.package = package

    def list_versions(self) -> list[str]:
        prompt_root = resources.files(self.package)
        versions: list[str] = []
        for entry in prompt_root.iterdir():
            if entry.is_file() and entry.name.endswith(".j2") and not entry.name.startswith("_"):
                versions.append(f"{entry.name[:-3]}.v1")
        return sorted(versions)

    def resolve(self, prompt_version: str) -> PromptTemplate:
        value = str(prompt_version or "").strip()
        match = _PROMPT_VERSION_RE.fullmatch(value)
        if not match:
            raise ConfigError(
                "ai.prompt_version must use '<prompt_name>.v<number>' format, "
                f"got {prompt_version!r}"
            )
        if match.group("version") != "1":
            raise ConfigError(
                f"unknown prompt version {value!r}; available versions: "
                f"{', '.join(self.list_versions())}"
            )
        template_name = match.group("name")
        resource_name = f"{template_name}.j2"
        prompt_file = resources.files(self.package).joinpath(resource_name)
        if not prompt_file.is_file():
            raise ConfigError(
                f"unknown prompt version {value!r}; packaged prompt file {resource_name!r} "
                f"was not found"
            )
        text = prompt_file.read_text(encoding="utf-8").strip()
        if not text:
            raise ConfigError(f"prompt template {value!r} is empty")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return PromptTemplate(
            version=value,
            template_name=template_name,
            resource_name=resource_name,
            text=text,
            sha256=digest,
        )


prompt_registry = PromptRegistry()


def resolve_prompt(prompt_version: str) -> PromptTemplate:
    return prompt_registry.resolve(prompt_version)
