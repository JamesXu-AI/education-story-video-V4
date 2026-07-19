"""Canonical department-scoped task workspace paths."""

from __future__ import annotations

from pathlib import Path


DEPARTMENTS = frozenset(
    {
        "screenplay-writer",
        "direct-production-design",
        "previsualize-cinematography",
        "virtual-production",
        "seedance-video-review",
        "finish-postproduction",
    }
)
ROOT_AUTHORITY_FILES = frozenset({"task.json", "story.md"})
IGNORED_ROOT_METADATA_FILES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})


class TaskPathError(RuntimeError):
    """Raised when a task path violates the current workspace contract."""


def task_root(task_dir: str | Path) -> Path:
    root = Path(task_dir).expanduser().resolve()
    if not root.is_dir():
        raise TaskPathError(f"Task directory does not exist: {root}")
    return root


def _inside(root: Path, raw: Path, *, label: str) -> Path:
    resolved = raw.resolve()
    if resolved == root or root not in resolved.parents:
        raise TaskPathError(f"{label} must resolve below the task root")
    return resolved


def department_root(
    task_dir: str | Path,
    department: str,
    *,
    create: bool = False,
) -> Path:
    if department not in DEPARTMENTS:
        raise TaskPathError(f"Unknown task department: {department}")
    root = task_root(task_dir)
    raw = root / department
    if create:
        raw.mkdir(parents=False, exist_ok=True)
    return _inside(root, raw, label=f"{department} directory")


def department_path(
    task_dir: str | Path,
    department: str,
    *parts: str,
    create_parent: bool = False,
) -> Path:
    if not parts or any(not part or Path(part).is_absolute() for part in parts):
        raise TaskPathError("Department path parts must be non-empty relative names")
    root = department_root(task_dir, department, create=create_parent)
    candidate = _inside(root, root.joinpath(*parts), label="Department artifact")
    if create_parent:
        candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def validate_root_files(task_dir: str | Path) -> None:
    root = task_root(task_dir)
    unexpected = sorted(
        path.name
        for path in root.iterdir()
        if path.is_file()
        and path.name not in ROOT_AUTHORITY_FILES
        and path.name not in IGNORED_ROOT_METADATA_FILES
        and not path.name.startswith("._")
    )
    if unexpected:
        raise TaskPathError(
            "Only task.json and story.md may be task-root files; found: "
            + ", ".join(unexpected)
        )
