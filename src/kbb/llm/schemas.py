"""Pydantic schemas for structured LLM output validation.

These replace the raw JSON schema dicts previously defined in prompts.py.
Each provider's native structured output API enforces these schemas at
generation time, so the LLM is guaranteed to return conformant JSON.
Pydantic validation provides a second layer of defense on the application side.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from kbb.models import QuestionTopic


class ProfileSchema(BaseModel):
    """Structured profile data extracted from a user's freeform description."""

    name: str = ""
    education: list[str] = Field(default_factory=list)
    work_experience: list[str] = Field(default_factory=list)
    life_experience: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)


class QuestionSchema(BaseModel):
    """A generated question targeting a specific knowledge area."""

    text: str
    topic: QuestionTopic = QuestionTopic.GENERAL
    rationale: str = ""


def _make_strict(schema: dict) -> dict:
    """Post-process a JSON schema for strict structured output compatibility.

    OpenAI and Anthropic's structured output APIs require:
    - ``additionalProperties: false`` on every object
    - All fields in ``required`` (even those with defaults)
    - No ``$ref`` — all definitions must be inlined

    Pydantic's ``model_json_schema()`` omits optional fields from ``required``
    and uses ``$defs``/``$ref`` for enums, so we fix both here.
    """
    # Inline any $defs first
    defs = schema.pop("$defs", {})
    _inline_refs(schema, defs)

    # Ensure all properties are required for strict mode
    if "properties" in schema:
        schema["required"] = list(schema["properties"].keys())
        for prop in schema["properties"].values():
            # OpenAI strict mode doesn't allow 'default' in properties
            prop.pop("default", None)
            # Also remove Pydantic metadata that isn't part of JSON Schema
            prop.pop("title", None)
            if prop.get("type") == "object":
                _make_strict(prop)
            elif "items" in prop and prop["items"].get("type") == "object":
                _make_strict(prop["items"])

    schema["additionalProperties"] = False
    return schema


def _inline_refs(obj: dict, defs: dict) -> None:
    """Recursively replace $ref pointers with their definitions."""
    if not isinstance(obj, dict):
        return
    for key, value in list(obj.items()):
        if isinstance(value, dict):
            if "$ref" in value:
                # $ref looks like "#/$defs/QuestionTopic"
                ref_name = value["$ref"].split("/")[-1]
                if ref_name in defs:
                    obj[key] = {**defs[ref_name]}
                    # Recurse in case the inlined def has nested refs
                    _inline_refs(obj[key], defs)
            else:
                _inline_refs(value, defs)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    _inline_refs(item, defs)


def strict_json_schema(model: type[BaseModel]) -> dict:
    """Generate a strict-compatible JSON schema from a Pydantic model.

    Used by LLM providers that enforce structured output at generation time.
    Produces a schema with all properties required, no ``$ref`` pointers,
    and ``additionalProperties: false`` on every object.
    """
    schema = model.model_json_schema()
    return _make_strict(schema)


# Pre-computed strict schemas for use by providers
PROFILE_JSON_SCHEMA = strict_json_schema(ProfileSchema)
QUESTION_JSON_SCHEMA = strict_json_schema(QuestionSchema)
