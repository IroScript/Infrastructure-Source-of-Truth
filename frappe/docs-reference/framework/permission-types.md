---
title: "Permission Types"
space: "Framework"
url: "https://docs.frappe.io/framework/permission-types"
updated: "2026-02-17"
---

> Note: This feature is available v16 onwards.

Custom Permission Types let you create permission flags beyond the built-in ones `read`, `write`, `create`, `delete`, `submit`). Use them for action-specific permissions like "approve record", "download file", or "impersonate user".

## How it works

There are three steps:

1. **Developer creates the permission type** in dev mode for a DocType
2. **Developer adds permission checks** in code where the action happens
3. **System Manager assigns the permission to roles** in the Desk UI

The permission type is saved as a fixture and shipped with your app.

## Example: Creating an "approve" permission on Invoice

### Step 1: Create the permission type (Developer)

1. Enable developer mode and log in as Administrator
2. Create a new **Permission Type** record
3. Set **Perm Type** as `approve` and **DocType** as `Invoice`
4. Save

The permission type is now created and will be exported with your app.

### Step 2: Add permission checks in your code (Developer)

In your Invoice controller or in functions that handle approvals, check for the permission:

```python
@frappe.whitelist()
def approve_invoice(invoice_name):
    invoice = frappe.get_doc("Invoice", invoice_name)
    if not frappe.has_permission(invoice, "approve"):
        frappe.throw("Not permitted to approve", frappe.PermissionError)
    invoice.approval_status = "Approved"
    invoice.save()
```

You can also check without throwing an error:

```python
if frappe.has_permission(invoice, "approve"):
    # show approve button on frontend
```

### Step 3: Assign to roles (System Manager)

After your app is installed, system managers assign the permission to roles:

1. Open **Role Permission Manager**
2. Select the Invoice DocType
3. For each role, check or uncheck the "Approve" column, just like other permissions
4. The permission is now applied to all users with that role

That's it. Users with the "approve" permission can now perform the action. Users without it will see an error.

## How to check the permission

Use `frappe.has_permission()` in your Python code:

```python
# Check document-level permission
if frappe.has_permission(invoice_doc, "approve"):
    # User can approve this invoice

# Check DocType-level permission
if frappe.has_permission("Invoice", "approve"):
    # User can approve any invoice
```



