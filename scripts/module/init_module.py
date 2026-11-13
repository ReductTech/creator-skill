#!/usr/bin/env python3
"""Ensure the canonical module outline exists.

Reads: modules/<directory>/outlines.json (existence only).
Writes: Only creates a missing outline; leaves every existing file untouched.
"""

from pathlib import Path
import argparse
import json
import os
import re
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from _common import modules_directory, read_modules, emit_result, report_error, require_target_root
from module.module_identity import new_identity, register_identity


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory", help="module directory name; generate a new UUID when omitted"
    )
    parser.add_argument(
        "--title",
        help="initial title for a new outline; ignored when the file already exists",
    )
    parser.add_argument(
        "--repository",
        type=Path,
        default=None,
        help="must match targetRoot in the Skill's target-root.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report whether an outline would be created without writing files",
    )
    return parser


def ensure_outline(
    root: Path, directory: str, title: str | None = None, dry_run: bool = False
) -> dict:
    """Create the canonical outline once, without reading or rewriting an existing one."""
    root = Path(root).resolve()
    directory = directory or str(uuid.uuid4())
    if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", directory):
        raise ValueError("Invalid module directory name; use a canonical UUID v4")
    modules = modules_directory(root)
    target = modules / directory
    if (
        not modules.is_relative_to(root)
        or target.is_symlink()
        or target.resolve().parent != modules
    ):
        raise ValueError("Module directory must stay inside repository modules/")
    outline = target / "outlines.json"
    if outline.is_symlink():
        raise ValueError("Outline must not be a symbolic link")
    result = {"module": directory, "path": str(outline), "dry_run": dry_run}
    if outline.exists():
        if not outline.is_file():
            raise ValueError("outlines.json must be a file")
        return {**result, "status": "unchanged"}
    if target.exists() and not target.is_dir():
        raise ValueError("Module directory must be a directory")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        raise ValueError("Title must be a nonempty string")
    if dry_run:
        return {**result, "status": "would-create"}
    document = {
        "id": directory.lower(),
        "title": title if title is not None else directory,
        "description": "",
        "path": "/modules/" + directory.lower(),
        "pages": [],
        "moduleIdentity": ({"version": 1, "id": directory} if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", directory) else new_identity({})),
    }
    content = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    target.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=target,
            prefix=".outlines-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            # Linking a completed file is atomic and fails if any destination already exists.
            os.link(temporary, outline)
        except FileExistsError:
            if not outline.is_file() or outline.is_symlink():
                raise ValueError("outlines.json must be a regular file")
            return {**result, "status": "unchanged"}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {**result, "status": "created"}


def plan_module(root, directory, outline):
    """Legacy scaffold helper; not used by the module.init command."""
    directory = directory or str(uuid.uuid4())
    if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", directory):
        raise ValueError("Invalid module directory name; use a canonical UUID v4")
    target = modules_directory(root) / directory
    if target.exists():
        raise ValueError(f"Module already exists: {target}")
    doc = json.loads(json.dumps(outline))
    if (
        not isinstance(doc, dict)
        or not isinstance(doc.get("title"), str)
        or not doc["title"].strip()
    ):
        raise ValueError("Outline needs a title")
    if "moduleIdentity" in doc:
        raise ValueError(
            "Remove copied moduleIdentity before initializing a new course"
        )
    pages = doc.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("Outline needs a nonempty pages array")
    ids = set()
    for page in pages:
        if (
            not isinstance(page, dict)
            or not isinstance(page.get("id"), str)
            or not page["id"].strip()
            or not isinstance(page.get("title"), str)
            or not page["title"].strip()
        ):
            raise ValueError("Every page needs nonempty id and title")
        if page["id"] in ids:
            raise ValueError(f"Duplicate page ID: {page['id']}")
        ids.add(page["id"])
    seen = {}
    for existing, metadata in read_modules(root):
        register_identity(
            metadata.get("moduleIdentity"), existing / "outlines.json", seen
        )
    doc.update(
        {
            "id": directory,
            "path": "/modules/" + directory.lower(),
            "entry": "GuidePage.tsx",
            "ppt": {"entry": "CoursePpt.tsx", "path": "/scenedeck/", "player": False},
            "moduleIdentity": ({"version": 1, "id": directory} if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", directory) else new_identity({})),
        }
    )
    if any(
        metadata.get("id", existing.name) == doc["id"]
        for existing, metadata in read_modules(root)
    ):
        raise ValueError("Duplicate module slug")
    if not isinstance(doc["id"], str) or not doc["id"].strip():
        raise ValueError("Invalid module slug")
    if (target / "assets").exists():
        raise ValueError("Generated UUID asset directory already exists")
    guide = """import { useRef, type ReactNode } from 'react';
import { Button, LessonFlow, ModuleShell } from '@shuku/course-style/react';
import { useSceneScale } from '@shuku/course-style/react/presentation/canvas';
import { scenes } from './course';
import outline from './outlines.json';
import '@shuku/course-style/react/styles.css';
import '@shuku/course-style/react/presentation.css';
function Canvas({children}:{children:ReactNode}) {
  const ref=useRef<HTMLDivElement>(null); const scale=useSceneScale(ref);
  return <div ref={ref} style={{width:'100%',aspectRatio:'16 / 9',position:'relative'}}><div className="course-page-surface course-shell" style={{width:1600,height:900,transform:`scale(${scale})`,transformOrigin:'top left'}}>{children}</div></div>;
}
const steps=scenes.map((scene,index)=>({id:scene.id,completesLesson:index===scenes.length-1,render:(context:Parameters<typeof scene.render>[0])=><><Canvas>{scene.render(context)}</Canvas><Button onClick={context.complete}>继续</Button></>}));
export function GuidePage(){return <ModuleShell title={outline.title} subtitle={outline.description || ''}><LessonFlow steps={steps} persistenceKey={outline.moduleIdentity.id+':guide'}/></ModuleShell>;}
"""
    course = """import { ContentBlock } from '@shuku/course-style/react';
import type { SceneDefinition, SpeakerNote } from '@shuku/course-style/react/presentation';
import outline from './outlines.json';
// Engineering scaffold only. Implement each page after its design is confirmed.
export const scenes:SceneDefinition[]=outline.pages.map(page=>({id:page.id,title:page.title,section:'',render:()=> <ContentBlock title={page.title}/> }));
export function getPptNotes(id:string):SpeakerNote[]{const page=outline.pages.find(page=>page.id===id);return page?.snippet?[{text:page.snippet,selectors:[]}]:[];}
"""
    # Ensure optional source fields are present so generated JSON inference stays valid.
    doc.setdefault("description", "")
    if not isinstance(doc["description"], str):
        raise ValueError("Description must be a string")
    for page in doc["pages"]:
        page.setdefault("snippet", "")
        if not isinstance(page["snippet"], str):
            raise ValueError("Page snippet must be a string")
    ppt = """import { SceneDeck, type DeckDefinition } from '@shuku/course-style/react/presentation';
import outline from './outlines.json';
import { scenes, getPptNotes } from './course';
export { getPptNotes };
export const deck:DeckDefinition={id:outline.id,title:outline.title,subtitle:outline.description,scenes};
export function CoursePpt(){return <SceneDeck catalog={[deck]} moduleId={outline.id} assetId={outline.moduleIdentity.id} progressKey={outline.moduleIdentity.id+':ppt'} getNotes={getPptNotes}/>;}
"""
    return doc, {
        "outlines.json": json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        "GuidePage.tsx": guide,
        "CoursePpt.tsx": ppt,
        "course.tsx": course,
    }


def initialize(root, directory, outline, dry_run=False):
    doc, files = plan_module(root, directory, outline)
    if not dry_run:
        work = root / "work"
        work.mkdir(exist_ok=True)
        modules_directory(root).mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="module-init-", dir=work) as temporary:
            stage = Path(temporary).resolve()
            if not stage.is_relative_to(work.resolve()):
                raise ValueError("Staging directory escaped workspace")
            for name, content in files.items():
                (stage / name).write_text(content, encoding="utf-8")
            (stage / "assets").mkdir()
            # On Windows, rename fails if another process created the destination.
            stage.rename(modules_directory(root) / directory)
    return {
        "module": directory,
        "uuid": doc["moduleIdentity"]["id"],
        "files": list(files),
        "dry_run": dry_run,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        emit_result(
            ensure_outline(require_target_root(args.repository), args.directory, args.title, args.dry_run)
        )
        return 0
    except (OSError, ValueError) as exc:
        return report_error(exc)


if __name__ == "__main__":
    raise SystemExit(main())
