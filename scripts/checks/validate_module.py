#!/usr/bin/env python3
"""Check module metadata, entries, identities and literal asset references.

Reads: Module outlines, source files and asset indexes.
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
from module_assets import asset_directory, asset_relative
from course_identity import IdentityError, register_identity


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
    parser.add_argument("--strict-authoring",action="store_true",help="Apply legacy CIDL authoring field restrictions; default preserves existing IDL metadata")
    return parser


def contained_file(base: Path, relative: str) -> bool:
    path = (base / relative).resolve()
    return path.is_relative_to(base.resolve()) and path.is_file()


def validate_modules(repository: Path, requested: str | None = None, *, strict_authoring=False) -> list[str]:
    errors: list[str] = []
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
        for key in (("id", "title") if "id" in doc else ("title",)):
            if not isinstance(doc.get(key), str) or not doc[key].strip():
                errors.append(f"{label}: missing nonempty {key}")
        if doc.get("path") != "/modules/" + directory.name.lower():
            errors.append(f"{label}: path must match /modules/{directory.name.lower()}")
        entries = [doc.get("entry")] if doc.get("entry") else []
        ppt = doc.get("ppt")
        if ppt is not None:
            if not isinstance(ppt, dict):
                errors.append(f"{label}: ppt must be an object")
            else:
                if ppt.get("entry"): entries.append(ppt["entry"])
        for entry in entries:
            if (
                not isinstance(entry, str)
                or not entry.endswith(".tsx")
                or not contained_file(directory, entry)
            ):
                errors.append(
                    f"{label}: entry must name an existing module TSX file: {entry!r}"
                )
        pages = doc.get("pages")
        if not isinstance(pages, list) or (not pages and entries):
            errors.append(f"{label}: pages must be a nonempty array")
        else:
            page_ids = set()
            for number, page in enumerate(pages, 1):
                if not isinstance(page, dict):
                    errors.append(f"{label}: page {number} must be an object")
                    continue
                obsolete = sorted(set(page) & {"interaction", "next", "section", "implementationStatus"})
                if obsolete and strict_authoring:
                    errors.append(f"{label}: page {number} contains obsolete outline fields: {', '.join(obsolete)}; keep design and progress notes in _scratchpad/")
                page_id = page.get("id")
                if not isinstance(page_id, str) or not page_id.strip():
                    errors.append(f"{label}: page {number} has no valid id")
                elif page_id in page_ids:
                    errors.append(f"{label}: duplicate page id {page_id}")
                else:
                    page_ids.add(page_id)
                if not isinstance(page.get("title"), str) or not page["title"].strip():
                    errors.append(f"{label}: page {number} has no title")
                if not isinstance(page.get("snippet"), str) or not page["snippet"].strip():
                    errors.append(f"{label}: page {number} has no snippet")
        local_assets = directory / "assets"
        for source in directory.rglob("*"):
            if "_scratchpad" in source.relative_to(directory).parts:
                continue
            if source.suffix not in {".ts", ".tsx", ".css"}:
                continue
            try:
                text = source.read_text(encoding="utf-8-sig")
            except UnicodeError:
                errors.append(f"{source}: source file must be UTF-8")
                continue
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
        errors = validate_modules(require_target_root(args.repository), args.module,strict_authoring=args.strict_authoring)
    except (OSError, UnicodeError, ValueError) as exc:
        return report_error(exc)
    emit_result(
        {
            "errors": errors,
            "attribution": "unverified: no before/after baseline supplied",
            "coverage": {"staticMetadata": True, "literalReferences": True, "rendering": False},
            "unverified": ["Dynamic resource expressions", "Rendered layout and interactions", "Whether an issue predates this change"],
            "profile": "strict-cidl-authoring" if args.strict_authoring else "compatible-idl",
            "notes": "Outline-only drafts are validated as metadata and do not become buildable or published courses.",
            "limitations": "Dynamic resource expressions and rendering require separate checks.",
        },
        status="failed" if errors else "passed",
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
