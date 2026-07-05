#!/usr/bin/env python3
"""Reject literal API keys in a Hermes YAML configuration file."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml


ENV_REFERENCE = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}")


def is_api_key_field(key: object) -> bool:
    return str(key).strip().lower().replace("-", "_") == "api_key"


def is_allowed_value(value: object) -> bool:
    return value is None or value == "" or (
        isinstance(value, str) and ENV_REFERENCE.fullmatch(value) is not None
    )


def api_key_violations(value: Any, path: str = "") -> Iterator[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if is_api_key_field(key) and not is_allowed_value(child):
                yield child_path
            yield from api_key_violations(child, child_path)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            yield from api_key_violations(child, f"{path}[{index}]")


def validate(path: Path) -> list[str]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RuntimeError(f"configuration file not found: {path}") from error
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise RuntimeError(f"could not parse {path}: {error}") from error
    return list(api_key_violations(document))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=Path("config.yaml"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        violations = validate(args.path)
    except RuntimeError as error:
        print(f"API-key validation failed: {error}", file=sys.stderr)
        return 2
    if violations:
        print("Literal API-key values found; refusing commit:", file=sys.stderr)
        for path in violations:
            print(f"- {path}", file=sys.stderr)
        return 1
    print(f"API-key validation passed: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
