---
title: "Automations"
space: "Framework"
url: "https://docs.frappe.io/framework/automations"
updated: "2026-09-30"
---

An **Automation Flow** says "when this happens to this kind of record, do these things in order", without writing code. You pick a trigger, narrow it with conditions, and add a list of steps: update a field, send a notification, assign someone, call a webhook, wait two days, branch on a value.

:::note
Automation Flow is in **beta**. The configuration described here is stable but the run log and internals may change in upcoming releases.
:::

## When to use an Automation Flow

Frappe already has single-purpose tools for common jobs and they remain the right choice when one of them does exactly what you need:


| You want to…                                      | Use                                                              |
| ------------------------------------------------- | ---------------------------------------------------------------- |
| Send one email or system notification on an event | [Notification](/framework/notifications)                         |
| Post a document to an external URL on an event    | [Webhook](/framework/user/en/guides/integration/webhooks)        |
| Distribute new documents across a team            | Assignment Rule                                                  |
| Change a document's behaviour in code             | [Server Script](/framework/user/en/desk/scripting/server-script) |


Use an Automation Flow when you need what those tools can't do on their own:

- **Several steps in order**: assign the document, then email the assignee, then create a follow-up task.
- **Waiting**: do something, wait two days, then do something else, or wait until another event happens.
- **Branching**: if the deal is over 10,000 do one thing, otherwise do another.
- **Reaching linked records**: the trigger is a Communication, but the record you want to update is the Lead it belongs to.

## How it works

1. **Trigger**: a document event, a date, a schedule, a custom event from an app, or a manual run starts the flow. See [Triggers and Conditions](/framework/automations/triggers-and-conditions).
2. **Match**: the flow's match fields and condition decide whether this document qualifies.
3. **Queue**: a matching trigger is queued, not executed inline. A background worker picks it up shortly after the request commits, so a slow webhook never blocks a user's save. Repeated saves of the same document before the worker runs collapse into a single run.
4. **Run**: the worker executes the steps in order and writes an **Automation Run** record with the outcome of every step. See [Steps and Actions](/framework/automations/steps-and-actions).

Because runs happen in the background, the **scheduler and background workers must be running** for automations to fire.



:::note
Only a **System Manager** can create, edit or read Automation Flows.
:::

## Creating a flow

1. Go to **Automation Flow** in the awesome bar and click **New**.
2. Enter a **Title** and choose the **Document Type** the flow is about.
3. Choose a **Trigger Type** and fill in the fields it asks for.
4. Optionally add **Match Fields** and an **Advanced Expression using Python**.
5. Add one or more rows under **Actions**.
6. Save and click **Test Run** to try it against a real document (all changes are rolled back), then check **Enabled** and save again.

A flow can only be enabled once it has at least one action.

### Example: follow up on high-value leads

- **Document Type**: Lead
- **Trigger Type**: Doc Created
- **Match Fields**: *Annual Revenue* &gt; 1,000,000
- **Actions**:
  1. **Assign to User**: `sales-head@example.com`
  2. **Send Notification**: Email to `sales-head@example.com`, subject `New lead: {{ doc.lead_name }}`
  3. **Wait**: 2 Days
  4. **Send Notification**: Email to `@assignees`, subject `Follow up on {{ doc.lead_name }}`, with a step condition `doc.status == "Lead"` so it is skipped if someone has already moved the lead on.

## Run history

Every run is saved as an **Automation Run** which is linked to the flow and to the document it ran against. Each run has a status:

- **Success**: every step succeeded or was skipped.
- **Partially Failed**: a step failed and *Stop on Error* was off, so later steps still ran.
- **Failed**: a step failed and `Stop on Error` stopped the run or the run couldn't start.
- **Waiting**: the run is paused at a `Wait step` and resumes on its own.
- **Skipped**: the document was deleted or no longer matched when `Revalidate on Run` is on.

Open a run to see each step's status, its output, how long it took, and, for a failed step, the error message and traceback. For a skipped step, the run shows the condition and the values it read, so you can see *why* it didn't match. Run logs are cleared after 30 days by the standard log cleanup.

## Automation Settings

**Automation Settings** holds the site-wide switches and limits:

- **Disable Automations**: stop dispatching all flows on the site. Rows already queued are not affected. To stop automations even when the database is unreachable, set `"automation_disabled": 1` in `site_config.json`.
- **Maximum Recursion Depth** (default 3): how many times a flow's actions may trigger another flow before the chain is refused. This stops two flows that update each other from looping forever.
- **Failure Threshold** (default 10): after this many consecutive failed runs, the flow is **disabled automatically** and its pending runs are skipped and its owner gets a notification. The reason is shown in the flow's *Disabled Reason* field.
- **Allow Unregistered Events**: accept custom events that no installed app has registered. See [Extending Automations](/framework/automations/extending-automations).

The remaining settings (drain timing, retries, retention and size limits) tune the background worker and rarely need changing.

## Next steps

- [Triggers and Conditions](/framework/automations/triggers-and-conditions)
- [Steps and Actions](/framework/automations/steps-and-actions)
- [Extending Automations](/framework/automations/extending-automations), for app developers