#!/usr/bin/env python3
"""Provider-neutral fail-closed validation for independent verifier records."""
import json
import hashlib
import re
import sys
from pathlib import Path

REQUIRED = {"task_id", "verifier_id", "verifier_type", "timestamp", "claim", "evidence", "deterministic_result", "independent_verdict", "unresolved_items", "confidence_category"}
TYPES = {"codex", "claude", "agy_strong_model", "generic_cli", "manual_external", "deterministic"}


def validate(record, bundle_root=None):
    if not isinstance(record, dict) or not REQUIRED.issubset(record):
        return False, "missing required top-level evidence fields"
    if not all(isinstance(record[k], str) and record[k] for k in ("task_id", "verifier_id", "timestamp", "claim")):
        return False, "required identity/claim fields must be nonempty strings"
    if record["verifier_type"] not in TYPES or record["independent_verdict"] not in {"approved", "correction_needed", "inconclusive"}:
        return False, "unknown verifier or verdict"
    evidence = record["evidence"]
    if not isinstance(evidence, list) or not evidence:
        return False, "evidence must contain at least one machine evidence record"
    if not isinstance(record.get("unresolved_items"), list) or record.get("deterministic_result") not in {"pass", "fail", "inconclusive"}:
        return False, "unresolved_items or deterministic_result is invalid"
    if record["independent_verdict"] == "approved" and record["deterministic_result"] != "pass":
        return False, "approval requires deterministic_result=pass"
    bundle_root = Path(bundle_root or ".").resolve()

    def verify_ref(ref, expected_hash):
        path = Path(ref)
        if path.is_absolute():
            return False, "evidence references must be bundle-relative"
        target = (bundle_root / path).resolve()
        if not target.is_relative_to(bundle_root) or not target.is_file():
            return False, f"evidence artifact missing or escapes bundle: {ref}"
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if not re.fullmatch(r"[a-f0-9]{64}", str(expected_hash)) or actual != expected_hash:
            return False, f"evidence artifact hash mismatch: {ref}"
        return True, ""

    for item in evidence:
        required = ("command", "arguments", "stdout_ref", "stderr_ref", "stdout_sha256", "stderr_sha256",
                    "exit_code", "files_inspected", "negative_tests", "commit_sha", "runtime_identity", "timestamp")
        if not isinstance(item, dict) or not all(k in item for k in required):
            return False, "evidence record is incomplete"
        if (not isinstance(item["command"], str) or not item["command"] or not isinstance(item["arguments"], list)
                or not isinstance(item["exit_code"], int) or not item["runtime_identity"] or not item["commit_sha"]):
            return False, "command outputs and exit code are mandatory"
        if record["deterministic_result"] == "pass" and item["exit_code"] != 0:
            return False, "passing deterministic evidence must have exit_code=0"
        if not isinstance(item["files_inspected"], list) or not item["files_inspected"]:
            return False, "inspected-file hashes are mandatory"
        if not isinstance(item["negative_tests"], list) or not item["negative_tests"]:
            return False, "negative test records are mandatory"
        for key in ("stdout_ref", "stderr_ref"):
            ok, message = verify_ref(item[key], item[key.replace("_ref", "_sha256")])
            if not ok:
                return False, message
        for file in item["files_inspected"]:
            if not isinstance(file, dict) or not file.get("path") or not file.get("artifact_ref") or not re.fullmatch(r"[a-fA-F0-9]{64}", str(file.get("sha256", ""))):
                return False, "invalid inspected-file SHA256"
            ok, message = verify_ref(file["artifact_ref"], file["sha256"])
            if not ok:
                return False, message
        for negative in item["negative_tests"]:
            fields = ("command", "arguments", "exit_code", "expected_exit_code", "expected_effect", "observed_effect",
                      "matched", "stdout_ref", "stderr_ref", "stdout_sha256", "stderr_sha256")
            if not isinstance(negative, dict) or not all(k in negative for k in fields):
                return False, "negative test lacks executable result semantics"
            if not isinstance(negative["arguments"], list) or negative["expected_exit_code"] == 0:
                return False, "negative test must describe arguments and expect nonzero exit"
            if negative["exit_code"] != negative["expected_exit_code"] or negative["matched"] is not True:
                return False, "negative test did not satisfy expected failure semantics"
            if not negative["expected_effect"] or not negative["observed_effect"]:
                return False, "negative test effect must be observed and stated"
            if not (negative.get("expected_stdout_contains") or negative.get("expected_stderr_contains")):
                return False, "negative test must assert a concrete output effect"
            for key in ("stdout_ref", "stderr_ref"):
                ok, message = verify_ref(negative[key], negative[key.replace("_ref", "_sha256")])
                if not ok:
                    return False, message
            stdout_text=(bundle_root/negative["stdout_ref"]).read_text(encoding="utf-8",errors="replace")
            stderr_text=(bundle_root/negative["stderr_ref"]).read_text(encoding="utf-8",errors="replace")
            if negative.get("expected_stdout_contains") and negative["expected_stdout_contains"] not in stdout_text:
                return False, "negative-test expected stdout effect is absent"
            if negative.get("expected_stderr_contains") and negative["expected_stderr_contains"] not in stderr_text:
                return False, "negative-test expected stderr effect is absent"
    return True, "structured verifier evidence valid"


if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            raise ValueError("usage: validate_verifier_result.py RECORD.json [BUNDLE_ROOT]")
        ok, message = validate(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2] if len(sys.argv) > 2 else Path(sys.argv[1]).parent)
    except Exception as exc:
        print(f"INVALID: {exc}"); raise SystemExit(1)
    print(("VALID: " if ok else "INVALID: ") + message)
    raise SystemExit(0 if ok else 1)
