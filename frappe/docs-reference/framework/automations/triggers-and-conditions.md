---
title: "Triggers and Conditions"
space: "Framework"
url: "https://docs.frappe.io/framework/automations/triggers-and-conditions"
updated: "2026-09-30"
---

The trigger decides **when** an Automation Flow is considered. The match fields and condition decide **whether** a particular document qualifies. Both are set on the Automation Flow form.

## Trigger types

| Trigger Type | Fires when | Needs |
| --- | --- | --- |
| **Doc Created** | A document is inserted | Document Type |
| **Doc Updated** | An existing document is saved (not on insert) | Document Type |
| **Field Value Changed** | One field changes value on save | Document Type, Trigger Field |
| **Doc Deleted** | A document is deleted | Document Type |
| **Doc Submitted** | A submittable document is submitted | Document Type |
| **Doc Cancelled** | A submittable document is cancelled | Document Type |
| **Date Based** | A date field is N days before or after today | Document Type, Date Field |
| **Scheduled** | A cron expression comes due | Cron Expression |
| **Custom Event** | An app calls `frappe.automation_engine.emit()` | Custom Event name |
| **Manual** | Someone starts the flow explicitly | — |

### Field Value Changed

Set **Trigger Field** to the field to watch. Optionally narrow it with:

- **From Value**: fire only when the old value was this.
- **To Value**: fire only when the new value is this.

Leave either empty to accept any value. For example, *Trigger Field* `status`, *To Value* `Closed` fires whenever a document is closed, whatever its previous status was.

### Date Based

Pick a **Date Field**, a **Date Offset (Days)** and a **Date Direction**:

- `3` days **Before** `renewal_date`: fires on documents whose renewal is three days from today.
- `1` day **After** `due_date`: fires on documents that became overdue yesterday.

Date Based flows are checked **hourly**. Each document fires at most once per day, however many times the check runs.

### Scheduled

Enter a standard five-field **Cron Expression**, for example `0 9 * * 1` for 09:00 every Monday. The form shows the **Next Run** time after you save.

- **Without a Document Type**, the flow runs once per schedule, with no document. Use this for periodic jobs such as a weekly digest email or calling an external API.
- **With a Document Type**, the flow runs once for **every document that matches** its match fields and condition, each time the schedule comes due.

If the scheduler was down and missed several fires, the flow catches up once for the latest one, not once for every fire it missed.

### Custom Event

Custom Event flows run when an app emits a named event, such as `crm.deal_won`. Enter the event name exactly as the app emits it in **Custom Event**. How an app emits and registers events is covered in [Extending Automations](/framework/automations/extending-automations).

If a Document Type is set, the flow only runs for events about a document of that type.

### Manual

A Manual flow never fires on its own. It runs only when an app starts it through the `frappe.automation_engine.api.run_manually` method, for example from a button in the app's UI. The caller needs write access to the flow and read access to the document.

## Match fields

**Match Fields** use the same filter editor as the list view. Add a row per field rule. The document must satisfy every rule for the flow to run.

For example, on a Lead flow:

- *Status* = `Open`
- *Source* is set
- *Annual Revenue* > `1000000`

A flow with no match fields matches every document of its type.

## Advanced condition

For logic the match fields can't express, write a Python expression in **Advanced Expression using Python**. The document is available as `doc`, and the expression is evaluated with Frappe's safe evaluator, so `frappe.utils` helpers are available.

```python
doc.status == "Open" or doc.priority == "High"
```

```python
doc.grand_total > 50000 and doc.customer_group != "Internal"
```

The match fields **and** the expression must both be true. If the expression raises an error, the document is treated as not matching and the error is written to the Error Log.

## Revalidate on Run

A trigger is matched when the document is saved, but the steps run a moment later in a background worker. Check **Revalidate on Run** to test the match fields and condition again right before executing. If the document no longer matches, the run is recorded as **Skipped**.

This is useful when a document can change quickly after the save that triggered the flow, for example a status that is set and then reverted.

## Run As

**Run As** decides whose permissions the steps run with:

- **Automation User** (default): the user in the **Automation User** field, `Administrator` unless you change it.
- **Triggering User**: the user whose action triggered the flow.
- **Document Owner**: the owner of the document the flow runs against.

Every step still runs normal permission checks as that user. If a step fails with a permission error, check whether the Run As user can read the trigger document and write the record the step changes.

:::note
Set **Automation User** to a dedicated user with only the roles the flow needs, rather than leaving it as `Administrator`.
:::

## When flows do not fire

Automation Flows are skipped during installs, migrations and patches, while **Disable Automations** is checked in Automation Settings, and when `automation_disabled` is set in `site_config.json`.

Code that must save documents without triggering flows, such as a data import, can suppress them:

```python
from frappe.automation_engine import skip_automations

with skip_automations():
    doc.save()
```