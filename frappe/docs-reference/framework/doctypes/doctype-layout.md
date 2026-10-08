---
title: "DocType Layout"
space: "Framework"
url: "https://docs.frappe.io/framework/doctypes/doctype-layout"
updated: "2026-06-03"
---

# DocType Layout



DocType Layout lets you create multiple form views for the same DocType — each with different field labels, visibility rules, and defaults — **without modifying the DocType itself**. Layouts activate automatically based on document state, so the right view appears with no manual action.

**Common use cases**

- A simplified data-entry view that hides advanced fields
- A read-heavy review view that relabels fields for clarity
- Auto-switching to a "Return" layout when `doc.is_return == 1`
- State- or context-specific layouts driven by conditions or workspace links

## Creating a Layout



Go to the **DocType Layout** list and click **New**.


| Field                      | Description                                                                                                               |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **Title**                  | Display name shown in the layout indicator and breadcrumb (e.g. *Compact View*).                                          |
| **Document Type**          | The DocType this layout applies to. Set once and cannot change.                                                           |
| **Condition**              | Optional JS expression. When truthy, this layout activates automatically on form refresh.                                 |
| **Based On**               | Inherit field configuration from another layout of the same DocType.                                                      |
| **Is Child Table**         | Mark this layout as a child-table layout. When checked, it appears in the Child Layout selector of other DocType Layouts. |
| **Default Print Format**   | Pre-selects this print format when the layout is active.                                                                  |
| **Default Email Template** | Pre-selects this email template when the layout is active.                                                                |


After selecting a **Document Type**, click **Sync Fields** to pull in all fields from the DocType. A visual form builder opens in the **Parent Layout** tab where you can reorder and configure fields.

## Overriding Field Properties



In the form builder, select any field to override its properties. The following properties can be set **per layout** without affecting the base DocType:


| Property               | Effect                                        |
| ---------------------- | --------------------------------------------- |
| `label`                | Rename the field for this layout              |
| `hidden`               | Hide the field                                |
| `reqd`                 | Make the field mandatory                      |
| `read_only`            | Make the field read-only                      |
| `bold`                 | Emphasize the label                           |
| `allow_in_quick_entry` | Include the field in the Quick Entry dialog   |
| `in_list_view`         | Show the field as a column in the List View   |
| `in_standard_filter`   | Include the field in the Standard Filters bar |
| `default`              | Set a default value for new documents         |
| `description`          | Override the help text                        |
| `depends_on`           | Conditional visibility expression             |
| `mandatory_depends_on` | Conditional required expression               |
| `read_only_depends_on` | Conditional read-only expression              |


Properties not set in the layout fall back to the base DocType definition.

## Automatic Layout Switching



Layout selection is **entirely condition-driven** — there is no manual switcher. Set a **Condition** to make a layout activate automatically when the expression evaluates to truthy after a form refresh:

```
// Activates for return transactions
doc.is_return == 1

// Activates for high-value orders
doc.grand_total > 100000

// Activates for a specific status
doc.status === "Closed"
```

When a condition matches, the layout is applied and the URL is updated with `?layout=<name>`. The first matching layout wins; layouts are evaluated in the order they appear in the list. A layout indicator badge appears next to the document title whenever a non-default layout is active.

## Breadcrumb Navigation



When a layout is active, the breadcrumb bar reflects it:

- On the **form view**, the layout title appears as a clickable crumb between the DocType and the document name. Clicking it opens the list **filtered by the layout's condition** (parsed from `doc.field OP value` expressions).
- On that **filtered list**, the layout title appears as a non-clickable crumb so the active context stays visible.
- Clicking the **DocType crumb** while a layout is active clears all filters and removes the layout crumb, returning to the unfiltered list.

## Child Table Layouts



A layout can specify different layouts for its child tables. In the **Child Layouts** tab, add a row for each child table you want to customize:


| Field               | Description                                                            |
| ------------------- | ---------------------------------------------------------------------- |
| **Table Fieldname** | The fieldname of the child table in the parent DocType                 |
| **Child Layout**    | A DocType Layout whose Document Type matches the child table's DocType |


When the parent layout is active, each child table grid automatically renders using its assigned child layout — applying the same field-level overrides as a parent layout would.

**Important.** The child layout's **Document Type** must match the child table's DocType (e.g. `Sales Invoice Item`), not the parent DocType. Create a separate layout for the child table first, then reference it here.

The same field properties available on a parent layout — `label`, `hidden`, `reqd`, `read_only`, `depends_on`, column order, and so on — apply inside the grid when the child layout is active.

**Example.** A *Finance View* parent layout maps the items table to a *Compact Items* child layout that hides `description`, `uom`, and other detail columns, leaving only `item_code`, `qty`, and `amount` visible. Switching to the parent layout automatically compacts the grid — no extra action required from the user.

## Layout Inheritance



Use **Based On** to inherit the field configuration of another layout for the same DocType. The child layout starts with the parent's field order and overrides, and can further customize individual fields or add new ones.

This is useful for creating a family of related layouts: define a *Base Layout* with common field order, then create specialized layouts (e.g. *Sales View*, *Finance View*) that inherit and tweak it.

## Keeping Fields in Sync



The **Sync Fields** button compares the layout's field list against the current DocType definition and reports:

- **Added** — fields present in the DocType but missing from the layout (added to the end)
- **Removed** — fields in the layout that no longer exist in the DocType (removed)

Run this after modifying the underlying DocType to keep the layout consistent.

## Workspace Integration



Any DocType link in the sidebar workspace can be tied to a specific layout. Open the workspace in edit mode, select a DocType link, and set the **DocType Layout** field to the layout you want. Clicking that link opens the list pre-scoped to that layout (the URL carries `?layout=<name>`), and new documents created from the list open under that layout.

## For Developers: Standard Layouts



Layouts can be shipped as part of an app by setting **Is Standard** and selecting a **Module**. In developer mode, saving a standard layout automatically exports it as a JSON file to:

{app}/{module}/doctype/{doctype}/doctype_layout/{layout_name}.json

This file is included in migrations and deployed automatically via `bench migrate`. Standard layouts are **read-only** on production instances (outside developer mode).