# FAIL-CLOSED OPERATIONAL POLICY
**Default Security and Verification Posture for AGY CLI**

When an AGY agent encounters an unexpected condition, broken pipeline, or missing component, the system MUST fail closed:

1. **Missing Verifier:** If `verify_10_fold.py` is absent or unexecutable, the Stop Hook terminates turn completion and returns `decision: continue` with an explicit failure reason.
2. **Replayed Nonce:** Single-use cryptographic nonces prevent replay attacks. A consumed nonce triggers an immediate termination block.
3. **Missing Policy File:** If any file listed in `trust/TRUST_BASELINE.json` is missing or fails its SHA-256 integrity check, `verify_trust_baseline.sh` exits with code 1 and outputs `AGY TRUST BASELINE: FAIL`.
4. **Premature Done:** Any textual claim of task completion without an active signed verification state generated in the preceding 120 seconds is intercepted and rejected by `completion_gate_stop_hook.py`.
