#!/usr/bin/env python3
"""
Delete Guard Hook - Sudo & Delete Permitted with Hard Project Boundary Isolation (v4.0)
Updated per user requirement:
"no....delete command rules ekhon lagbe naa, it means agy cli has the permisiion to delete... even it can run sudo commands... but project gulor alada boundary thakbe, maane ek whatsapp agent onno agent er kaaj dekhte paabe na, access o korte parbe naa"

Enforces:
1. Sudo Commands = APPROVED & PERMITTED for AGY CLI operations.
2. Delete Operations = APPROVED & PERMITTED for workspace files, builds, folders, caches, and cleanup operations.
3. Hard Inter-Agent Project Boundary Isolation:
   - Each WhatsApp project agent is strictly jailed to its own project directory.
   - Cross-project file viewing (view_file), modification (write_to_file, replace_file_content), or command execution (run_command Cwd / CommandLine) targeting another project's workspace is strictly BLOCKED.
   - Master Agent (agy:0) running at /home/azureuser operates as principal orchestrator.
4. Critical System Roots (/etc, /boot, /root, /sys, /proc, /dev, /) = PROTECTED from catastrophic recursive deletion.
5. Cryptographic Verification Secret Key exfiltration = PROHIBITED.
6. Destructive Git Force Push / Delete (git push --force, git branch -D, gh repo delete) = PROHIBITED.
7. Protected Configuration Tampering (hooks.json, delete_guard.py, completion_gate_stop_hook.py, chmod on .agents) = PROHIBITED.
"""

import sys
import os
import re
import json
import shlex
import uuid
from datetime import datetime, timezone
from pathlib import Path

def resolve_roots_and_incident_paths():
    home = os.environ.get("HOME", str(Path.home()))
    projects_root = os.environ.get("PROJECTS_ROOT") or os.environ.get("AGY_PROJECTS_ROOT")
    state_root = os.environ.get("STATE_ROOT") or os.environ.get("SOT_STATE_ROOT")
    
    profile_path = os.environ.get("SOT_DEPLOYMENT_PROFILE") or os.environ.get("DEPLOYMENT_PROFILE") or os.environ.get("AGY_DEPLOYMENT_PROFILE")
    if profile_path and os.path.exists(profile_path):
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                prof = json.load(f)
            roots = prof.get("roots", {})
            if "HOME" in roots:
                val = roots["HOME"].replace("$" + "{HOME}", home)
                home = val.replace("/home/azureuser", os.environ.get("HOME", home))
            if "PROJECTS_ROOT" in roots and not projects_root:
                val = roots["PROJECTS_ROOT"].replace("$" + "{HOME}", home)
                projects_root = val.replace("/home/azureuser", home)
            if "STATE_ROOT" in roots and not state_root:
                val = roots["STATE_ROOT"].replace("$" + "{HOME}", home)
                state_root = val.replace("/home/azureuser", home)
        except Exception:
            pass

    if not projects_root:
        projects_root = os.path.join(home, "IroScript_Projects")

    inc_dir = os.environ.get("INCIDENT_DIR") or os.environ.get("SOT_INCIDENT_DIR")
    inc_log = os.environ.get("INCIDENT_LOG") or os.environ.get("SOT_INCIDENT_LOG")
    
    if not inc_dir:
        if state_root:
            inc_dir = os.path.join(state_root, "incidents", "active")
        else:
            inc_dir = os.path.join(home, "AGY-MASTER", "INCIDENTS", "active")

    if not inc_log:
        if state_root:
            inc_log = os.path.join(state_root, "incidents", "delete_attempts.jsonl")
        else:
            inc_log = os.path.join(home, "AGY-MASTER", "INCIDENTS", "delete_attempts.jsonl")

    registry_path = os.environ.get("PROTECTED_REGISTRY_PATH", os.path.join(home, "AGY-MASTER", "POLICIES", "protected_registry.json"))
    archive_root = os.environ.get("GLOBAL_ARCHIVE_ROOT", os.path.join(home, "GLOBAL-ARCHIVE"))

    return home, projects_root, inc_dir, inc_log, registry_path, archive_root

HOME, PROJECTS_ROOT, INCIDENT_DIR, INCIDENT_LOG, REGISTRY_PATH, ARCHIVE_ROOT = resolve_roots_and_incident_paths()

# System-level root paths that must never be wiped
CRITICAL_SYSTEM_ROOTS = [
    "/",
    "/etc",
    "/bin",
    "/sbin",
    "/usr",
    "/boot",
    "/root",
    "/sys",
    "/proc",
    "/dev"
]

PROTECTED_CONFIG_PATTERNS = [
    r".*\.agents/hooks\.json$",
    r".*\.agents/rules/.*",
    r".*\.agents/verify_10_fold\.py$",
    r".*hooks\.json$",
    r".*completion_gate_stop_hook\.py$",
    r".*delete_guard\.py$",
    r".*\.verification_secret\.key$",
    r".*verification_state\.json$",
    r".*consumed_nonces\.jsonl$",
    r".*\.key$",
    r"/etc/.*",
    r"/bin/.*",
    r"/sbin/.*",
    r"/usr/.*",
    r"/boot/.*",
    r"/root/.*"
]

# Project Boundaries mapping
def get_project_boundaries(home=None, projects_root=None):
    h = home or HOME
    pr = projects_root or PROJECTS_ROOT
    return {
        "yt": [
            os.path.join(pr, "Social Media", "youtube")
        ],
        "frappe": [
            os.path.join(h, "Frappe-erp-Alco"),
            os.path.join(pr, "Frappe-erp-Alco")
        ],
        "tg": [
            os.path.join(pr, "Social Media", "telegram-bot")
        ],
        "history": [
            os.path.join(pr, "Personal Life", "PERSONAL AI AGENT"),
            os.path.join(pr, "Personal Life", "Digital History management"),
            os.path.join(pr, "Digital History")
        ],
        "kids": [
            os.path.join(pr, "Personal Life", "kids_tube_with_folder_seection")
        ],
        "rust": [
            os.path.join(pr, "Personal Life", "Rust_Task_With_Time_Keeping_And_Live_Note")
        ],
        "article": [
            os.path.join(pr, "Article_Publishing_Management", "Article-Publishing-Platform")
        ],
        "game": [
            os.path.join(pr, "Article_Publishing_Management", "3D-Game-Design-Studio")
        ],
        "research": [
            os.path.join(pr, "Ask-And-Research-Agent"),
            os.path.join(pr, "Whatsapp master", "webterminal", "Agy Whatsapp Agents", "Ask-And-Research")
        ],
        "report": [
            os.path.join(pr, "Whatsapp master", "webterminal", "Agy Whatsapp Agents", "Reporting-Agent")
        ]
    }

PROJECT_BOUNDARIES = get_project_boundaries()

def log_incident(tool_name, details, reason, rule_id):
    now = datetime.now(timezone.utc)
    inc_id = f"INC-DEL-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    
    incident = {
        "incident_id": inc_id,
        "timestamp": now.isoformat(),
        "severity": "CRITICAL",
        "detector": "DELETE_GUARD_PRETOOLUSE",
        "tool": tool_name,
        "details": details,
        "decision": "DENIED",
        "reason": reason,
        "rule_id": rule_id
    }

    try:
        _, _, inc_dir, inc_log, _, _ = resolve_roots_and_incident_paths()
        os.makedirs(inc_dir, exist_ok=True)
        os.makedirs(os.path.dirname(inc_log), exist_ok=True)
        inc_file = os.path.join(inc_dir, f"{inc_id}.json")
        with open(inc_file, "w", encoding="utf-8") as f:
            json.dump(incident, f, indent=2)
        with open(inc_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(incident) + chr(10))
    except Exception as e:
        sys.stderr.write(f"Failed to log incident: {e}" + chr(10))
    return incident

def identify_caller_project(cwd_hint=None):
    candidates = []
    if cwd_hint:
        candidates.append(cwd_hint)
    
    # Process ancestry check
    try:
        pid = os.getppid()
        for _ in range(8):
            if pid <= 1:
                break
            try:
                p_cwd = os.path.realpath(f"/proc/{pid}/cwd")
                if p_cwd and p_cwd not in candidates:
                    candidates.append(p_cwd)
                with open(f"/proc/{pid}/stat", "r") as f:
                    stat_line = f.read()
                pid = int(stat_line.split(")")[1].split()[1])
            except Exception:
                break
    except Exception:
        pass

    for cand in candidates:
        real_cand = os.path.realpath(cand)
        for p_key, roots in PROJECT_BOUNDARIES.items():
            for r in roots:
                real_r = os.path.realpath(r)
                if real_cand == real_r or real_cand.startswith(real_r + "/"):
                    return p_key, roots

    return None, []

def check_cross_project_violation(caller_key, allowed_roots, target_path):
    if not caller_key or not target_path:
        return False, ""
    try:
        real_target = os.path.realpath(os.path.abspath(str(target_path).strip()))
    except Exception:
        real_target = str(target_path).strip()

    # If the target is within the agent's own allowed roots, it is allowed
    for r in allowed_roots:
        real_r = os.path.realpath(r)
        if real_target == real_r or real_target.startswith(real_r + "/"):
            return False, ""

    # If the target enters ANY OTHER project directory, it is a boundary violation
    for other_key, other_roots in PROJECT_BOUNDARIES.items():
        if other_key == caller_key:
            continue
        for other_r in other_roots:
            real_other = os.path.realpath(other_r)
            if real_target == real_other or real_target.startswith(real_other + "/"):
                return True, f"Agent [{caller_key}] attempted cross-project access to [{other_key}] path: {real_target}"

    return False, ""

def is_path_protected_config(target_path):
    if not target_path:
        return False
    target_raw = str(target_path).strip()
    target_abs = os.path.abspath(target_raw)
    target_real = os.path.realpath(target_abs)
    for pat in PROTECTED_CONFIG_PATTERNS:
        if re.search(pat, target_raw) or re.search(pat, target_abs) or re.search(pat, target_real):
            return True
    return False

def check_rm_targets(command_str):
    for match in re.finditer(r'\b(?:rm|unlink|rmdir)\s+([^;&|`$\n]+)', command_str):
        args_str = match.group(1).strip()
        try:
            tokens = shlex.split(args_str)
        except Exception:
            tokens = args_str.split()
        for tok in tokens:
            if tok.startswith("-"):
                continue
            # Check catastrophic system roots
            tok_clean = tok.rstrip("/*")
            for root_dir in CRITICAL_SYSTEM_ROOTS:
                if tok == root_dir or tok_clean == root_dir:
                    return True, f"Catastrophic deletion of system root directory '{root_dir}' is prohibited", "CRITICAL_SYSTEM_ROOT_PROTECT"
            if is_path_protected_config(tok):
                return True, f"Deletion on protected configuration '{tok}' is prohibited (Rule 38)", "RULE_38_PROTECTED_CONFIG_DELETE"
    return False, "", ""

def inspect_command(command_str, caller_key, allowed_roots):
    # Rule 39: Destructive Git push operations (force, lease, delete)
    if re.search(r'git\s+push\b.*(?:\s+-(?:f|-force|-force-with-lease|-delete)\b|\s+--force\b|\s+--force-with-lease\b|\s+--delete\b)', command_str):
        return True, "Destructive git force push or delete is prohibited (Rule 39)", "RULE_39_GIT_FORCE_PUSH"

    # Rule 40: Destructive Git branch -D / gh repo delete
    if re.search(r'git\s+branch\b.*(?:\s+-D\b)', command_str):
        return True, "Destructive 'git branch -D' force-deletion is prohibited (Rule 40)", "RULE_40_GIT_FORCE_BRANCH_DELETE"
    if re.search(r'gh\s+repo\s+delete\b', command_str):
        return True, "Destructive 'gh repo delete' repository deletion is prohibited (Rule 40)", "RULE_40_GH_REPO_DELETE"

    # Rule 41: Secret key reading/dumping/exfiltration prevention
    if re.search(r'\.verification_secret\.key\b', command_str):
        read_exfil_cmds = r'\b(?:cat|head|tail|more|less|grep|awk|sed|strings|od|xxd|hexdump|base64|curl|wget|nc|scp|cp|mv|ln|dd)\b'
        if re.search(read_exfil_cmds, command_str) or re.search(r'open\s*\(.*verification_secret', command_str):
            return True, "Direct reading, dumping, or exfiltration of the cryptographic verification secret key is strictly prohibited (Rule 41)", "RULE_41_SECRET_KEY_READ_DENIED"

    # Redirection or pipeline overwrite targeting protected config (B2, B3, B5)
    redir_targets = re.findall(r'(?:>|>>|\|\s*tee\s+(?:-a\s+)?)\s*([^\s;&|]+)', command_str)
    for rt in redir_targets:
        if is_path_protected_config(rt):
            return True, f"Redirection/tee into protected path '{rt}' is prohibited (Rule 38)", "RULE_38_POLICY_TAMPERING"

    # Sed / perl in-place tampering (B4, B8)
    if re.search(r'\b(?:sed|perl)\b.*-(?:i|pi)\b', command_str):
        for token in command_str.split():
            if is_path_protected_config(token):
                return True, f"In-place tampering on protected path '{token}' is prohibited (Rule 38)", "RULE_38_POLICY_TAMPERING"

    # mv targeting protected config (B9)
    if re.search(r'\bmv\s+', command_str):
        for token in command_str.split():
            if is_path_protected_config(token):
                return True, f"Destructive mv targeting protected path '{token}' is prohibited (Rule 6, 14)", "RULE_6_7_14_MV_OVERWRITE"

    # chmod on protected config or .agents (E6)
    if re.search(r'\bchmod\s+', command_str) and ('.agents' in command_str or any(is_path_protected_config(t) for t in command_str.split())):
        return True, "Destructive chmod on protected configuration is prohibited (Rule 15)", "RULE_15_CHMOD_STRIP"

    # Target-specific Deletion & Catastrophic Root Check
    is_bad_rm, rm_reason, rm_rule = check_rm_targets(command_str)
    if is_bad_rm:
        return True, rm_reason, rm_rule

    # Cross-project boundary violation check for command arguments
    if caller_key:
        for other_key, other_roots in PROJECT_BOUNDARIES.items():
            if other_key == caller_key:
                continue
            for other_r in other_roots:
                real_other = os.path.realpath(other_r)
                if other_r in command_str or real_other in command_str:
                    return True, f"Cross-project command violation: Agent [{caller_key}] cannot access [{other_key}] directory: {other_r}", "RULE_79_INTER_AGENT_ISOLATION"

    # SUDO & DELETE OPERATIONS:
    # Explicitly approved by user:
    # 1. Sudo execution is PERMITTED for AGY CLI
    # 2. File and directory deletions within authorized workspace are PERMITTED
    return False, "Operation permitted (delete and sudo approved, within project boundary)", "ALLOW"

def main():
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({"decision": "allow"}))
            return
        payload = json.loads(raw_input)
    except Exception as e:
        err_msg = f"Failed to parse hook payload: {e}"
        print(json.dumps({
            "decision": "deny",
            "reason": f"🛑 [DELETE-GUARD FAIL-CLOSED] {err_msg}"
        }))
        return

    tool_call = payload.get("toolCall", {})
    tool_name = tool_call.get("name", "")
    args = tool_call.get("args", {})

    cwd_arg = args.get("Cwd")
    caller_key, allowed_roots = identify_caller_project(cwd_arg)

    if tool_name == "run_command":
        cmd_line = args.get("CommandLine", "")
        # Check Cwd boundary
        if cwd_arg and caller_key:
            viol, v_msg = check_cross_project_violation(caller_key, allowed_roots, cwd_arg)
            if viol:
                try:
                    inc = log_incident(tool_name, {"Cwd": cwd_arg}, v_msg, "RULE_79_INTER_AGENT_ISOLATION")
                    inc_id = inc.get("incident_id", "UNKNOWN") if isinstance(inc, dict) else "UNKNOWN"
                except Exception:
                    inc_id = "UNKNOWN"
                print(json.dumps({
                    "decision": "deny",
                    "reason": f"🛑 [BOUNDARY-GUARD HARD DENIAL: RULE_79] {v_msg}. Inc-ID: {inc_id}."
                }))
                return

        is_dest, reason, rule_id = inspect_command(cmd_line, caller_key, allowed_roots)
        if is_dest:
            try:
                inc = log_incident(tool_name, {"CommandLine": cmd_line}, reason, rule_id)
                inc_id = inc.get("incident_id", "UNKNOWN") if isinstance(inc, dict) else "UNKNOWN"
            except Exception:
                inc_id = "UNKNOWN"
            print(json.dumps({
                "decision": "deny",
                "reason": f"🛑 [DELETE-GUARD HARD DENIAL: {rule_id}] {reason}. Inc-ID: {inc_id}."
            }))
            return

    elif tool_name in ["write_to_file", "replace_file_content"]:
        target_file = args.get("TargetFile", "")
        if caller_key:
            viol, v_msg = check_cross_project_violation(caller_key, allowed_roots, target_file)
            if viol:
                try:
                    inc = log_incident(tool_name, {"TargetFile": target_file}, v_msg, "RULE_79_INTER_AGENT_ISOLATION")
                    inc_id = inc.get("incident_id", "UNKNOWN") if isinstance(inc, dict) else "UNKNOWN"
                except Exception:
                    inc_id = "UNKNOWN"
                print(json.dumps({
                    "decision": "deny",
                    "reason": f"🛑 [BOUNDARY-GUARD HARD DENIAL: RULE_79] {v_msg}. Inc-ID: {inc_id}."
                }))
                return

        if is_path_protected_config(target_file):
            reason = f"Overwriting/modifying protected governance/hook/verifier target '{target_file}' is strictly prohibited (Rule 38)"
            try:
                inc = log_incident(tool_name, {"TargetFile": target_file}, reason, "RULE_38_POLICY_TAMPERING")
                inc_id = inc.get("incident_id", "UNKNOWN") if isinstance(inc, dict) else "UNKNOWN"
            except Exception:
                inc_id = "UNKNOWN"
            print(json.dumps({
                "decision": "deny",
                "reason": f"🛑 [DELETE-GUARD HARD DENIAL: RULE_38] {reason}. Inc-ID: {inc_id}."
            }))
            return

    elif tool_name == "view_file":
        abs_path = args.get("AbsolutePath", "")
        if caller_key:
            viol, v_msg = check_cross_project_violation(caller_key, allowed_roots, abs_path)
            if viol:
                try:
                    inc = log_incident(tool_name, {"AbsolutePath": abs_path}, v_msg, "RULE_79_INTER_AGENT_ISOLATION")
                    inc_id = inc.get("incident_id", "UNKNOWN") if isinstance(inc, dict) else "UNKNOWN"
                except Exception:
                    inc_id = "UNKNOWN"
                print(json.dumps({
                    "decision": "deny",
                    "reason": f"🛑 [BOUNDARY-GUARD HARD DENIAL: RULE_79] {v_msg}. Inc-ID: {inc_id}."
                }))
                return

    # Default Allow
    print(json.dumps({"decision": "allow"}))

if __name__ == "__main__":
    main()
