"""Manifest-driven installation and drift detection for files outside SOT."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import time
from pathlib import Path

from .rules import RuleError, _atomic_copy, _inside, discover_packages, resolve_template, sha256


def load_manifest(repo_root: Path) -> dict:
    path = repo_root / "external/EXTERNAL_ARTIFACTS.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("manifest_version") != "1.0.0":
        raise RuleError("unsupported external artifact manifest version")
    ids = set()
    for item in data.get("artifacts", []):
        required = {"artifact_id", "source", "destination_template", "agent_runtime", "owner", "mode",
                    "permissions", "sha256", "activation", "reload", "verification_probe", "required"}
        if not required.issubset(item):
            raise RuleError(f"external artifact missing fields: {sorted(required-item.keys())}")
        if item["artifact_id"] in ids:
            raise RuleError(f"duplicate external artifact_id: {item['artifact_id']}")
        ids.add(item["artifact_id"])
        source = (repo_root / item["source"]).resolve()
        if not _inside(source, repo_root) or not source.is_file() or sha256(source) != item["sha256"]:
            raise RuleError(f"source missing, escapes SOT, or hash mismatch: {item['artifact_id']}")
        if item["owner"] not in {"current_user", "root", "declared_group"}:
            raise RuleError(f"unsupported owner policy: {item['owner']}")
        try:
            mode = int(str(item["mode"]), 8)
        except ValueError as exc:
            raise RuleError(f"invalid mode: {item['artifact_id']}") from exc
        if mode & 0o002:
            raise RuleError(f"world-writable artifact forbidden: {item['artifact_id']}")
        if not isinstance(item["permissions"], list) or (bool(mode & 0o111) != ("execute" in item["permissions"])):
            raise RuleError(f"permissions do not match executable mode: {item['artifact_id']}")
    return data


def verify(repo_root: Path, profile: dict) -> dict:
    manifest = load_manifest(repo_root)
    roots = dict(profile["resolved_roots"])
    roots["SOT_ROOT"] = str(repo_root.resolve())
    declared = set()
    errors = []
    checked = []
    for item in manifest["artifacts"]:
        destination = Path(resolve_template(item["destination_template"], roots)).resolve()
        allowed = [Path(v).resolve() for v in roots.values()]
        if not any(_inside(destination, x) for x in allowed):
            errors.append(f"destination escapes deployment roots: {item['artifact_id']}")
            continue
        declared.add(str(destination))
        source = repo_root / item["source"]
        expected = source.read_bytes()
        if item.get("render_template", False):
            text = expected.decode("utf-8")
            for name, value in roots.items():
                text = text.replace("${" + name + "}", value)
            if "${" in text:
                errors.append(f"unresolved template variable: {item['artifact_id']}")
                continue
            expected = text.encode("utf-8")
        expected_sha = hashlib.sha256(expected).hexdigest()
        if not destination.is_file():
            if item["required"]:
                errors.append(f"missing required external artifact: {destination}")
            continue
        if sha256(destination) != expected_sha:
            errors.append(f"hash mismatch: {destination}")
        if stat.S_IMODE(destination.stat().st_mode) != int(str(item["mode"]), 8):
            errors.append(f"mode mismatch: {destination}")
        checked.append({"artifact_id": item["artifact_id"], "destination": str(destination),
                        "sha256": sha256(destination), "expected_sha256": expected_sha, "source_sha256": sha256(source)})
    for _, package in discover_packages(repo_root):
        for artifact in package["artifacts"]:
            destination = Path(resolve_template(artifact["destination_template"], roots)).resolve()
            declared.add(str(destination))
            if not destination.is_file() or sha256(destination) != artifact["sha256"]:
                errors.append(f"installed rule artifact missing/hash mismatch: {package['rule_id']}:{artifact['artifact_id']}")
            elif stat.S_IMODE(destination.stat().st_mode) != int(str(artifact["mode"]), 8):
                errors.append(f"installed rule artifact mode mismatch: {package['rule_id']}:{artifact['artifact_id']}")
    unmanaged = []
    for spec in manifest.get("managed_roots", []):
        root = Path(resolve_template(spec["root_template"], roots)).resolve()
        if not root.exists():
            if spec.get("required", False):
                unmanaged.append(f"MISSING MANAGED ROOT: {root}")
            continue
        for pattern in spec["include_globs"]:
            for path in root.glob(pattern):
                if path.is_file() and str(path.resolve()) not in declared:
                    unmanaged.append(f"UNMANAGED EXTERNAL ARTIFACT: {path.resolve()}")
    return {"ok": not errors and not unmanaged, "checked": checked,
            "errors": errors, "unmanaged": sorted(set(unmanaged))}


def install(repo_root: Path, profile: dict, state_root: Path, dry_run=False) -> list[dict]:
    manifest = load_manifest(repo_root)
    roots = dict(profile["resolved_roots"])
    roots["SOT_ROOT"] = str(repo_root.resolve())
    installed = []
    for item in manifest["artifacts"]:
        target = Path(resolve_template(item["destination_template"], roots)).resolve()
        if not any(_inside(target, Path(v).resolve()) for v in roots.values()):
            raise RuleError(f"destination escapes deployment roots: {item['artifact_id']}")
        source = repo_root / item["source"]
        mode = int(str(item["mode"]), 8)
        if not dry_run:
            backup_dir=state_root/"external-rollback"; backup_dir.mkdir(parents=True,exist_ok=True)
            record={"artifact_id":item["artifact_id"],"target":str(target),"previously_existed":target.exists()}
            if target.exists():
                previous=backup_dir/(item["artifact_id"]+".previous")
                previous.write_bytes(target.read_bytes());record["previous"]=str(previous);record["previous_mode"]=oct(stat.S_IMODE(target.stat().st_mode))
            (backup_dir/(item["artifact_id"]+".json")).write_text(json.dumps(record,sort_keys=True)+"\n")
            if item.get("render_template", False):
                content = source.read_text(encoding="utf-8")
                for name, value in roots.items():
                    content = content.replace("${" + name + "}", value)
                if "${" in content:
                    raise RuleError(f"unresolved template variable: {item['artifact_id']}")
                target.parent.mkdir(parents=True, exist_ok=True)
                fd, temp = tempfile.mkstemp(prefix=".sot-artifact-", dir=target.parent)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(content.encode("utf-8")); stream.flush(); os.fsync(stream.fileno())
                    os.chmod(temp, mode); os.replace(temp, target)
                finally:
                    try: os.unlink(temp)
                    except FileNotFoundError: pass
            else:
                _atomic_copy(source, target, mode)
        installed.append({"artifact_id": item["artifact_id"], "destination": str(target),
                          "sha256": item["sha256"], "dry_run": dry_run})
    if not dry_run:
        receipt=state_root/"external-installation.json";receipt.parent.mkdir(parents=True,exist_ok=True)
        receipt.write_text(json.dumps({"installed":installed,"timestamp":int(time.time())},indent=2)+"\n")
    return installed


def rollback(state_root: Path) -> list[str]:
    backup_dir=state_root/"external-rollback";restored=[]
    records=sorted(backup_dir.glob("*.json"),reverse=True)
    for path in records:
        record=json.loads(path.read_text());target=Path(record["target"])
        if record["previously_existed"]:
            _atomic_copy(Path(record["previous"]),target,int(record["previous_mode"],8))
        elif target.exists():target.unlink()
        restored.append(str(target))
    return restored
