---
title: "Event Streaming"
space: "Framework"
url: "https://docs.frappe.io/framework/help/event-streaming"
updated: "2026-07-04"
---

Event Streaming was a Frappe feature used to publish document changes from one Frappe site and consume them on another site. It was useful when selected DocTypes needed to be synchronized between sites without building a separate integration for every record type.

## How Event Streaming Worked

In a typical setup, one site acted as the **Event Producer** and another site acted as the **Event Consumer**. When selected documents were created or updated on the producer site, events were recorded and then consumed by the other site. This made it possible to replicate masters, transactions, or custom DocTypes across Frappe sites.

## Status In Version 15 And Later

Event Streaming is not supported as a maintained core feature from Frappe/ERPNext version 15 onward. In Frappe version 14, Event Streaming existed inside the framework source under `frappe/event_streaming`. In version 15, Frappe added a removal patch for the Event Streaming module and its DocTypes, including Event Producer, Event Consumer, Event Update Log, and related mapping DocTypes.

## Separate App

The feature was separated into its own app: [frappe/event_streaming](https://github.com/frappe/event_streaming). However, the app is not actively maintained. The GitHub repository was archived by Frappe on December 6, 2024, is now read-only, and has no published releases. Treat it as unsupported for new production implementations unless your team is ready to test and maintain it independently.

## Recommended Alternatives

- **REST API:** Use Frappe's REST API for explicit integrations between ERPNext and other systems.
- **Webhooks:** Use webhooks when another system should be notified after a document is created or updated.
- **Background Jobs:** Use scheduled or queued jobs for sync logic that needs retries, logs, and error handling.
- **Custom Integration Apps:** Build a custom app when data mapping, conflict handling, or business rules need to be controlled carefully.

## When To Be Careful

Avoid planning new implementations around Event Streaming on version 15 or later. For current ERPNext integrations, prefer APIs, webhooks, and integration-specific queues so ownership, retry behavior, and failure handling are clear.

## Related Topics

- [frappe/event_streaming on GitHub](https://github.com/frappe/event_streaming)
- [Frappe version 15 Event Streaming removal patch](https://github.com/frappe/frappe/blob/version-15/frappe/patches/v15_0/remove_event_streaming.py)
- [Frappe REST API](https://docs.frappe.io/framework/user/en/api/rest)
- [Webhooks](https://docs.frappe.io/framework/user/en/guides/integration/webhooks)
- [Background Jobs](https://docs.frappe.io/framework/user/en/api/background_jobs)