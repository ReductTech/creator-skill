"""Small shared path and metadata helpers for authoring commands."""

from pathlib import Path
import json
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
SKILL = SCRIPTS.parent
TARGET_ROOT_CONFIG = SKILL / "target-root.json"
sys.path.insert(0, str(SCRIPTS))


def get_target_root(config_file=None):
    """Read the single configured absolute directory; never infer a target."""
    config = Path(config_file) if config_file is not None else TARGET_ROOT_CONFIG
    try:
        document = json.loads(config.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot read target-root.json: {exc}") from exc
    if not isinstance(document, dict) or set(document) != {"targetRoot"}:
        raise ValueError("target-root.json must contain only the targetRoot field")
    value = document["targetRoot"]
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Set targetRoot in target-root.json to the target project's absolute directory")
    root = Path(value)
    if not root.is_absolute():
        raise ValueError("targetRoot must be an absolute directory")
    if not root.is_dir():
        raise ValueError(f"targetRoot directory does not exist: {root}")
    root = root.resolve()
    backend = str(root / "backend/src")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    return root


def __getattr__(name):
    # Existing tools import ROOT; resolve it only for tools that need a project.
    if name == "ROOT":
        return get_target_root()
    raise AttributeError(name)


def require_target_root(requested=None):
    """Legacy root arguments may confirm the configured root, never override it."""
    root = get_target_root()
    if requested is not None and Path(requested).resolve() != root:
        raise ValueError("Target overrides must match targetRoot in target-root.json")
    return root


def project_path(value, *, external=False):
    """Anchor relative paths to the JSON target, independent of the caller's cwd."""
    root = get_target_root()
    value = Path(value).expanduser()
    target = (value if value.is_absolute() else root / value).resolve()
    if not external and not target.is_relative_to(root):
        raise ValueError(f"Path must stay inside targetRoot: {target}")
    return target


def read_modules(root=None):
    root = Path(root) if root is not None else get_target_root()
    for path in sorted((root / "modules").glob("*/outlines.json")):
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(document, dict):
            raise ValueError(f"Invalid outline: {path}")
        yield path.parent, document


def resolve_module(requested, root=None):
    matches = [
        (directory, doc)
        for directory, doc in read_modules(root)
        if requested.lower()
        in {
            directory.name.lower(),
            str(doc.get("id", directory.name)).lower(),
            str(doc.get("moduleIdentity", {}).get("id", "")).lower(),
        }
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one module matching {requested!r}; found {len(matches)}"
        )
    return matches[0]


def emit_result(result: dict, *, status: str = "ok") -> None:
    """Write one JSON result, retaining tool-specific fields and status values."""
    payload = {"status": status, **result}
    print(json.dumps(payload, ensure_ascii=False))


def scratchpad_path(
    directory: Path, requested: Path | None = None, *, default: str,
    page_directory: str | None = None,
) -> Path:
    """Resolve an intermediate output inside its module; reject escapes and symlinks out.

    Explicit paths are relative to cwd, matching other tool path arguments.
    This helper validates only; callers create directories after input validation.
    """
    module = directory.resolve()
    if page_directory is not None:
        if not page_directory or Path(page_directory).name != page_directory or page_directory in {".", ".."} or "/" in page_directory or "\\" in page_directory:
            raise ValueError("Page directory must be a single semantic directory name")
        scratchpad = (module / "pages" / page_directory / "_scratchpad").resolve()
    else:
        scratchpad = (module / "_scratchpad").resolve()
    target = project_path(requested) if requested is not None and not requested.is_absolute() else (requested if requested is not None else scratchpad / default).resolve()
    # Explicit page-local outputs are also valid for tools with module-wide defaults.
    if requested is not None and page_directory is None and target.is_relative_to(module):
        parts = target.relative_to(module).parts
        if len(parts) >= 3 and parts[0] == "pages" and parts[2] == "_scratchpad":
            scratchpad = (module / "pages" / parts[1] / "_scratchpad").resolve()
    if not scratchpad.is_relative_to(module) or not target.is_relative_to(scratchpad):
        raise ValueError(
            f"Intermediate output must be inside the module or selected page _scratchpad: {target}"
        )
    return target


def report_error(error: Exception) -> int:
    """Report an execution error on stderr and return the shared exit code 2."""
    message = str(error)
    print(message, file=sys.stderr)
    emit_result({"error": message}, status="error")
    return 2
