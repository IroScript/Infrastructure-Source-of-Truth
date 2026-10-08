---
title: "Docstatus or Document Status"
space: "Framework"
url: "https://docs.frappe.io/framework/doctypes/docstatus"
updated: "2026-07-05"
---

Frappe uses the concept of a "Docstatus" to keep track of the status of transactions. The docstatus will always have one of the following three values:

1. Draft (value: 0)
2. Submitted (value: 1)
3. Cancelled (value: 2)

Documents that are _not submittable_ will always remain in the "draft" state. Documents that are _submittable_ can optionally proceed from the draft state to the "submitted", and then to the "cancelled" state.

Documents in the submitted and cancelled state cannot be edited, with one execption: for individual fields we can explicitly allow edits, even when the document is in the submitted state.

In the backend code we have a helper class `DocStatus` that can be used as follows:

```py
import frappe
from frappe.model.docstatus import DocStatus

draft_invoice_names = frappe.get_list(
 "Sales Invoice",
 filters={"docstatus": DocStatus.draft()},
 pluck="name"
)

invoice_doc = frappe.get_doc("Sales Invoice", draft_invoice_names[0])
invoice_doc.docstatus == DocStatus.draft() # -> True
invoice_doc.docstatus.is_draft() # -> True
invoice_doc.docstatus.is_submitted() # -> False
invoice_doc.docstatus.is_cancelled() # -> False

invoice_doc.submit()
invoice_doc.docstatus == DocStatus.submitted() # -> True
invoice_doc.docstatus.is_draft() # -> False
invoice_doc.docstatus.is_submitted() # -> True
invoice_doc.docstatus.is_cancelled() # -> False

invoice_doc.cancel()
invoice_doc.docstatus == DocStatus.cancelled() # -> True
invoice_doc.docstatus.is_draft() # -> False
invoice_doc.docstatus.is_submitted() # -> False
invoice_doc.docstatus.is_cancelled() # -> True
```

The docstatus gets stored as an integer value in each Doctype table of the database.