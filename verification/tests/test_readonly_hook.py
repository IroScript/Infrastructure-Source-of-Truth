"""Verification of real installed PreToolUse hook enforcing TASK_MODE=READ_ONLY."""
import json
import os
import subprocess
from pathlib import Path

def test_installed_delete_guard_read_only_enforcement():
    hook_path = Path("/home/azureuser/.agents/hooks/delete_guard.py")
    assert hook_path.is_file(), f"Installed hook missing: {hook_path}"

    test_cases = [
        # (tool_name, args, expected_decision)
        ("write_to_file", {"TargetFile": "/tmp/test.txt", "CodeContent": "hello"}, "deny"),
        ("replace_file_content", {"TargetFile": "/tmp/test.txt"}, "deny"),
        ("run_command", {"CommandLine": 'git commit -m "foo"'}, "deny"),
        ("run_command", {"CommandLine": "git push origin main"}, "deny"),
        ("run_command", {"CommandLine": 'tmux send-keys -t agy:0 "ls" Enter'}, "deny"),
        ("run_command", {"CommandLine": "systemctl restart agy-agents.service"}, "deny"),
        ("run_command", {"CommandLine": "pkill -9 node"}, "deny"),
        ("run_command", {"CommandLine": 'echo "hello" > /tmp/foo.txt'}, "deny"),
        ("run_command", {"CommandLine": "git status"}, "allow"),
        ("run_command", {"CommandLine": "cat /etc/hosts"}, "allow"),
        ("run_command", {"CommandLine": "tmux capture-pane -p -t agy:0"}, "allow"),
        ("run_command", {"CommandLine": "ps aux"}, "allow"),
        ("run_command", {"CommandLine": 'sqlite3 /tmp/test.db "SELECT * FROM foo;"'}, "allow"),
        ("run_command", {"CommandLine": 'sqlite3 /tmp/test.db "INSERT INTO foo VALUES (1);"'}, "deny"),
    ]

    env = dict(os.environ)
    env["TASK_MODE"] = "READ_ONLY"

    for tool_name, args, expected in test_cases:
        payload = json.dumps({"toolCall": {"name": tool_name, "args": args}})
        p = subprocess.run(["python3", str(hook_path)], input=payload, text=True, capture_output=True, env=env)
        assert p.returncode == 0
        res = json.loads(p.stdout.strip())
        assert res.get("decision") == expected, f"Failed for {tool_name} {args}: got {res}"
        if expected == "deny":
            assert "POLICY_VIOLATION_READ_ONLY" in res.get("reason", "")
