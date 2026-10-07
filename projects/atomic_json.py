"""Process-safe JSON persistence helpers for canonical registries."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
import uuid
import threading
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def registry_lock(path: str | Path):
    lock_path = Path(str(path) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


_project_lock_state = threading.local()


@contextmanager
def project_lock(identity: str):
    root = Path(__file__).resolve().parents[1] / ".project-locks"
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    held = getattr(_project_lock_state, "held", set())
    if key in held:
        yield
        return
    with registry_lock(root / key):
        held = set(held); held.add(key); _project_lock_state.held = held
        try:
            yield
        finally:
            held.remove(key); _project_lock_state.held = held


def read_json(path: str | Path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def atomic_write_json(path: str | Path, value, validator=None) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if validator:
        validator(value)
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, target)
        dir_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        reread = read_json(target)
        if reread != value:
            raise ValueError(f"Post-write JSON verification failed: {target}")
        return hashlib.sha256(payload).hexdigest()
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def validate_project_registry(data):
    if not isinstance(data, dict) or not isinstance(data.get("projects"), list):
        raise ValueError("Project registry must contain a projects array")
    ids = [p.get("project_id") for p in data["projects"]]
    if any(not isinstance(item, str) or not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("Project registry has missing or duplicate project_id values")
    uuids = [p.get("project_uuid") for p in data["projects"]]
    try:
        valid_uuids = all(str(uuid.UUID(value)) == value for value in uuids if isinstance(value, str))
    except (ValueError, AttributeError):
        valid_uuids = False
    if len(uuids) != len(set(uuids)) or any(not isinstance(value, str) for value in uuids) or not valid_uuids:
        raise ValueError("Project registry has missing, invalid, or duplicate project_uuid values")
    for item in data["projects"]:
        if not isinstance(item.get("canonical_path"), str) or not item["canonical_path"]:
            raise ValueError(f"Invalid canonical_path for {item.get('project_id')}")
