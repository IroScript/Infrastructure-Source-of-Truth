---
title: "Steps and Actions"
space: "Framework"
url: "https://docs.frappe.io/framework/automations/steps-and-actions"
updated: "2026-09-30"
---

The **Actions** table on an Automation Flow lists the steps a run executes, top to bottom. Each row has a **Step Type** and, for action steps, an **Action Type** and its **Parameters**.

## Step types


| Step Type        | What it does                                                            |
| ---------------- | ----------------------------------------------------------------------- |
| **Action**       | Runs one action, such as setting a field or sending an email            |
| **Wait**         | Pauses the run for a fixed time, then continues with the next step      |
| **WaitForEvent** | Pauses the run until an app emits a matching event, or a timeout passes |
| **If**           | Evaluates a condition and runs only the steps in the matching branch    |


### Wait

Set **Parameters** to a duration:

```json
{"value": 2, "unit": "Days"}
```

`unit` is one of `Seconds`, `Minutes`, `Hours` or `Days`. While paused, the run shows as **Waiting**. When it resumes, the document is loaded fresh, so later steps see any changes made during the wait.

### WaitForEvent

Pauses until an app emits an event with a matching correlation key:

```json
{
  "event_name": "crm.email_replied",
  "correlation_key": "{{ doc.name }}",
  "timeout_value": 3,
  "timeout_unit": "Days"
}
```

The correlation key is rendered when the step is reached, and the run resumes when the app calls `emit()` with the same event and key. If the timeout passes first, the run resumes anyway. Steps after the wait can read how it ended from `context.event`: `outcome` is `Matched` or `Timed Out`, and `payload` holds the event's data.



A typical use case: send a follow-up only if the customer hasn't replied, by adding an If step after the wait with the condition `context["event"]["outcome"] == "Timed Out"`.

### If

An If step needs a **Step Condition**. Steps that belong to it set **Parent Step** to the If row's number and **Branch** to `If` (runs when the condition is true) or `Else` (runs when it's false). Steps without a Parent Step always run.


| #   | Step Type | Action                                | Parent Step | Branch |
| --- | --------- | ------------------------------------- | ----------- | ------ |
| 1   | If        | condition `doc.grand_total > 10000`   |             |        |
| 2   | Action    | Assign to User: `manager@example.com` | 1           | If     |
| 3   | Action    | Assign to User: `sales@example.com`   | 1           | Else   |
| 4   | Action    | Send Notification                     |             |        |


If Steps can be nested. The branch is decided once, when the run first reaches the If step, and isn't re-evaluated after a Wait.

## Step conditions

Any step can have a **Step Condition**, a Python expression that must be true for the step to run. Otherwise the step is recorded as **Skipped** and the run continues. The expression can read:

- `doc`: the document that triggered the run
- `target`: the record the step acts on
- `context`: the run's state, including `context["steps"]`, the outputs of earlier steps keyed by step key

## Actions

These are the actions shipped as core framework actions. Other Apps can extend this actions via `hooks.py`, see [extending automations](/framework/automations/extending-automations) .


| Action Type               | What it does                                       | Key parameters                                                                              |
| ------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| **Set Field Value**       | Sets one or more fields on the target and saves it | `field` + `value`, or `values` as a map                                                     |
| **Increment Field Value** | Adds a number to a numeric field                   | `field`, `amount` (negative to subtract)                                                    |
| **Create Document**       | Inserts a new document of any type                 | `doctype`, `values`                                                                         |
| **Send Notification**     | Sends an email or a system notification            | `channel` (`Email` or `System`), `recipients`, `subject` and `message`, or `email_template` |
| **Assign to User**        | Assigns the target to one or more users            | `assign_to`, `description`                                                                  |
| **Call Webhook**          | Sends an HTTP request                              | `url`, `method`, `headers`, `payload`, `timeout`                                            |
| **Run Script**            | Runs Python code                                   | `server_script` (an API Server Script), or inline `script`                                  |


### Examples

Set two fields at once:

```json
{"values": {"status": "Replied", "priority": "High"}}
```

Create a follow-up ToDo:

```json
{
  "doctype": "ToDo",
  "values": {
    "description": "Call {{ doc.lead_name }}",
    "reference_type": "{{ doc.doctype }}",
    "reference_name": "{{ doc.name }}",
    "allocated_to": "{{ doc.lead_owner }}"
  }
}
```

Email the document owner and assignees:

```json
{
  "channel": "Email",
  "recipients": ["@owner", "@assignees", "team@example.com"],
  "subject": "{{ doc.name }} was closed",
  "message": "<p>{{ doc.name }} was closed on {{ frappe.utils.nowdate() }}.</p>"
}
```

`@owner` and `@assignees` resolve against the document when the step runs. They read the document as it was loaded at the start of the run (or after the last Wait), so an assignment made by an earlier step in the same run isn't included yet.

## Templates

Text parameters accept Jinja. Available variables:

- `doc` / `target`: the record the step acts on
- `trigger`: the document that started the run
- `payload`: data from a custom event or schedule
- `context`: the run's state, including `context.steps.<step_key>` for earlier steps' outputs

## Acting on other records

By default a step acts on the trigger document. To act on a linked record, declare a named alias under **Relationships** and set the step's **Target** to that alias:

```json
[{"alias": "customer", "relationship": "customer"}]
```

Link, Dynamic Link and child-table link fields are available automatically, under their fieldname. Reverse links are named `<doctype>_via_<field>`, for example `crm_deal_via_lead`. Apps can register more (see [Extending Automations](/framework/automations/extending-automations)).

A **Create Document** step can also set an **Output Alias**. Later steps can then target the document it created.

## Error handling

- **Stop on Error** (on by default): the first failed step stops the run, which is marked **Failed**. Turn it off to keep going; the run is then marked **Partially Failed**.
- Each step runs inside its own savepoint, so a failed step's database changes are rolled back without undoing earlier steps.
- **Call Webhook** and **Run Script** can reach outside the database. Once one of them has run, the run is never replayed from the start, so a webhook isn't sent twice.
- **Call Webhook** refuses private and internal network addresses, and follows at most five redirects. A response status of 400 or above fails the step.
- **Run Script** needs Server Scripts enabled (`bench set-config -g server_script_enabled 1`), and only a System Manager can write an inline script. The script can read `doc`, `target`, `trigger`, `payload` and `context`, and can set keys on `result` to publish output to later steps. It can't call `frappe.db.commit()`.

## Test Run

Click **Test Run** on a saved flow and pick a document. The flow runs for real against it, and then **every change is rolled back**. The result lists each step's status, messages and the condition values it read.

During a test run, Wait steps are simulated, and Call Webhook reports the request it *would* send without sending it.