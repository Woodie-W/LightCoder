#!/usr/bin/env python3
"""Validate and reproducibly package the compact LightCoder skill set."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE = ROOT / "skills"
DEFAULT_ZIP = ROOT / "coding-agent-skills.zip"
VALID_ROLES = {"core", "playbook", "execution"}
FORBIDDEN_TEXT = {
    "swe-marathon",
    "swebench",
    "swe-bench",
    "rust-java-lsp",
    "vliw-kernel-optimization",
    "ruby-rust-port",
    "find-network-alignments",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_ZIP)
    parser.add_argument("--build-zip", action="store_true")
    return parser.parse_args()


def load_manifest(package: Path) -> dict[str, object]:
    value = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("manifest.json must contain an object")
    return value


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return {}
    block = text[4 : text.find("\n---\n", 4)]
    result: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip().strip("\"'")
    return result


def validate(package: Path, manifest: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != 1:
        errors.append("manifest schema_version must be 1")
    entries = manifest.get("skills")
    if not isinstance(entries, list):
        return errors + ["manifest skills must be a list"]
    names: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("manifest skill entries must be objects")
            continue
        name = str(entry.get("name", ""))
        role = str(entry.get("role", ""))
        names.append(name)
        if role not in VALID_ROLES:
            errors.append(f"{name}: invalid role {role}")
        path = package / name / "SKILL.md"
        if not path.is_file():
            errors.append(f"{name}: missing SKILL.md")
            continue
        text = path.read_text(encoding="utf-8")
        metadata = _frontmatter(text)
        if metadata.get("name") != name:
            errors.append(f"{name}: frontmatter name mismatch")
        if not metadata.get("description"):
            errors.append(f"{name}: description is required")
        if not text.isascii():
            errors.append(f"{name}: agent-facing content must be ASCII English")
        lowered = text.lower()
        for forbidden in FORBIDDEN_TEXT:
            if forbidden in lowered:
                errors.append(
                    f"{name}: benchmark-specific text is forbidden: {forbidden}"
                )
    if len(names) != len(set(names)):
        errors.append("manifest skill names must be unique")
    directories = {path.name for path in package.iterdir() if path.is_dir()}
    if directories != set(names):
        errors.append(
            f"skill directories differ from manifest: missing={sorted(set(names) - directories)}, "
            f"extra={sorted(directories - set(names))}"
        )
    return errors


def build_zip(package: Path, output: Path) -> None:
    paths = [package / "manifest.json"]
    paths.extend(sorted(package.glob("*/SKILL.md")))
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in paths:
            relative = Path("skills") / path.relative_to(package)
            info = zipfile.ZipInfo(
                str(relative).replace("\\", "/"), (2026, 1, 1, 0, 0, 0)
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.package)
    errors = validate(args.package, manifest)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"validated {len(manifest['skills'])} skills")  # type: ignore[arg-type]
    if args.build_zip:
        build_zip(args.package, args.output)
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
