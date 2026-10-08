---
title: "Extending Automations"
space: "Framework"
url: "https://docs.frappe.io/framework/automations/extending-automations"
updated: "2026-09-30"
---

Apps can extend Automation Flows in three ways: **emit events** that flows trigger on or wait for, **add actions** to the step list, and **add relationships** so steps can reach records the schema doesn't link directly. Each one is registered in your app's `hooks.py`.

## Emitting events

Call `emit()` wherever something meaningful happens in your app:

```python
from frappe.automation_engine import emit

def on_deal_won(deal):
    emit("crm.deal_won", doc=deal, payload={"amount": deal.deal_value})
```


| Argument          | Description                                                                                               |
| ----------------- | --------------------------------------------------------------------------------------------------------- |
| `event`           | Event name. Use an app-prefixed, dotted name like `crm.deal_won`.                                         |
| `doc`             | The document the event is about. Custom Event flows with a Document Type run against it.                  |
| `payload`         | A JSON-serializable dict. Flows read it as `payload` in templates and `context["payload"]` in conditions. |
| `correlation_key` | Resumes runs paused at a matching **WaitForEvent** step.                                                  |


`emit()` does two things:

1. It queues every enabled **Custom Event** flow for *that* event.
2. If `correlation_key` is given, it resumes any run waiting for that event with the same key.

It returns `{"queued": <count>, "resumed": <count>}`. Runs start after the current transaction commits, and calling `emit()` twice for the same record before then produces a single run. Payloads larger than the **Event Payload Limit** in Automation Settings (64 KB by default) are rejected.

### Resuming a waiting flow

A flow can send an email, then **WaitForEvent** `crm.email_replied` with the correlation key `{{ doc.name }}`. When the reply arrives, your app emits the same event with the same key:

```python
emit(
    "crm.email_replied",
    doc=lead,
    payload={"communication": comm.name},
    correlation_key=lead.name,
)
```

The waiting run resumes immediately, and its later steps can read the payload from `context["event"]["payload"]`.

### Registering events

`emit()` only accepts events an installed app has registered, unless **Allow Unregistered Events** is on in Automation Settings. Register events in `hooks.py`, either as bare names or with metadata that builder UIs can show:

```python
automation_events = [
    "crm.deal_won",
    {
        "crm.email_replied": {
            "label": "Email replied",
            "description": "A contact replied to an email sent from CRM",
            "subject": {"doctype_key": "reference_doctype", "name_key": "reference_name", "doctypes": ["CRM Lead", "CRM Deal"]},
        }
    },
]
```

`subject` tells the engine which record an event is *about*, read from the payload. With a subject, a flow on `CRM Lead` runs against the lead named in the payload even if the code that emitted the event was holding a Communication. Use `"doctype": "CRM Lead"` in place of `doctype_key` when the subject type is fixed.

## Adding actions

Subclass `AutomationAction` and implement `execute`:

```python
# my_app/automation.py
from typing import ClassVar

import frappe
from frappe.automation_engine.actions.base import AutomationAction, AutomationParamError, render_value


class PostToChannel(AutomationAction):
    action_type = "PostToChannel"
    label = "Post to Channel"
    description = "Post a message to a team channel."
    transactional = False  # it calls an external service
    params_schema: ClassVar[list] = [
        {"fieldname": "channel", "label": "Channel", "fieldtype": "Data", "reqd": 1},
        {"fieldname": "message", "label": "Message", "fieldtype": "Small Text", "reqd": 1},
    ]

    def validate(self, params, doctype):
        if not params.get("channel"):
            raise AutomationParamError("Channel is required", fieldname="channel")

    def execute(self, doc, params, context):
        message = render_value(params["message"], doc, context)
        post_message(params["channel"], message)
        return f"Posted to {params['channel']}"
```

```python
# hooks.py
automation_actions = ["my_app.automation.PostToChannel"]
```

Class attributes:


| Attribute                 | Purpose                                                                                                                                                        |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `action_type`             | Unique identifier stored on the step. Don't change it after release.                                                                                           |
| `label`, `description`    | Shown in the Action Type list and in builder UIs.                                                                                                              |
| `params_schema`           | Parameter fields: `fieldname`, `label`, `fieldtype`, `options`, `reqd`.                                                                                        |
| `requires_document`       | Set to `False` if the action can run without a trigger document, for example on a Scheduled flow.                                                              |
| `applicable_doctypes`     | Limits the action to these DocTypes. `None` means all.                                                                                                         |
| `supported_trigger_types` | Limits the action to these trigger types. `None` means all.                                                                                                    |
| `transactional`           | Set to `False` if the action has effects a database rollback can't undo, such as HTTP calls or messages. The engine then never replays the run from the start. |


Methods:

- `validate(params, doctype)`: runs when the flow is saved and again before each execution. Raise `AutomationParamError` with a `fieldname` to point at the bad parameter.
- `execute(doc, params, context)`: does the work. Return a short string for the run log, or a dict with a `detail` key plus any output later steps should read through `context["steps"][step_key]`.
- `output_doctype(params)`: if the action creates a record, return its DocType. A step's **Output Alias** can then target the new record, and later steps are validated against it.

The action runs as the flow's **Run As** user, so normal permission checks apply. Don't call `frappe.db.commit()`; the engine owns the transaction. To pause the run from inside an action, raise `StopAutomation("reason", resume_after=seconds)`.

## Adding relationships

Link, Dynamic Link and child-table link fields become relationships automatically, in both directions. Register a provider only for connections the schema doesn't express, such as a record matched on an email address:

```python
from frappe.automation_engine.relationships import AutomationRelationshipProvider


class ContactRelationships(AutomationRelationshipProvider):
    def get_definitions(self, source_doctype):
        if source_doctype != "Communication":
            return []
        return [{
            "name": "sender_lead",
            "label": "Lead (by sender email)",
            "target_doctype": "CRM Lead",
            "cardinality": "one",
        }]

    def resolve(self, source_doc, relationship, params):
        name = frappe.db.get_value("CRM Lead", {"email": source_doc.sender})
        return [{"doctype": "CRM Lead", "name": name}] if name else []
```

```python
# hooks.py
automation_relationships = ["my_app.automation.ContactRelationships"]
automation_relationship_ignore = ["My Log DocType"]
```

- `cardinality` is `one` or `many`. Only `one` relationships can be used as a step's target alias. `many` relationships are for related-record conditions, where overriding `query()` to filter in SQL keeps them fast on large tables.
- A definition with the same `name` as a derived relationship replaces it, which lets an app relabel a schema link.
- Every reference a provider returns is checked for existence and read permission before a step uses it.
- `automation_relationship_ignore` hides DocTypes (such as logs) from derived relationships.

## Suppressing and checking automations

```python
from frappe.automation_engine import is_enabled, skip_automations

if is_enabled():
    ...

with skip_automations():
    doc.save()  # no Automation Flow fires for this save
```