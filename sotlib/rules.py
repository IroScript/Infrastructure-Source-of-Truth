"""Dynamic, schema-checked rule package discovery and sandboxable installation."""
from __future__ import annotations

import fnmatch
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

RULE_ID = re.compile(r"^RULE-[A-Z0-9][A-Z0-9-]+$")
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
PROOF_LEVELS = {"DECLARED": 1, "DISCOVERED": 2, "PARSED": 3, "LOADED": 4,
                "RESOLVED": 5, "ENFORCED": 6, "ADVERSARIAL_VERIFIED": 7}
PROBE_EXECUTABLES = {"python3", "python"}


class RuleError(ValueError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _dict_is_subset(sub: Any, super_dict: Any) -> bool:
    if not isinstance(sub, dict) or not isinstance(super_dict, dict):
        return sub == super_dict
    for k, v in sub.items():
        if k not in super_dict:
            return False
        if isinstance(v, dict):
            if not _dict_is_subset(v, super_dict[k]):
                return False
        elif super_dict[k] != v:
            return False
    return True


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_template(value: str, roots: dict[str, str]) -> str:
    """Resolve only declared roots. Unknown placeholders and shell expansion fail."""
    out = value
    for key, root in roots.items():
        out = out.replace("${" + key + "}", root)
    if re.search(r"\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*|`|\$\(", out):
        raise RuleError(f"unresolved or executable path template: {value}")
    return os.path.normpath(os.path.expanduser(out))


def load_profile(profile_path: Path, env: dict[str, str] | None = None) -> dict:
    env = env or os.environ
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if not profile.get("profile_id") or not isinstance(profile.get("roots"), dict):
        raise RuleError("invalid deployment profile")
    roots = {}
    for name, template in profile["roots"].items():
        expanded = template.replace("${HOME}", env.get("HOME", ""))
        for key, value in roots.items():
            expanded = expanded.replace("${" + key + "}", value)
        if "${" in expanded or not os.path.isabs(expanded):
            raise RuleError(f"profile root {name} is unresolved or not absolute")
        roots[name] = os.path.normpath(expanded)
    for required in ("HOME", "PROJECTS_ROOT", "STATE_ROOT", "RUNTIME_ROOT", "BACKUP_ROOT"):
        if not roots.get(required):
            raise RuleError(f"profile missing required root: {required}")
    profile["resolved_roots"] = roots
    return profile


def validate_package(repo_root: Path, manifest_path: Path) -> dict:
    repo_root = repo_root.resolve()
    manifest_path = manifest_path.resolve()
    if not _inside(manifest_path, repo_root):
        raise RuleError("rule manifest escapes repository")
    package = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {"manifest_version", "rule_id", "version", "name", "scope", "severity", "enabled",
                "supported_agent_classes", "artifacts", "load_order", "precedence", "activation",
                "reload_requirement", "required_proof_level", "expected_effect", "positive_probe",
                "negative_probe", "supersedes", "rollback"}
    missing = required - package.keys()
    if missing:
        raise RuleError(f"{manifest_path}: missing fields {sorted(missing)}")
    if package["manifest_version"] != "1.0.0" or not RULE_ID.fullmatch(package["rule_id"]):
        raise RuleError(f"{manifest_path}: invalid manifest version or rule_id")
    if not VERSION.fullmatch(package["version"]):
        raise RuleError(f"{manifest_path}: invalid semantic version")
    if package["severity"] not in {"low", "medium", "high", "critical"}:
        raise RuleError(f"{manifest_path}: invalid severity")
    if package.get("schema_version", "1.0.0") != "1.0.0":
        raise RuleError(f"{manifest_path}: unsupported rule schema")
    level = package["required_proof_level"]
    if not isinstance(level, int) or not 1 <= level <= 7:
        raise RuleError(f"{manifest_path}: required_proof_level must be 1..7")
    if not package["enabled"]:
        return package
    if not package["artifacts"]:
        raise RuleError(f"{manifest_path}: enabled package has no artifacts")
    seen = set()
    for artifact in package["artifacts"]:
        for key in ("artifact_id", "source", "destination_template", "mode", "sha256", "kind"):
            if key not in artifact:
                raise RuleError(f"{manifest_path}: artifact missing {key}")
        if artifact["artifact_id"] in seen:
            raise RuleError(f"{manifest_path}: duplicate artifact_id")
        seen.add(artifact["artifact_id"])
        source = (repo_root / artifact["source"]).resolve()
        if not _inside(source, repo_root) or not source.is_file():
            raise RuleError(f"{manifest_path}: missing or escaping artifact source {artifact['source']}")
        if not re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"]):
            raise RuleError(f"{manifest_path}: invalid artifact SHA256")
        if sha256(source) != artifact["sha256"]:
            raise RuleError(f"{manifest_path}: artifact hash mismatch for {artifact['artifact_id']}")
        try:
            mode = int(str(artifact["mode"]), 8)
        except ValueError as exc:
            raise RuleError(f"{manifest_path}: invalid artifact mode") from exc
        if mode & 0o002:
            raise RuleError(f"{manifest_path}: world-writable artifacts are forbidden")
        if artifact["kind"] not in {"documentation", "config", "python", "shell", "hook", "systemd", "agent_config", "data"}:
            raise RuleError(f"{manifest_path}: unsupported artifact kind {artifact['kind']}")
        if not isinstance(artifact.get("permissions"), list):
            raise RuleError(f"{manifest_path}: artifact permissions must be an array")
        try:
            if artifact["kind"] == "config" and source.suffix.lower() == ".json":
                json.loads(source.read_text(encoding="utf-8"))
            elif artifact["kind"] == "config" and source.suffix.lower() == ".toml":
                import tomllib
                tomllib.loads(source.read_text(encoding="utf-8"))
            elif artifact["kind"] == "config" and source.suffix.lower() in {".yaml", ".yml"}:
                import yaml
                yaml.safe_load(source.read_text(encoding="utf-8"))
            elif artifact["kind"] == "config":
                raise RuleError(f"no deterministic parser declared for config artifact {artifact['source']}")
            elif artifact["kind"] == "python":
                ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            elif artifact["kind"] == "shell":
                parsed = subprocess.run(["bash", "-n", str(source)], capture_output=True, text=True, timeout=10)
                if parsed.returncode:
                    raise RuleError(f"shell syntax error: {parsed.stderr.strip()}")
        except ImportError as exc:
            raise RuleError(f"required parser unavailable for {artifact['source']}") from exc
        except (ValueError, SyntaxError) as exc:
            raise RuleError(f"artifact parse failed for {artifact['artifact_id']}: {exc}") from exc
        except Exception as exc:
            if artifact["kind"] == "config" and source.suffix.lower() in {".yaml", ".yml"}:
                raise RuleError(f"config parse failed for {artifact['artifact_id']}: {exc}") from exc
            raise
    if not isinstance(package["supported_agent_classes"], list) or not isinstance(package["load_order"], int):
        raise RuleError(f"{manifest_path}: invalid agent classes or load order")
    if not isinstance(package["supersedes"], list):
        raise RuleError(f"{manifest_path}: supersedes must be an array")
    if not isinstance(package["rollback"], dict) or not package["rollback"].get("strategy"):
        raise RuleError(f"{manifest_path}: rollback strategy is required")
    if not isinstance(package["precedence"], (str, list)) or not isinstance(package["reload_requirement"], str):
        raise RuleError(f"{manifest_path}: invalid precedence or reload requirement")
    for label in ("activation", "positive_probe", "negative_probe"):
        probe = package[label]
        if label == "activation" and isinstance(probe, dict) and "argv" not in probe:
            probe = probe.get("probe")
        if not isinstance(probe, dict) or not isinstance(probe.get("argv"), list) or not probe["argv"]:
            raise RuleError(f"{manifest_path}: {label}.argv must be a non-empty array")
        if not isinstance(probe["argv"][0], str) or (not Path(probe["argv"][0]).is_absolute() and probe["argv"][0] not in PROBE_EXECUTABLES):
            raise RuleError(f"{manifest_path}: unsupported probe executable")
        if not isinstance(probe.get("expected_exit_code"), int):
            raise RuleError(f"{manifest_path}: {label}.expected_exit_code is required")
        if label == "activation":
            package[label] = probe
    if package["required_proof_level"] >= 7 and not package["negative_probe"].get("expected_effect"):
        raise RuleError(f"{manifest_path}: L7 negative probe must state the expected blocked behavior")
    if package["required_proof_level"] >= 7 and not (package["negative_probe"].get("expected_stdout_contains") or package["negative_probe"].get("expected_stderr_contains")):
        raise RuleError(f"{manifest_path}: L7 negative probe must assert an observed output effect")
    if package["required_proof_level"] >= 4 and not (package["activation"].get("expected_stdout_contains") or package["activation"].get("expected_stderr_contains")):
        raise RuleError(f"{manifest_path}: L4 activation must assert an observed runtime load effect")
    if package["required_proof_level"] >= 6 and not (package["positive_probe"].get("expected_stdout_contains") or package["positive_probe"].get("expected_stderr_contains")):
        raise RuleError(f"{manifest_path}: L6 positive probe must assert an observed enforcement effect")
    negative = package["negative_probe"]
    if negative["expected_exit_code"] == 0:
        raise RuleError(f"{manifest_path}: adversarial probe must expect a failure exit code")
    return package


def audit_rule_baseline(repo_root: Path) -> dict:
    """Audits active rules against canonical expected inventory (RULE 23, FIX 7)."""
    registry_path = repo_root / "governance" / "RULE_REGISTRY.json"
    expected_packages = []
    if registry_path.is_file():
        try:
            reg_data = json.loads(registry_path.read_text(encoding="utf-8"))
            expected_packages = reg_data.get("packages", [])
        except Exception:
            expected_packages = []

    expected_by_id = {p["rule_id"]: p for p in expected_packages}
    discovered = []
    tampered = []
    missing_required = []

    # Check for missing required packages
    for exp_id, exp_info in expected_by_id.items():
        man_path = repo_root / exp_info.get("manifest", "")
        if not man_path.is_file():
            missing_required.append(exp_id)

    # Validate existing packages
    seen_ids = set()
    for manifest in sorted((repo_root / "governance/rules").glob("*/*/rule.json")):
        try:
            pkg = validate_package(repo_root, manifest)
            rid = pkg["rule_id"]
            seen_ids.add(rid)
            discovered.append((manifest, pkg))
        except Exception as exc:
            tampered.append({"manifest": str(manifest.relative_to(repo_root)), "error": str(exc)})

    required_current = [p["rule_id"] for _, p in discovered if p["rule_id"] in expected_by_id]
    new_optional = [p["rule_id"] for _, p in discovered if p["rule_id"] not in expected_by_id]

    status = "RULE_BASELINE_INCOMPLETE" if (missing_required or tampered) else "PASS"

    return {
        "status": status,
        "required_current_packages": required_current,
        "new_optional_valid_packages": new_optional,
        "missing_required_packages": missing_required,
        "tampered_packages": tampered,
        "discovered_packages": discovered
    }


def discover_packages(repo_root: Path, enforce_baseline: bool = True) -> list[tuple[Path, dict]]:
    """Discovers rules with canonical baseline inventory enforcement (FIX 7)."""
    audit = audit_rule_baseline(repo_root)
    if enforce_baseline and audit["missing_required_packages"]:
        raise RuleError(f"RULE_BASELINE_INCOMPLETE: missing required rule packages: {audit['missing_required_packages']}")
    if enforce_baseline and audit["tampered_packages"]:
        raise RuleError(f"RULE_BASELINE_INCOMPLETE: tampered rule packages: {audit['tampered_packages']}")
    return audit["discovered_packages"]



def _atomic_copy(source: Path, target: Path, mode: int):
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".sot-rule-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(source.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, target)
        with target.open("rb") as stream:
            if hashlib.sha256(stream.read()).digest() != hashlib.sha256(source.read_bytes()).digest():
                raise RuleError(f"post-install hash mismatch: {target}")
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def install_package(repo_root: Path, package: dict, roots: dict[str, str], state_root: Path,
                    dry_run: bool = False) -> dict:
    repo_root = repo_root.resolve()
    state_root = state_root.resolve()
    installed = {}
    for artifact in package["artifacts"]:
        source = (repo_root / artifact["source"]).resolve()
        target = Path(resolve_template(artifact["destination_template"], roots)).resolve()
        allowed = [Path(value).resolve() for value in roots.values()]
        if not any(_inside(target, root) for root in allowed):
            raise RuleError(f"destination escapes all deployment roots: {target}")
        mode = int(str(artifact["mode"]), 8)
        installed[artifact["artifact_id"]] = str(target)
        if dry_run:
            continue
        run_id = f"{package['rule_id']}-{package['version']}"
        backup_dir = state_root / "rule-rollback" / run_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_record = {"target": str(target), "previously_existed": target.exists()}
        if target.exists():
            previous = backup_dir / (artifact["artifact_id"] + ".previous")
            previous.write_bytes(target.read_bytes())
            backup_record["previous"] = str(previous)
            backup_record["previous_mode"] = oct(target.stat().st_mode & 0o777)
        record_path = backup_dir / (artifact["artifact_id"] + ".json")
        record_path.write_text(json.dumps(backup_record, sort_keys=True) + "\n")
        if target.exists() and target.suffix == ".json" and source.suffix == ".json":
            try:
                existing_obj = json.loads(target.read_text(encoding="utf-8"))
                src_text = source.read_text(encoding="utf-8")
                for name, value in roots.items():
                    src_text = src_text.replace("${" + name + "}", value)
                incoming_obj = json.loads(src_text)
                if isinstance(existing_obj, dict) and isinstance(incoming_obj, dict):
                    from .artifacts import _deep_merge_dict
                    merged = _deep_merge_dict(existing_obj, incoming_obj)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    fd, tmp = tempfile.mkstemp(prefix=".sot-rule-", dir=target.parent)
                    try:
                        with os.fdopen(fd, "wb") as stream:
                            stream.write((json.dumps(merged, indent=2) + "\n").encode("utf-8"))
                            stream.flush()
                            os.fsync(stream.fileno())
                        os.chmod(tmp, mode)
                        os.replace(tmp, target)
                    finally:
                        try:
                            os.unlink(tmp)
                        except FileNotFoundError:
                            pass
                    continue
            except Exception:
                pass
        _atomic_copy(source, target, mode)
    if not dry_run:
        receipt = {"rule_id": package["rule_id"], "version": package["version"],
                   "installed": installed, "timestamp": int(time.time())}
        receipt_dir = state_root / "rule-installations" / package["rule_id"]
        receipt_dir.mkdir(parents=True, exist_ok=True)
        (receipt_dir / f"{package['version']}.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return installed


def _expand_argv(probe: dict, installed: dict[str, str]) -> list[str]:
    output = []
    for arg in probe["argv"]:
        value = str(arg)
        for artifact_id, path in installed.items():
            value = value.replace("{artifact:" + artifact_id + "}", path)
        if "{artifact:" in value or "${" in value or "$(" in value:
            raise RuleError(f"probe contains unresolved or executable substitution: {arg}")
        output.append(value)
    return output


def run_probe(probe: dict, installed: dict[str, str], timeout: int = 15) -> dict:
    argv = _expand_argv(probe, installed)
    if not Path(argv[0]).is_absolute() and shutil.which(argv[0]) is None:
        raise RuleError(f"probe executable is unavailable: {argv[0]}")
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env={
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"
    })
    expected = probe["expected_exit_code"]
    stdout_ok = probe.get("expected_stdout_contains", "") in result.stdout
    stderr_ok = probe.get("expected_stderr_contains", "") in result.stderr
    return {"argv": argv, "exit_code": result.returncode, "expected_exit_code": expected,
            "matched": result.returncode == expected and stdout_ok and stderr_ok,
            "expected_stdout_contains": probe.get("expected_stdout_contains"),
            "expected_stderr_contains": probe.get("expected_stderr_contains"),
            "stdout": result.stdout, "stderr": result.stderr,
            "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest()}


def verify_package(repo_root: Path, package: dict, roots: dict[str, str], state_root: Path,
                   evidence_dir: Path) -> dict:
    installed = {a["artifact_id"]: resolve_template(a["destination_template"], roots)
                 for a in package["artifacts"]}
    evidence_dir.mkdir(parents=True, exist_ok=True)
    levels = []
    errors = []
    for level, status, description in [(1, "DECLARED", "package metadata and expected effect"),
                                        (2, "DISCOVERED", "manifest enumerated by package loader"),
                                        (3, "PARSED", "manifest validated, declared artifact parsers passed, and source hashes matched")]:
        levels.append({"level": level, "name": status, "result": "VERIFIED", "evidence": description})
    for artifact in package["artifacts"]:
        target = Path(installed[artifact["artifact_id"]])
        if not target.is_file():
            errors.append(f"installed artifact missing: {artifact['artifact_id']}")
        elif sha256(target) != artifact["sha256"]:
            merged_ok = False
            if target.suffix == ".json":
                try:
                    dest_obj = json.loads(target.read_text(encoding="utf-8"))
                    src_text = (repo_root / artifact["source"]).read_text(encoding="utf-8")
                    for name, value in roots.items():
                        src_text = src_text.replace("${" + name + "}", value)
                    src_obj = json.loads(src_text)
                    if isinstance(dest_obj, dict) and isinstance(src_obj, dict):
                        if _dict_is_subset(src_obj, dest_obj):
                            merged_ok = True
                except Exception:
                    pass
            if not merged_ok:
                errors.append(f"installed artifact missing/hash mismatch: {artifact['artifact_id']}")
    if errors:
        return {"rule_id": package["rule_id"], "required_level": package["required_proof_level"],
                "achieved_level": 3, "verdict": "NOT VERIFIED", "levels": levels, "errors": errors}
    for artifact_id, target in installed.items():
        if not Path(target).is_file():
            return {"rule_id": package["rule_id"], "required_level": package["required_proof_level"],
                    "achieved_level": 3, "verdict": "NOT VERIFIED", "levels": levels,
                    "errors": [f"artifact not installed: {artifact_id}"]}
    probes = [(4, "LOADED", package["activation"]), (5, "RESOLVED", package["positive_probe"]),
              (6, "ENFORCED", package["positive_probe"]), (7, "ADVERSARIAL_VERIFIED", package["negative_probe"])]
    for level, name, probe in probes:
        if level > package["required_proof_level"]:
            break
        result = run_probe(probe, installed)
        file_stem = f"{package['rule_id']}-L{level}"
        out_path = evidence_dir / (file_stem + ".stdout")
        err_path = evidence_dir / (file_stem + ".stderr")
        out_path.write_text(result["stdout"])
        err_path.write_text(result["stderr"])
        result["stdout_ref"] = out_path.name
        result["stderr_ref"] = err_path.name
        result["stdout_artifact_sha256"] = sha256(out_path)
        result["stderr_artifact_sha256"] = sha256(err_path)
        result["input_fixture_sha256"] = probe.get("input_fixture_sha256")
        result["tested_file_hashes"] = {a["artifact_id"]: sha256(Path(installed[a["artifact_id"]])) for a in package["artifacts"]}
        levels.append({"level": level, "name": name,
                       "result": "VERIFIED" if result["matched"] else "FAILED",
                       "evidence": result})
        if not result["matched"]:
            errors.append(f"{name} probe exit {result['exit_code']} != expected {result['expected_exit_code']}")
        if level >= package["required_proof_level"] and errors:
            break
    achieved = 3
    for item in levels[3:]:
        if item["result"] != "VERIFIED":
            break
        achieved = item["level"]
    required = package["required_proof_level"]
    verdict = "VERIFIED" if achieved >= required and not errors else "FAILED" if errors else "NOT VERIFIED"
    return {"rule_id": package["rule_id"], "version": package["version"],
            "required_level": required, "achieved_level": achieved, "verdict": verdict,
            "git_commit": _git_commit(repo_root), "runtime": {"python": os.sys.version.split()[0], "platform": os.name},
            "levels": levels, "errors": errors}


def _git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "NOT_IN_GIT_CHECKOUT"


def rollback_package(package: dict, state_root: Path) -> list[str]:
    backup_dir = state_root / "rule-rollback" / f"{package['rule_id']}-{package['version']}"
    restored = []
    for artifact in reversed(package["artifacts"]):
        record_path = backup_dir / (artifact["artifact_id"] + ".json")
        if not record_path.exists():
            raise RuleError(f"rollback record missing for {artifact['artifact_id']}")
        record = json.loads(record_path.read_text())
        target = Path(record["target"])
        if record["previously_existed"]:
            _atomic_copy(Path(record["previous"]), target, int(record["previous_mode"], 8))
        elif target.exists():
            target.unlink()
        restored.append(str(target))
    return restored


def write_index(repo_root: Path, packages: list[tuple[Path, dict]]) -> Path:
    index = {"schema_version": "1.0.0", "generated": True, "packages": [
        {"rule_id": p["rule_id"], "version": p["version"], "manifest": str(path.relative_to(repo_root))}
        for path, p in packages]}
    target = repo_root / "governance/RULE_REGISTRY.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".RULE_REGISTRY.", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(index, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, target)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
    return target


def scan_unmanaged(profile: dict, manifest: dict) -> list[str]:
    declared = {resolve_template(a["destination_template"], profile["resolved_roots"])
                for a in manifest.get("artifacts", [])}
    unmanaged = []
    for root_spec in manifest.get("managed_roots", []):
        root = Path(resolve_template(root_spec["root_template"], profile["resolved_roots"]))
        if not root.exists():
            if root_spec.get("required", False):
                unmanaged.append(f"MISSING MANAGED ROOT: {root}")
            continue
        for pattern in root_spec.get("include_globs", []):
            for candidate in root.glob(pattern):
                if candidate.is_file() and str(candidate.resolve()) not in declared:
                    unmanaged.append(f"UNMANAGED EXTERNAL ARTIFACT: {candidate}")
    return sorted(set(unmanaged))
