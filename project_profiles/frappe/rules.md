# FRAPPE & ERPNEXT OFFICIAL-SOURCE CODING RULES

## RULE 1: MODEL TRAINING KNOWLEDGE IS NOT AUTHORITATIVE
Coding agents (AGY, Codex, Claude, Qwen, etc.) MUST NEVER justify a Frappe-specific implementation with:
"I know Frappe works this way" or "In Frappe it is standard to...".
Every framework-specific API, hook, DocType behavior, ORM method, whitelisted endpoint, and permission pattern requires verifiable evidence from the matching official reference (`docs.frappe.io` or `frappe/frappe` branch `version-16`).

## RULE 2: OFFICIAL EVIDENCE HIERARCHY
1. Exact-version/current-major official documentation (`docs.frappe.io`)
2. Official source code for the matching branch/tag (`frappe/frappe` version-16, `frappe/erpnext` version-16)
3. Official unit tests and examples in the matching upstream source
4. Official migration notes and release notes
If documentation has a gap, the agent must verify directly against the matching branch source. Self-invention is prohibited.

## RULE 3: CORE FRAMEWORK MODIFICATION PROHIBITION
Custom business logic and features MUST reside in custom apps (`apps/alco_ecommerce`).
Direct modification of upstream `apps/frappe` or `apps/erpnext` is strictly prohibited. Any accidental edit to core files will trigger `CORE_MODIFICATION_PROHIBITED` and block task completion.

## RULE 4: PROHIBITED OUTDATED PATTERNS
The following patterns are forbidden and will be rejected with `OUTDATED_FRAPPE_PATTERN`:
- Raw SQL string concatenation or f-strings in `frappe.db.sql` (use `frappe.qb` or parameterized dict/tuple).
- `@frappe.whitelist()` without explicit `methods=["GET"]` or `methods=["POST"]`.
- Direct `ALTER TABLE` DDL queries (use DocType JSON schema or Custom Field fixtures).
- Explicit `frappe.db.commit()` inside read/GET queries.
- Imports from removed or deprecated modules.

## RULE 5: MACHINE-READABLE EVIDENCE
Every Frappe-specific coding task must produce a machine-readable evidence bundle recording:
task_id, project_uuid, frappe_version, erpnext_version, official_reference_commit, official_docs_consulted, apis_hooks_used, changed_files, tests_run, negative_tests, and verdict.
Chain-of-thought is excluded.
