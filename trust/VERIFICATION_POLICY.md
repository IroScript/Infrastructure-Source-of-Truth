# VERIFICATION POLICY
**10-Fold Verification Protocol & Independent Verification Architecture**

## 1. The 10 Verification Vectors
1. Static Code Integrity (Syntax, parser, type check)
2. Dynamic Unit & Flow Regression (Substantive test runner)
3. Process Health & Exit Code Fidelity (Exit code 0, clean stderr)
4. Runtime Sockets, Network & Endpoints (ss -tulpn, curl probe)
5. Filesystem & Persistence Ground Truth (Non-zero bytes, mtime)
6. Diff Inspection & Integrity Check (Clean git diff, comment preservation)
7. Idempotency & Stability Re-test (Repeatable outcome)
8. Resource Consumption & System Impact (CPU baseline, memory sanity)
9. Security & Governance Compliance (Safety level compliance, zero privilege escalation)
10. All-or-Nothing Intent Gating (10/10 PASS mandatory; 9/10 = STRICT FAILURE)

## 2. Evidence Role of HMAC-SHA256
HMAC-SHA256 signatures in `verification_state.json` guarantee that verification records produced during a turn have not been tampered with or modified post-run.
However, cryptographic signatures alone do not establish underlying truth: the Source of Truth remains the immutable GitHub repository and live empirical system commands.
