from __future__ import annotations

import copy
import json
from typing import Any

from pydantic import BaseModel, ValidationError

from ingestforge.core.errors import ValidationFailure


def parse_strict_json(text: str) -> dict[str, Any]:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValidationFailure("provider output must be a JSON object")
    return value


def extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValidationFailure("no JSON object found")
    return parse_strict_json(text[start : end + 1])


def validate_model_payload(model: type[BaseModel], payload: dict[str, Any]) -> BaseModel:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise ValidationFailure(str(exc)) from exc


def strict_openai_schema(schema: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(schema or {"type": "object", "properties": {}})
    forbidden = {"default", "examples", "title"}

    def walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            for key in list(obj.keys()):
                if key in forbidden:
                    obj.pop(key, None)
            if obj.get("type") == "object" or "properties" in obj:
                obj.setdefault("type", "object")
                obj["additionalProperties"] = False
                props = obj.get("properties", {})
                if not isinstance(props, dict):
                    raise ValidationFailure("object schema properties must be a mapping")
                obj["properties"] = {str(k): walk(v) for k, v in props.items()}
            if "items" in obj:
                obj["items"] = walk(obj["items"])
            if "$ref" in obj or "$defs" in obj:
                raise ValidationFailure("$ref/$defs must be resolved before OpenAI strict schema")
            return obj
        if isinstance(obj, list):
            return [walk(v) for v in obj]
        return obj

    return walk(out)


def _resolve_local_refs(schema: dict[str, Any]) -> dict[str, Any]:
    root = copy.deepcopy(schema)
    defs = root.get("$defs", {}) or root.get("definitions", {}) or {}

    def walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            ref = obj.get("$ref")
            if isinstance(ref, str):
                prefix = "#/$defs/"
                if not ref.startswith(prefix):
                    raise ValidationFailure(f"unsupported external schema ref: {ref}")
                name = ref[len(prefix) :]
                if name not in defs:
                    raise ValidationFailure(f"unresolved schema ref: {ref}")
                replacement = copy.deepcopy(defs[name])
                override = {k: v for k, v in obj.items() if k != "$ref"}
                replacement.update(override)
                return walk(replacement)
            return {k: walk(v) for k, v in obj.items() if k not in {"$defs", "definitions"}}
        if isinstance(obj, list):
            return [walk(v) for v in obj]
        return obj

    resolved = walk(root)
    if "$ref" in json.dumps(resolved):
        raise ValidationFailure("unresolved $ref remains after schema sanitation")
    return resolved


def sanitize_schema_for_gemini(schema: dict[str, Any]) -> dict[str, Any]:
    out = _resolve_local_refs(schema or {"type": "object", "properties": {}})
    forbidden = {"default", "examples", "title", "additionalProperties"}

    def clean(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items() if k not in forbidden}
        if isinstance(obj, list):
            return [clean(v) for v in obj]
        return obj

    return clean(out)


def sanitize_json_schema_for_provider(schema: dict[str, Any], provider: str) -> dict[str, Any]:
    if provider == "openai":
        return strict_openai_schema(schema)
    if provider == "gemini":
        return sanitize_schema_for_gemini(schema)
    forbidden = {"default", "examples", "title"}

    def clean(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items() if k not in forbidden}
        if isinstance(obj, list):
            return [clean(v) for v in obj]
        return obj

    return clean(copy.deepcopy(schema))
