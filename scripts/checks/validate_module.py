#!/usr/bin/env python3
"""Check module metadata, entries, identities and literal asset references.

Reads: Module outlines, source files and course-local assets.
Writes: None. Does not compile TypeScript or verify rendered pages.
"""

from __future__ import annotations


import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from _common import modules_directory, emit_result, report_error, require_target_root
from module_assets import asset_roots, asset_directory, asset_relative
from course_metadata import module_errors, RULES
from course_identity import IdentityError, register_identity, is_canonical_uuid


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository",
        type=Path,
        default=None,
        help="repository root; default this checkout",
    )
    parser.add_argument(
        "--module",
        help="directory name, module slug or UUID; identity uniqueness is always checked globally",
    )
    return parser


def contained_file(base: Path, relative: str) -> bool:
    path = (base / relative).resolve()
    return path.is_relative_to(base.resolve()) and path.is_file()


def validate_modules(repository: Path, requested: str | None = None) -> list[str]:
    errors: list[str] = []
    try:
        asset_roots(repository)
    except (ValueError, OSError) as exc:
        return [str(exc)]
    seen: dict[str, Path] = {}
    loaded = []
    paths = sorted(modules_directory(repository).glob("*/outlines.json"))
    if not paths:
        return [f"No module outlines found under {repository / 'modules'}"]
    for path in paths:
        try:
            document = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(document, dict):
                raise ValueError("outline must be an object")
            if "moduleIdentity" not in document:
                raise IdentityError("Missing moduleIdentity")
            module_id = register_identity(document["moduleIdentity"], path, seen)
            loaded.append((path, document, module_id))
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"{path}: {exc}")
    selected = [
        item
        for item in loaded
        if requested is None
        or requested.lower()
        in {item[0].parent.name.lower(), str(item[1].get("id", "")).lower(), item[2],str(item[1].get("alias", "")).lower()}
    ]
    if requested and not selected:
        errors.append(f"Unknown module: {requested}")
    slugs: dict[str, Path] = {}
    for path, doc, module_id in loaded:
        slug = doc.get("id")
        if isinstance(slug, str) and slug:
            if slug in slugs:
                errors.append(f"Duplicate module slug {slug}: {slugs[slug]} and {path}")
            slugs[slug] = path
    for path, doc, module_id in selected:
        directory = path.parent
        label = directory.name
        errors.extend(module_errors(doc, label, complete=True,
                                    exists=lambda entry: contained_file(directory, entry)))
        local_assets = directory / "assets"
        for source in directory.rglob("*"):
            if "_scratchpad" in source.relative_to(directory).parts:
                continue
            if source.suffix not in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".css"}:
                continue
            try:
                text = source.read_text(encoding="utf-8-sig")
            except UnicodeError:
                errors.append(f"{source}: source file must be UTF-8")
                continue
            if re.search(r"\b(?:moduleAssetUrl|moduleJson)(?:<[^>]+>)?\(\s*(?:['\"][^'\"]+['\"]|moduleIdentity\.id)\s*,", text):
                errors.append(f'{source}: asset helpers require one course-local path; explicit module IDs are unsupported')
            if re.search(r'\bVITE_(?:LLM_SERVICE_URL|ASSET_BASE_URL)\b|\b__DL_TELEMETRY__\b', text):
                errors.append(f'{source}: retired runtime globals and environment variables are unsupported')
            if re.search(
                r"(?:from\s*|import\s*\(|fetch\s*\()\s*['\"][^'\"]*modules-legacy", text
            ):
                errors.append(f"{source}: legacy runtime dependency")
            for asset_id in re.findall(r"assetId=[\"\']([^\"\']+)[\"\']", text):
                if asset_id != module_id:
                    errors.append(
                        f"{source}: assetId must be {module_id}, got {asset_id}"
                    )
            for match in re.finditer(
                r"moduleAssetUrl\(\s*(?:(?:['\"]([^'\"]+)['\"]|moduleIdentity\.id)\s*,\s*)?['\"]([^'\"]+)['\"]\s*\)",
                text,
            ):
                asset_id, relative = match.groups()
                asset_id = asset_id or module_id
                if asset_id == module_id:
                    try:
                        asset_root = asset_directory(repository, module_id)
                        relative_path = asset_relative(repository, module_id, relative)
                    except (OSError, ValueError) as exc:
                        errors.append(f"{source}: missing or escaping asset: {relative}; {exc}")
                        continue
                if asset_id != module_id:
                    errors.append(
                        f"{source}: moduleAssetUrl UUID must be {module_id}, got {asset_id}"
                    )
                elif not contained_file(asset_root, relative_path):
                    # Atlas consumers use virtual image names; validate the referenced sheet instead.
                    mapped = False
                    if re.search(
                        r"atlasCropUrl\(\s*$",
                        text[max(0, match.start() - 40) : match.start()],
                    ):
                        index_path = asset_root / "image-atlases/index.json"
                        if index_path.is_file():
                            index = json.loads(
                                index_path.read_text(encoding="utf-8-sig")
                            )
                            region = (
                                index.get(relative) if isinstance(index, dict) else None
                            )
                            mapped = (
                                isinstance(region, dict)
                                and isinstance(region.get("sheet"), str)
                                and contained_file(asset_root, region["sheet"])
                            )
                    if not mapped:
                        errors.append(
                            f"{source}: missing or escaping asset: {relative}"
                        )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        errors = validate_modules(require_target_root(args.repository), args.module)
    except (OSError, UnicodeError, ValueError) as exc:
        return report_error(exc)
    emit_result(
        {
            "errors": errors,
            "attribution": "unverified: no before/after baseline supplied",
            "coverage": {"staticMetadata": True, "literalReferences": True, "rendering": False},
            "unverified": ["Dynamic resource expressions", "Rendered layout and interactions", "Whether an issue predates this change"],
            "profile": "shuku-course-preflight",
            "notes": "Outline-only drafts are validated as metadata and do not become buildable or published courses.",
            "limitations": "Static preflight only; use course.pack with the selected Shuku for platform admission/build, and inspect rendering separately.",
        },
        status="failed" if errors else "passed",
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
