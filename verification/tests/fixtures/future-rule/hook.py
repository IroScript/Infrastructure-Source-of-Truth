#!/usr/bin/env python3
import json
import sys

config = json.load(open(sys.argv[1], encoding="utf-8"))
action = sys.argv[2]
if action == "activation":
    print("loaded")
    raise SystemExit(0)
if action == config["allowed_action"]:
    print("allowed")
    raise SystemExit(0)
if action == config["denied_action"]:
    print("blocked", file=sys.stderr)
    raise SystemExit(3)
print("unknown action", file=sys.stderr)
raise SystemExit(4)
