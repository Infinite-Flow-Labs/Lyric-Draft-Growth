#!/usr/bin/env python3
"""Validate framework specs and runtime contract schemas."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, validate


BASE_DIR = Path(__file__).resolve().parent

SCHEMA_FILES = [
    "FRAMEWORK_SPEC_SCHEMA.json",
    "SOURCE_ITEM_SCHEMA.json",
    "FRAMEWORK_MATCH_SCHEMA.json",
    "REWRITE_CONTEXT_SCHEMA.json",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def check_schema_file(path: Path) -> None:
    Draft202012Validator.check_schema(load_json(path))


def validate_framework_specs() -> list[str]:
    schema = load_json(BASE_DIR / "FRAMEWORK_SPEC_SCHEMA.json")
    errors: list[str] = []

    for spec_path in sorted(BASE_DIR.glob("*/FRAMEWORK_SPEC.json")):
        spec = load_json(spec_path)
        try:
            validate(spec, schema)
        except Exception as exc:  # pragma: no cover - best-effort error surfacing
            errors.append(f"{spec_path.parent.name}: schema validation failed: {exc}")
            continue

        submodes = {item["submode_id"] for item in spec["structure"]["submodes"]}
        style_profiles = {item["style_profile_id"] for item in spec["style"]["submode_profiles"]}
        style_submodes = {item["submode_id"] for item in spec["style"]["submode_profiles"]}
        sample_submodes = {item["submode_id"] for item in spec["samples"]["sample_refs"]}
        linked_style_profiles = {item["style_profile_id"] for item in spec["structure"]["submodes"]}

        if spec["samples"]["sample_count"] != len(spec["samples"]["sample_refs"]):
            errors.append(
                f"{spec_path.parent.name}: sample_count={spec['samples']['sample_count']} "
                f"but sample_refs={len(spec['samples']['sample_refs'])}"
            )

        missing_styles = linked_style_profiles - style_profiles
        if missing_styles:
            errors.append(f"{spec_path.parent.name}: missing style profiles {sorted(missing_styles)}")

        unknown_style_submodes = style_submodes - submodes
        if unknown_style_submodes:
            errors.append(
                f"{spec_path.parent.name}: style profiles reference unknown submodes {sorted(unknown_style_submodes)}"
            )

        unknown_sample_submodes = sample_submodes - submodes
        if unknown_sample_submodes:
            errors.append(
                f"{spec_path.parent.name}: sample refs reference unknown submodes {sorted(unknown_sample_submodes)}"
            )

    return errors


def main() -> int:
    errors: list[str] = []

    for schema_name in SCHEMA_FILES:
        schema_path = BASE_DIR / schema_name
        try:
            check_schema_file(schema_path)
            print(f"schema_ok {schema_name}")
        except Exception as exc:  # pragma: no cover - best-effort error surfacing
            errors.append(f"{schema_name}: invalid schema: {exc}")

    errors.extend(validate_framework_specs())

    if errors:
        print("\nvalidation_errors:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("\nall_framework_contracts_valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
