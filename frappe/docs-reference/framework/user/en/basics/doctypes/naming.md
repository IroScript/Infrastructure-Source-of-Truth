---
title: "Naming\n"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/basics/doctypes/naming"
updated: "2026-04-14"
---

All DocTypes in Frappe have a primary key called `name`. This is the unique ID by which you find records and manipulate them using the ORM.

## Naming Methods

You can configure how documents should be named when a new document is created. There are 9 ways of naming provided in the framework:

1. Set by user
2. Autoincrement
3. By fieldname
4. By "Naming Series" field
5. Expression
6. Expression (Old Style)
7. Random
8. UUID
9. By script

### 1. Set by user

The document name is entered manually by the user at the time of creation.

### 2. Autoincrement

The system generates a sequential numeric name by incrementing the last created document.

**Key considerations:**

- Numbering starts from 1.
- **Not gap-safe:** Deleted records are not reused. For example, if you have documents named `1`, `2`, `3`, `4` and you delete `3`, the next document will be named `5`, not `3`.
- You cannot switch to a different naming schema once this is set unless the DocType has zero documents.
- You cannot switch to this naming schema from another unless the DocType has zero documents.

![](/files/autoincrement.gif)
*Autoincrement*

### 3. By fieldname

The document name is fetched directly from the value of a specific field.

> **Note:** The value in the selected field must always be unique.

![](/files/fieldname.gif)
*By Fieldname*

### 4. By "Naming Series" field

The naming pattern is derived from a specific field in the document (usually `naming_series`).

For example, if you have a field `naming_series` in your document and its value is set to `PRE.#####`, that pattern will be used to generate the name (e.g., `PRE00001`). This value can change per document, allowing different documents within the same DocType to follow different patterns.

> **Requirement:** This works only if you have a field called `naming_series` in your DocType.

![](/files/naming-series.gif)
*By "Naming Series"*

### 5. Expression

You can provide a standard naming pattern which will be incremented automatically.

For example, if you set the pattern as `PRE-.#####`:

- The first document created will be named `PRE-00001`
- The second will be `PRE-00002`
- And so on...  
  ![](/files/expression.gif)
  *Expression*

You can use this method to flexibly configure naming schemes using multiple field values and variables. Individual parts are separated by a dot `.` .

**Example Pattern:**

```python
EXAMPLE-.MM.-test-.{fieldname1}.-.{fieldname2}.-.#####
```

This format allows you to combine:

- Static text (`EXAMPLE`, `test`)
- Date variables (`MM`, `YYYY`, `DD`, `WW`, `timestamp`)
- Field values (`{fieldname1}`)
- Auto-incrementing numbers ( `#####`)

### 6. Expression (Old Style)

> **Warning: Deprecated in v16** This method is deprecated and will be removed in version 16.

This is a highly flexible method for configuring naming schemes using multiple field values and variables. You enter this pattern directly into the **Auto Name** field in the DocType settings.

**Example Pattern:**

```
EXAMPLE-{MM}-test-{fieldname1}-{fieldname2}-{#####}
```

This format allows you to combine:

- Static text `EXAMPLE`, `test`)
- Date variables `{MM}`, `{YYYY}`, `{DD}`)
- Field values `{fieldname1}`)
- Auto-incrementing numbers `{#####}`)

### 7. Random

Generates a random alphanumeric string as the document name.  

![](/files/ramdom.gif)
*Random*

### 8. UUID

Uses a randomly generated Universally Unique Identifier (UUID v4) as the document name.

**Example:** `550e8400-e29b-41d4-a716-446655440000`  

![](/files/uuid.gif)
*UUID*

### 9. By script

You can define custom naming logic using the `autoname` controller method in your DocType's Python file. This gives you complete control over the naming process.

```
from frappe.model.naming import getseries

class Project(Document):
    def autoname(self):
    # select a project name based on customer
    prefix = f"P-{self.customer}"
    series = getseries(prefix, 3)
    self.name = f"{prefix}-{series}"
```

## By Document Naming Rule

You can also create rules for naming DocTypes by creating **Document Naming Rule.**

![](/files/imagec0c7f9.png)

You can create multiple Document Naming Rules for a particular doctype that can be applied selectively based on filters.

To define a Document Naming Rule you have to specify

1. Document Type it is being applied on
2. Priority of the rule (rules with higher priority will be applied first)
3. Conditions to apply the rule
4. Naming Rules

### Numbering

You can define various numbering prefixes for the rule based on the conditions defined. This is done by setting a prefix and the number of digits for that rule.

For example if you are creating a separate numbering for high priority todos:

1. Prefix: todo-high-
2. Digits: 3

Will lead to numbering like `todo-high-001`, `todo-high-002` and so on.

## Naming Priority

When multiple naming rules might apply, the framework prioritizes them in this order:

1. **Document Naming Rule:** Defined in the `autoname` property of the DocType.
2. **Controller Method:** Logic defined in the `autoname` method of the controller script (overrides DocType settings if defined) .

## Special Rules

1. Child DocTypes do not follow naming rules
2. Amended documents have a suffix (`-1`, `-2` etc) to the original document

