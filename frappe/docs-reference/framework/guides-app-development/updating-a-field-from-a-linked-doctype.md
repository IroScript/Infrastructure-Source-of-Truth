---
title: "Updating a Field from a Linked Doctype"
space: "Framework"
url: "https://docs.frappe.io/framework/guides-app-development/updating-a-field-from-a-linked-doctype"
updated: "2026-07-05"
---

ERPNext lets you fetch a value from a linked document into another field by using the **Fetch From** property. This is useful when one field should automatically show information from a selected linked record.

For example, when a user selects a **Customer**, you may want to automatically show the customer's territory, tax ID, customer group, or another field from the Customer master. Instead of writing a Client Script, you can configure this using **Fetch From** in the field settings.



[https://www.youtube.com/watch?v=78Yp_OdXnBI](https://www.youtube.com/watch?v=78Yp_OdXnBI)

## How Fetch From Works

Fetch From works with a **Link** field.

The format is:

```text
link_fieldname.field_to_fetch
```

Where:

- `link_fieldname` is the fieldname of the Link field in the current DocType.
- `field_to_fetch` is the fieldname from the linked DocType.

When the user selects a value in the Link field, ERPNext reads the selected linked document and copies the specified field value into the current field.

## Example

Suppose you have a custom field on **Sales Order** called **Customer Territory**, and you want it to automatically fetch the territory from the selected Customer.

In this case:

- The Link field on Sales Order is `customer`.
- The field to fetch from Customer is `territory`.
- The Fetch From value should be:

```text
customer.territory
```

When a user selects a Customer in the Sales Order, ERPNext fetches the Customer's Territory and fills it in the Customer Territory field.

## Steps To Configure Fetch From

1. Go to **Customize Form**.
2. Select the DocType where you want to show the fetched value.
3. Add or select the target field where the fetched value should appear.
4. In the field settings, enter the **Fetch From** value using this format:

```text
link_fieldname.field_to_fetch
```

5. Save the customization.
6. Reload the form and test by selecting a linked document.

## Another Example

If you want to fetch the **Supplier Group** from the selected Supplier into a custom field on Purchase Order:

- Link field: `supplier`
- Field to fetch: `supplier_group`
- Fetch From value:

```text
supplier.supplier_group
```

When the Supplier is selected, ERPNext fetches the Supplier Group into the target field.

## Important Notes

- Fetch From works only when the source field is available on the linked DocType.
- Use the **fieldname**, not the field label. For example, use `customer_group`, not `Customer Group`.
- The target field should have a compatible field type. For example, fetch text into a Data field, dates into a Date field, and linked records into a Link field where appropriate.
- Fetch From is best for simple one-way fetching. If the value needs complex conditions, calculations, or multiple dependent updates, use a Client Script instead.
- If the value in the linked document changes later, existing documents may not update automatically unless the link field is changed or the document is refreshed and saved according to the form behavior.

## Common Mistakes

- **Using the label instead of fieldname:** `customer.Customer Group` will not work. Use `customer.customer_group`.
- **Using the wrong link field:** The first part must be the fieldname of the Link field on the current form.
- **Fetching from a field that does not exist:** Check the linked DocType to confirm the exact fieldname.
- **Expecting complex logic:** Fetch From copies a value. It is not a replacement for business logic or validation.

## When To Use Fetch From

Use Fetch From when:

- A field should show a value from a selected Customer, Supplier, Item, Employee, Project, or another linked record.
- The value is informational and follows the selected linked document.
- You want a no-code configuration instead of a Client Script.
- The fetching rule is simple and does not require conditions or calculations.

## Related Topics

- [Customize Form](https://docs.frappe.io/erpnext/customize-form)
- [Custom Field](https://docs.frappe.io/erpnext/custom-field)
- [Client Script](https://docs.frappe.io/erpnext/customization/custom-scripts)
- [DocType](https://docs.frappe.io/framework/user/en/basics/doctypes)
- [Link Field](https://docs.frappe.io/framework/user/en/basics/doctypes/fieldtypes)