---
title: "bench execute"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/bench/reference/execute"
updated: "2026-09-29"
---

The `bench execute` command lets you run Python functions from the command line. This is useful for running one-off tasks, debugging, or executing custom scripts.

The command automatically sets up the database connection and initializes the Frappe framework for the site, so you can directly call functions that interact with the database without any setup code.

## Basic Usage

```bash
bench --site [site-name] execute [path.to.method]
```

## Simple Examples

```bash
bench --site frappe.test execute frappe.clear_cache
```

This runs the `frappe.clear_cache()` function on your site.

```bash
bench --site frappe.test execute frappe.utils.get_site_info
```

This runs the `frappe.utils.get_site_info()` function on your site and prints the output.

## Passing Arguments

You can pass arguments directly after the method name:

```bash
bench --site frappe.test execute frappe.get_doc User Administrator
```

This calls `frappe.get_doc("User", "Administrator")`.

```bash
bench --site frappe.test execute frappe.db.get_value DocType User name
```

This calls `frappe.db.get_value("DocType", "User", "name")`.

### JSON arguments

Arguments are automatically parsed as JSON when possible:

```bash
bench --site frappe.test execute frappe.db.exists User Administrator
```

The string "Administrator" is kept as a string, but numbers and booleans are converted:

```bash
bench --site frappe.test execute some_function 123 true false
```

This passes the integer `123` and booleans `True` and `False`.

## Named Arguments (kwargs)

Use `--` prefix for named arguments:

```bash
bench --site frappe.test execute frappe.db.get_value --doctype User --filters '{"name":"Administrator"}' --fieldname email
```

This calls:

```python
frappe.db.get_value(doctype="User", filters={"name": "Administrator"}, fieldname="email")
```

### Boolean flags

Named arguments without values become `True`:

```bash
bench --site frappe.test execute frappe.get_list User --ignore_permissions
```

This calls `frappe.get_list("User", ignore_permissions=True)`.

### Mixing positional and named arguments

```bash
bench --site frappe.test execute frappe.get_list User --limit 5
```

This calls `frappe.get_list("User", limit=5)`.

## Running Python Expressions

You can run Python expressions directly:

```bash
bench --site frappe.test execute "frappe.db.count('User')"
```

You can call different types of Python callables:

```bash
# Method on a returned object
bench --site frappe.test execute "frappe.get_doc('User', 'Administrator').reload()"
```

## More Examples

```bash
# Clear cache for a specific DocType
bench --site frappe.test execute frappe.clear_cache --doctype "Sales Order"

# Get a document
bench --site frappe.test execute frappe.get_doc User Administrator

# Count records
bench --site frappe.test execute frappe.db.count User

# Run a whitelisted method
bench --site frappe.test execute myapp.api.my_function --param1 value1 --param2 value2

# Check if a record exists
bench --site frappe.test execute frappe.db.exists User guest

# Get configuration value
bench --site frappe.test execute frappe.conf.get developer_mode

# Execute a DocType method
bench --site frappe.test execute "frappe.get_doc('User', 'Administrator').get_fullname()"

# Chain operations with Python expressions
bench --site frappe.test execute "frappe.get_doc('User', 'Administrator').add_roles('System Manager')"
```

## Profiling

Use the `--profile` flag to see performance statistics:

```bash
bench --site frappe.test execute frappe.db.get_list --profile --doctype "Sales Order" --limit 1000
```

This prints the top 50% of function calls sorted by cumulative time.

```bash
        42084 function calls (41224 primitive calls) in 0.094 seconds

   Ordered by: cumulative time
   List reduced from 801 to 401 due to restriction <0.5>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
      3/2    0.000    0.000    0.091    0.046 {built-in method builtins.eval}
        1    0.000    0.000    0.091    0.091 <bench execute>:1(<module>)
        1    0.000    0.000    0.091    0.091 ~/frappe-bench/apps/frappe/frappe/database/database.py:830(get_list)
     11/1    0.000    0.000    0.091    0.091 ~/frappe-bench/apps/frappe/frappe/__init__.py:1337(get_list)
       31    0.000    0.000    0.073    0.002 ~/frappe-bench/apps/frappe/frappe/database/database.py:183(sql)
       29    0.000    0.000    0.072    0.002 ~/frappe-bench/apps/frappe/frappe/query_builder/utils.py:126(execute_query)
     18/5    0.000    0.000    0.071    0.014 ~/frappe-bench/apps/frappe/frappe/utils/caching.py:125(site_cache_wrapper)
    20/12    0.000    0.000    0.070    0.006 ~/frappe-bench/apps/frappe/frappe/model/meta.py:72(get_meta)
      7/3    0.000    0.000    0.070    0.023 ~/frappe-bench/apps/frappe/frappe/model/utils/__init__.py:132(is_virtual_doctype)
        2    0.000    0.000    0.069    0.034 ~/frappe-bench/apps/frappe/frappe/model/meta.py:149(__init__)
       31    0.000    0.000    0.066    0.002 ~/frappe-bench/apps/frappe/frappe/database/database.py:371(execute_query)
       31    0.000    0.000    0.066    0.002 ~/frappe-bench/env/lib/python3.14/site-packages/MySQLdb/cursors.py:162(execute)
       31    0.000    0.000    0.066    0.002 ~/frappe-bench/env/lib/python3.14/site-packages/MySQLdb/cursors.py:325(_query)
       31    0.000    0.000    0.065    0.002 ~/frappe-bench/env/lib/python3.14/site-packages/MySQLdb/connections.py:276(query)
       31    0.065    0.002    0.065    0.002 {function Connection.query at 0x10be545c0}
       16    0.000    0.000    0.056    0.003 ~/frappe-bench/apps/frappe/frappe/database/database.py:592(get_values)
        2    0.000    0.000    0.034    0.017 ~/frappe-bench/apps/frappe/frappe/model/meta.py:166(process)
     31/2    0.000    0.000    0.034    0.017 ~/frappe-bench/apps/frappe/frappe/model/document.py:187(__init__)
        2    0.000    0.000    0.034    0.017 ~/frappe-bench/apps/frappe/frappe/model/meta.py:157(load_from_db)
        2    0.000    0.000    0.034    0.017 ~/frappe-bench/apps/frappe/frappe/model/document.py:233(load_from_db)
     11/1    0.000    0.000    0.025    0.025 ~/frappe-bench/apps/frappe/frappe/model/qb_query.py:26(execute)
    27/13    0.000    0.000    0.022    0.002 ~/frappe-bench/apps/frappe/frappe/query_builder/utils.py:62(get_query)
        2    0.000    0.000    0.021    0.011 ~/frappe-bench/apps/frappe/frappe/model/meta.py:422(apply_property_setters)
        2    0.000    0.000    0.018    0.009 ~/frappe-bench/apps/frappe/frappe/model/document.py:304(load_children_from_db)
    27/13    0.000    0.000    0.018    0.001 ~/frappe-bench/apps/frappe/frappe/database/query.py:215(get_query)
        2    0.000    0.000    0.016    0.008 ~/frappe-bench/apps/frappe/frappe/database/database.py:514(get_value)
    27/13    0.000    0.000    0.015    0.001 ~/frappe-bench/apps/frappe/frappe/database/query.py:344(apply_fields)
        1    0.000    0.000    0.014    0.014 ~/frappe-bench/apps/frappe/frappe/database/query.py:1280(apply_field_permissions)
        1    0.000    0.000    0.013    0.013 ~/frappe-bench/apps/frappe/frappe/database/query.py:928(_get_cached_permitted_fields)
        1    0.000    0.000    0.013    0.013 ~/frappe-bench/apps/frappe/frappe/model/__init__.py:216(get_permitted_fields)
        1    0.000    0.000    0.013    0.013 ~/frappe-bench/apps/frappe/frappe/model/meta.py:677(get_permitted_fieldnames)
        1    0.000    0.000    0.013    0.013 ~/frappe-bench/apps/frappe/frappe/model/meta.py:720(get_permlevel_access)
        2    0.000    0.000    0.013    0.007 ~/frappe-bench/apps/frappe/frappe/__init__.py:384(get_roles)
        2    0.000    0.000    0.013    0.007 ~/frappe-bench/apps/frappe/frappe/permissions.py:522(get_roles)
        2    0.000    0.000    0.013    0.007 ~/frappe-bench/apps/frappe/frappe/utils/redis_wrapper.py:230(hget)
        1    0.000    0.000    0.013    0.013 ~/frappe-bench/apps/frappe/frappe/permissions.py:530(get)
        1    0.000    0.000    0.012    0.012 ~/frappe-bench/env/lib/python3.14/site-packages/redis/client.py:1163(get_message)
        1    0.000    0.000    0.012    0.012 ~/frappe-bench/env/lib/python3.14/site-packages/redis/client.py:979(parse_response)
        1    0.000    0.000    0.012    0.012 ~/frappe-bench/env/lib/python3.14/site-packages/redis/client.py:960(_execute)
       13    0.000    0.000    0.009    0.001 ~/frappe-bench/apps/frappe/frappe/model/meta.py:108(get_table_columns)
       13    0.000    0.000    0.009    0.001 ~/frappe-bench/apps/frappe/frappe/database/database.py:1356(get_table_columns)
       13    0.000    0.000    0.009    0.001 ~/frappe-bench/apps/frappe/frappe/database/database.py:1337(get_db_table_columns)
```

## Running on Multiple Sites

Execute a command on all sites:

```bash
bench --site all execute frappe.clear_cache
```

Or specific sites:

```bash
bench --site site1.local --site site2.local execute frappe.clear_cache
```

## Notes

- **Database**: Changes are automatically committed on success and rolled back on error
- **Return Values**: Return values are printed as JSON; `None` returns print nothing
- **Error Handling**: Errors exit with an error code and print the full traceback
- **Security**: Any Python function can be executed, not just whitelisted ones - use carefully in production

## Using the --args and --kwargs Options (Legacy)

&gt; **Note**: The `--args` and `--kwargs` options are the old format and are not encouraged. Use the direct argument passing methods shown above instead.

You must use the `--args` and `--kwargs` options with Python syntax. These values must be enclosed in quotes and will be evaluated as Python code (using `eval()`), not parsed as JSON.

### Pass a list of arguments

```bash
bench --site frappe.test execute frappe.db.get_value --args "['User', 'Administrator', 'email']"
```

### Pass a dictionary of keyword arguments

```bash
bench --site frappe.test execute frappe.db.set_value --kwargs "{'doctype': 'User', 'name': 'Administrator', 'fieldname': 'enabled', 'value': 1}"
```

### Combine both

```bash
bench --site frappe.test execute frappe.db.get_value --args "['User', 'Administrator']" --kwargs "{'fieldname': 'email'}"
```

