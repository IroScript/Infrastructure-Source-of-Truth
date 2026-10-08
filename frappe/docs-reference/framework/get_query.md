---
title: "frappe.qb.get_query"
space: "Framework"
url: "https://docs.frappe.io/framework/get_query"
updated: "2026-02-17"
---

The `frappe.qb.get_query` function provides a modern, safe, and expressive way to build database queries in Frappe. It leverages the power of the [Pypika](https://pypika.readthedocs.io/en/latest/) library while integrating seamlessly with Frappe's DocType metadata, permissions, and conventions. This guide will walk you through using `frappe.qb.get_query` from basic usage to more advanced scenarios.

## Introduction

While `frappe.db.get_list` and `frappe.db.get_all` have served Frappe well for many years and are capable of handling complex queries, their underlying code has grown complex over time, making them harder to maintain and extend. `frappe.qb.get_query` represents a modern approach to achieve similar results, built with better extensibility and maintainability in mind.

## Getting Started

### Basic Query Structure

To get started, you need to understand the basic structure of a query:

```python
# Get a query builder instance for the 'User' DocType
query = frappe.qb.get_query("User")

# Execute the query and fetch results
users = query.run(as_dict=True)
```

By default, if no `fields` are specified, it selects **only the `name` field**.

### Simple Example

```python
# Get all user names and emails
query = frappe.qb.get_query("User", fields=["name", "email"])
users = query.run(as_dict=True)
# users will be like: [{'name': 'Administrator', 'email': 'admin@example.com'}, ...]
```

## Field Selection

### Basic Field Selection

Use the `fields` argument to specify which columns you want.

```python
# Select specific fields
query = frappe.qb.get_query("User", fields=["name", "email"])

# You can also pass fields as a comma-separated string
query = frappe.qb.get_query("User", fields="name, email")

# Or select all fields using '*'
query = frappe.qb.get_query("User", fields="*")
```

### Using Aliases

Use `as` within the field string to give fields aliases in the output.

```python
query = frappe.qb.get_query(
    "User",
    fields=["name as user_name", "email as user_email"]
)
users = query.run(as_dict=True)
# users will be like: [{'user_name': 'Administrator', 'user_email': 'admin@example.com'}, ...]
```

### Linked Document Fields

If you have a Link field, you can fetch fields from the linked document using dot notation: `link_fieldname.target_fieldname`. The query builder automatically adds the necessary `LEFT JOIN`.

```python
# Get Sales Order customer name (assuming 'customer' is a Link field to Customer DocType)
query = frappe.qb.get_query(
    "Sales Order",
    fields=["name", "customer.customer_name as customer_name"],
    filters={"name": "SO-00001"}
)
so_data = query.run(as_dict=True)
# so_data might be: [{'name': 'SO-00001', 'customer_name': 'Test Customer'}]
```

### Child Table Fields

You can access fields within a Child Table using dot notation: `child_table_fieldname.child_doc_fieldname`.

```python
# Get item code from Sales Order Item (assuming 'items' is the child table fieldname)
query = frappe.qb.get_query(
    "Sales Order",
    fields=["name", "items.item_code"],
    filters={"name": "SO-00001"}
)
# This will likely return multiple rows if SO-00001 has multiple items
so_items = query.run(as_dict=True)
# so_items might be: [{'name': 'SO-00001', 'item_code': 'ItemA'}, {'name': 'SO-00001', 'item_code': 'ItemB'}]
```

**Important:** When selecting fields from child tables this way, the query performs a `LEFT JOIN`, potentially resulting in multiple rows for each parent document if the child table has multiple entries.

### Fetching Child Table Records

A more structured way to fetch child table data:

```python
# Get Sales Orders and their associated items
query = frappe.qb.get_query(
    "Sales Order",
    fields=[
        "name",
        "customer",
        {"items": ["item_code", "qty", "rate"]} # Fetch from 'items' child table
    ],
    filters={"docstatus": 1},
    limit=5
)

results = query.run(as_dict=True)

# Example result structure:
# [
#   {
#     'name': 'SO-00001',
#     'customer': 'Customer A',
#     'items': [
#       {'item_code': 'ItemA', 'qty': 2.0, 'rate': 100.0},
#       {'item_code': 'ItemB', 'qty': 1.0, 'rate': 50.0}
#     ]
#   },
#   {
#     'name': 'SO-00002',
#     'customer': 'Customer B',
#     'items': [
#       {'item_code': 'ItemC', 'qty': 5.0, 'rate': 20.0}
#     ]
#   }
# ]
```

This approach performs a separate query for the child records after fetching the parent records, efficiently grouping them by parent.


### SQL Functions in Fields

To use SQL functions in your select clauses, you can use dictionary-based syntax within the `fields` argument.

#### Aggregation Functions

```python
# COUNT - Count rows or non-null values
query = frappe.qb.get_query(
    "User",
    fields=["user_type", {"COUNT": "name", "as": "total_users"}],
    group_by="user_type"
)

# COUNT(*) - Count all rows including nulls
query = frappe.qb.get_query(
    "Sales Invoice",
    fields=[{"COUNT": "'*'", "as": "total_invoices"}]
)

# SUM - Calculate sum of numeric values
query = frappe.qb.get_query(
    "Sales Invoice",
    fields=[{"SUM": "grand_total", "as": "total_sales"}],
    filters={"docstatus": 1}
)

# AVG - Calculate average of numeric values
query = frappe.qb.get_query(
    "Sales Invoice",
    fields=[{"AVG": "grand_total", "as": "avg_invoice_amount"}],
    group_by="customer"
)

# MAX - Find maximum value
query = frappe.qb.get_query(
    "User",
    fields=[{"MAX": "creation", "as": "latest_user_date"}]
)

# MIN - Find minimum value
query = frappe.qb.get_query(
    "User",
    fields=[{"MIN": "creation", "as": "earliest_user_date"}]
)
```

#### Scalar Functions

```python
# ABS - Absolute value
query = frappe.qb.get_query(
    "Journal Entry Account",
    fields=[{"ABS": "debit_in_account_currency", "as": "abs_amount"}]
)

# IFNULL - Handle null values (takes two arguments)
query = frappe.qb.get_query(
    "User",
    fields=[{"IFNULL": ["first_name", "'Unknown'"], "as": "display_name"}]
)

# CONCAT - Concatenate strings (takes multiple arguments)
query = frappe.qb.get_query(
    "User",
    fields=[{"CONCAT": ["first_name", "' '", "last_name"], "as": "full_name"}]
)

# EXTRACT - Extract part of date/time (takes two arguments: unit and date)
query = frappe.qb.get_query(
    "User",
    fields=[{"EXTRACT": ["'YEAR'", "creation"], "as": "creation_year"}]
)

# NOW - Current timestamp (no arguments)
query = frappe.qb.get_query(
    "User",
    fields=[{"NOW": None, "as": "current_time"}]
)
```


## Filtering

### Basic Filters

The `filters` argument allows you to add `WHERE` clauses.

#### Dictionary Filters (Equality)

This is the simplest and often preferred way for equality checks.

```python
# Get users with first_name 'Admin'
query = frappe.qb.get_query(
    "User",
    fields=["name", "email"],
    filters={"first_name": "Admin"} # Simple key-value implies '='
)
```

#### Dictionary Filters (Other Operators)

For operators other than `=`, use a dictionary where the value is a list `[operator, value]`.

```python
# Get users created after a certain date
query = frappe.qb.get_query(
    "User",
    fields=["name", "creation"],
    filters={"creation": [">", "2023-01-01 00:00:00"]}
)

# Get users whose name is like 'test%'
query = frappe.qb.get_query(
    "User",
    fields=["name"],
    filters={"name": ["like", "test%"]}
)

# Get users whose name is in a list
query = frappe.qb.get_query(
    "User",
    fields=["name"],
    filters={"name": ["in", ["test1@example.com", "test2@example.com"]]}
)

# Get users whose name is NOT in a list
query = frappe.qb.get_query(
    "User",
    fields=["name"],
    filters={"name": ["not in", ["Administrator", "Guest"]]}
)
```

#### List Filters (Alternative Format)

You can also provide a list containing filter lists `[[fieldname, operator, value]]`.

```python
# Get users created after a certain date (using list format)
query = frappe.qb.get_query(
    "User",
    fields=["name", "creation"],
    filters=[["creation", ">", "2023-01-01 00:00:00"]]
)

# Multiple filters (combined with AND)
query = frappe.qb.get_query(
    "User",
    fields=["name"],
    filters=[
        ["enabled", "=", 1],
        ["user_type", "=", "System User"]
    ]
)
```

### Filter Operators

`frappe.qb.get_query` supports various operators:

| Operator String    | SQL Equivalent | Example Usage (Dictionary Format)                    | Example Usage (List Format)                               |
| :----------------- | :------------- | :--------------------------------------------------- | :-------------------------------------------------------- |
| `=`                | `=`            | `{"name": "Test"}`                                   | `[["name", "=", "Test"]]`                                 |
| `!=`               | `!=`           | `{"name": ["!=", "Test"]}`                           | `[["name", "!=", "Test"]]`                                |
| `>`                | `>`            | `{"creation": [">", "2023-01-01"]}`                 | `[["creation", ">", "2023-01-01"]]`                       |
| `<`                | `<`            | `{"creation": ["<", "2023-01-01"]}`                 | `[["creation", "<", "2023-01-01"]]`                       |
| `>=`               | `>=`           | `{"age": [">=", 18]}`                               | `[["age", ">=", 18]]`                                     |
| `<=`               | `<=`           | `{"age": ["<=", 65]}`                               | `[["age", "<=", 65]]`                                     |
| `like`             | `LIKE`         | `{"subject": ["like", "%urgent%"]}`                 | `[["subject", "like", "%urgent%"]]`                       |
| `not like`         | `NOT LIKE`     | `{"subject": ["not like", "spam%"]}`                | `[["subject", "not like", "spam%"]]`                      |
| `in`               | `IN`           | `{"status": ["in", ["Open", "Pending"]]}`           | `[["status", "in", ["Open", "Pending"]]]`                 |
| `not in`           | `NOT IN`       | `{"role": ["not in", ["Guest"]]}`                   | `[["role", "not in", ["Guest"]]]`                         |
| `is`               | `IS NULL` or `IS NOT NULL` | `{"customer": ["is", "set"]}` or `{"email": ["is", "not set"]}` | `[["customer", "is", "set"]]` or `[["email", "is", "not set"]]` |
| `descendants of`   | (Nested Set)   | `{"parent_account": ["descendants of", "Assets"]}`  | `[["parent_account", "descendants of", "Assets"]]`        |
| `ancestors of`     | (Nested Set)   | `{"location": ["ancestors of", "Room 101"]}`        | `[["location", "ancestors of", "Room 101"]]`              |
| `not descendants of` | (Nested Set)   | `{"category": ["not descendants of", "Internal"]}` | `[["category", "not descendants of", "Internal"]]`         |
| `not ancestors of` | (Nested Set)   | `{"territory": ["not ancestors of", "West Coast"]}` | `[["territory", "not ancestors of", "West Coast"]]`       |

**Note on `is set` / `is not set`:** These check if a field has a value (`IS NOT NULL` and `IS NULL` respectively).

### Filtering on Linked Document Fields

You can filter based on fields in linked documents using dot notation: `link_fieldname.target_fieldname`.

```python
# Get Sales Orders where the linked Customer's territory is 'North America'
query = frappe.qb.get_query(
    "Sales Order",
    fields=["name", "customer"],
    filters={"customer.territory": "North America"} # Filter on linked field
)
north_america_orders = query.run(as_dict=True)
```

### Filtering by Child Table Fields

You can filter parent records based on values in their child table records using dot notation: `child_table_fieldname.target_fieldname`.

```python
# Get Sales Orders that contain 'Item A' in their items table
# Use distinct=True to ensure each Sales Order appears only once
query = frappe.qb.get_query(
    "Sales Order",
    fields=["name", "customer"],
    filters={"items.item_code": "Item A"}, # Filter based on child table field
    distinct=True
)
orders_with_item_a = query.run(as_dict=True)
```

**Important:** When filtering based on child table fields, use `distinct=True` if you only want unique parent records.

### Nested Set Filters

For DocTypes that are trees (using `lft` and `rgt` columns, like Account, Territory, Warehouse, etc.), you can use special filters:

```python
# Get all accounts under 'Assets'
query = frappe.qb.get_query(
    "Account",
    fields=["name"],
    filters={"parent_account": ["descendants of", "Assets"]}
)

# Get the parent territories of 'West Coast'
query = frappe.qb.get_query(
    "Territory",
    fields=["name"],
    filters={"parent_territory": ["ancestors of", "West Coast"]}
)
```

### Logical Operators (AND/OR)

For complex conditions, structure your `filters` as a list combining conditions with `'and'` or `'or'`.

```python
# Find users who are enabled AND have first name 'Admin'
filters_and = [
    ["enabled", "=", 1],
    "and",
    ["first_name", "=", "Admin"],
]
query = frappe.qb.get_query("User", filters=filters_and)

# Find users who have first name 'Admin' OR 'Guest'
filters_or = [
    ["first_name", "=", "Admin"],
    "or",
    ["first_name", "=", "Guest"],
]
query = frappe.qb.get_query("User", filters=filters_or)

# Combine AND and OR (use nested lists for grouping)
# Find users who are enabled AND (have first name 'Admin' OR 'Guest')
filters_nested = [
    ["enabled", "=", 1],
    "and",
    [
        ["first_name", "=", "Admin"],
        "or",
        ["first_name", "=", "Guest"],
    ]
]
query = frappe.qb.get_query("User", filters=filters_nested)
```

## Query Execution

### Basic Execution

Once you have the `query` object, execute it using `.run()`:

```python
# Returns a list of tuples by default
results = query.run()

# Returns a list of dictionaries
results = query.run(as_dict=True)

# Returns a list of lists
results = query.run(as_list=True)

# If selecting a single field, returns a flat list of values
results = query.run(pluck=True)

# Print the generated SQL query and execution time
results = query.run(debug=True)
```

### Getting the SQL String

You can get the generated SQL string without executing:

```python
# Get the SQL string with values directly substituted (for debugging)
sql_string = query.get_sql()
print(sql_string)
# Example Output: SELECT `name`, `email` FROM `tabUser` WHERE `first_name`='Admin'
```

### Using Iterators for Large Datasets

When dealing with large datasets, use `as_iterator=True` to process results row by row without loading everything into memory:

```python
# Process a large number of tasks without loading all into memory
query = frappe.qb.get_query(
    "Task",
    fields=["name", "subject", "status"],
    filters={"status": "Open"}
)

# Use unbuffered_cursor for optimal memory usage with the iterator
with frappe.db.unbuffered_cursor():
    task_iterator = query.run(as_iterator=True, as_dict=True)

    processed_count = 0
    for task in task_iterator:
        # Process each task dictionary one by one
        print(f"Processing Task: {task['name']} - {task['subject']}")
        processed_count += 1
        if processed_count % 1000 == 0:
            print(f"Processed {processed_count} tasks...")
```

**Requirements:**

- You must use `as_iterator=True` with either `as_dict=True` or `as_list=True`
- For optimal memory efficiency, use within `frappe.db.unbuffered_cursor()` context manager

## Ordering, Grouping, and Pagination

### Ordering Results

Use the `order_by` argument to sort results:

```python
# Order users by creation date, ascending
query = frappe.qb.get_query("User", fields=["name", "creation"], order_by="creation asc")

# Order by multiple fields
query = frappe.qb.get_query(
    "Sales Invoice",
    fields=["name", "customer", "grand_total"],
    order_by="customer asc, grand_total desc"
)
```

### Grouping Results

Use `group_by` for aggregation:

```python
# Count invoices per customer
query = frappe.qb.get_query(
    "Sales Invoice",
    fields=["customer", {"COUNT": "'*'", "as": "invoice_count"}],
    filters={"docstatus": 1},
    group_by="customer"
)
results = query.run(as_dict=True)
# results: [{'customer': 'Cust A', 'invoice_count': 5}, {'customer': 'Cust B', 'invoice_count': 3}, ...]
```

### Pagination

Use `limit` and `offset` for pagination:

```python
# Get the first 10 users
query = frappe.qb.get_query("User", limit=10)

# Get the next 10 users (page 2)
query = frappe.qb.get_query("User", limit=10, offset=10)
```

### Distinct Results

Use `distinct=True` to get unique rows:

```python
# Get distinct customers from submitted Sales Invoices
query = frappe.qb.get_query(
    "Sales Invoice",
    fields=["customer"],
    filters={"docstatus": 1},
    distinct=True
)
```

## Permissions

### The `ignore_permissions` Flag

By default, `frappe.qb.get_query` **ignores** permissions (`ignore_permissions=True`). To enforce permissions, set `ignore_permissions=False`:

```python
# This query bypasses all permission checks (default behavior)
query_ignore = frappe.qb.get_query("DocType", fields=["name"], filters={"istable": 1})

# This query enforces standard Frappe permissions for the current user
query_enforce = frappe.qb.get_query(
    "DocType",
    fields=["name"],
    filters={"istable": 1},
    ignore_permissions=False # Explicitly enable permission checks
)

try:
    results = query_enforce.run()
except frappe.PermissionError:
    print("User does not have permission to read DocType!")
```

### How Permissions are Applied

When `ignore_permissions=False`:

1. **Role Permissions:** Checks if the user has 'read' or 'select' permission based on their roles.
2. **User Permissions:** Applies User Permissions (Allow/Restrict) defined for the DocType and linked DocTypes.
3. **Sharing:** Includes documents explicitly shared with the user.
4. **Owner Constraint:** If the role permissions only grant access `if_owner`, the query restricts results to documents owned by the user.
5. **Permission Query Conditions:** Applies conditions defined via Hooks or Server Scripts.
6. **Field Level Security:** Filters the selected `fields`, and does not allow fields used in `filters`, `group_by`, `order_by` if user does not have permlevel access. Also checks fields in `link_field.target_field` and `child_field.target_field` notations.

### Field-Level Security

When `ignore_permissions=False`:

- **`fields`:** Only fields accessible at the user's maximum permitted permlevel are included. Requesting inaccessible fields will **silently remove** the field from the selection.
- **`filters`:** Filtering is **only allowed** on fields the user has permission to access. Attempting to filter on an inaccessible field **will raise** a `frappe.PermissionError`.
- **`group_by`:** Grouping is **only allowed** on fields the user has permission to access. Attempting to group by an inaccessible field **will raise** a `frappe.PermissionError`.
- **`order_by`:** Ordering is **only allowed** on fields the user has permission to access. Attempting to order by an inaccessible field **will raise** a `frappe.PermissionError`.
- **Linked and Child Table Fields:** When using `link_field.target_field` or `child_field.target_field` notation in any of the above clauses, the system checks permissions for both the link/child field itself and the target field in the linked/child DocType.

```python
# Assume 'published' field in Blog Post has permlevel 1
# User 'test@example.com' only has permlevel 0 access

# This works, but 'published' field is silently removed from results
query = frappe.qb.get_query(
    "Blog Post",
    fields=["name", "title", "published"], # 'published' requested but inaccessible
    ignore_permissions=False,
    user="test@example.com"
)
# result will contain 'name' and 'title', but NOT 'published'

# This FAILS because filtering on 'published' is not allowed for this user
try:
    query = frappe.qb.get_query(
        "Blog Post",
        fields=["name"],
        filters={"published": 1}, # Filtering on restricted field
        ignore_permissions=False,
        user="test@example.com"
    )
    query.run()
except frappe.PermissionError as e:
    print(f"Permission error: {e}")
```

### Specifying User and Parent Context

```python
# Check permissions for a specific user
query = frappe.qb.get_query(
    "Task",
    ignore_permissions=False,
    user="test@example.com" # Check permissions for this user
)

# Provide parent context for child DocTypes
query = frappe.qb.get_query(
    "Sales Order Item",
    fields=["item_code", "qty"],
    filters={"parent": "SO-00001"},
    ignore_permissions=False,
    parent_doctype="Sales Order" # Specify parent context for permission checks
)
```

## Advanced Features

### Using Pypika Objects

For complex scenarios involving subqueries, advanced conditions, or functions not available in the dictionary syntax, you can use Pypika objects directly.

#### Pypika Objects in Fields

```python
from frappe.query_builder import Field, functions, Query

# Define Pypika objects
user_table = frappe.qb.DocType("User")
todo_table = frappe.qb.DocType("ToDo")

# Build a subquery to count open ToDos for each user
open_todo_subquery = (
    Query.from_(todo_table)
    .select(functions.Count("*"))
    .where(todo_table.owner == user_table.name) # Correlated subquery
    .where(todo_table.status == "Open")
).as_("open_todos_count")

# Use Pypika objects in fields
query = frappe.qb.get_query(
    "User",
    fields=[
        user_table.name,
        user_table.email,
        open_todo_subquery # Using the subquery object
    ],
    filters={"user_type": "System User"}
)
users_with_counts = query.run(as_dict=True)
```

#### Pypika Objects in Filters

```python
from frappe.query_builder import Field, functions

# Define Pypika objects
task_table = frappe.qb.DocType("Task")
modified_field = task_table.modified
creation_field = task_table.creation
subject_field = task_table.subject
status_field = task_table.status

# Build complex criterion
complex_filter = (
    (modified_field > creation_field) & (functions.Length(subject_field) > 10)
) | (status_field == "Cancelled")

# Use the Criterion object in filters
query = frappe.qb.get_query(
    "Task",
    fields=["name", "subject", "status", "creation", "modified"],
    filters=complex_filter
)
results = query.run(as_dict=True)
```

### Record Locking

For use within database transactions where you need to prevent other transactions from modifying specific rows:

#### Basic Locking

```python
# Lock specific Stock Ledger Entries
query = frappe.qb.get_query(
    "Stock Ledger Entry",
    fields=["name", "qty_after_transaction"],
    filters={"item_code": "ITEM001", "warehouse": "WH001"},
    for_update=True # Adds FOR UPDATE clause, will wait if rows are locked
)
entries = query.run(as_dict=True)
```

#### Skip Locked Rows

```python
# Skip rows that are already locked by another transaction
query = frappe.qb.get_query(
    "ToDo",
    fields=["name", "description"],
    filters={"status": "Pending"},
    limit=5,
    order_by="creation asc",
    for_update=True,
    skip_locked=True # Skip locked rows
)
available_tasks = query.run(as_dict=True)
```

#### Non-Blocking Lock Attempt

```python
# Fail immediately if rows are already locked
try:
    query = frappe.qb.get_query(
        "System Settings",
        fields=["name"],
        filters={"name": "System Settings"},
        for_update=True,
        wait=False # Don't wait for locks
    )
    settings = query.run(as_dict=True)
except Exception as e:
    print(f"Could not acquire lock immediately: {e}")
```

## Security Considerations

`frappe.qb.get_query` is designed with security in mind:

- **Field Validation:** Field names are validated against strict patterns to prevent SQL injection.
- **Parameterization:** Filter values are parameterized by the database driver.
- **Permission Enforcement:** Using `ignore_permissions=False` leverages Frappe's robust permission system.

Always ensure that any dynamic values used to construct filter keys or field names are properly sanitized if they originate from untrusted sources. **Always rely on passing user input as filter values.**


Written by Claude Sonnet 4. Reviewed by human.