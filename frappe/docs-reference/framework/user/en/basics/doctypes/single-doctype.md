---
title: "Single DocType\n"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/basics/doctypes/single-doctype"
updated: "2026-02-17"
---


A Single DocType is a DocType that has only one instance in the database. It is useful
for persisting things like *System Settings*, which don't make sense to have multiple
records.

![Single DocType](/files/single-doctype.png)

```python
>>> settings = frappe.get_doc('System Settings')
>>> settings.notification_frequency
'Daily'
```

### Schema

Single DocTypes are stored in the `tabSingles` table in the database, with each property having its own record.

Columns:

- `doctype`
- `field`
- `value`
