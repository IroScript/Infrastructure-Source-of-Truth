---
title: "Script Report\n"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/guides/reports-and-printing/how-to-make-script-reports"
updated: "2026-06-04"
---

You can create tabulated reports using server side scripts by creating a new Report.

> Note: You will need Administrator Permissions for this.

Since these reports give you unrestricted access via Python scripts, they can only be created by Administrators. The script part of the report becomes a part of the repository of the application. If you have not created an app, read this.

> Note: You must be in Developer Mode to do this

### 1. Create a new Report

![Script Report](/files/script-report.png)

1. Set Report Type as "Script Report"
2. Set "Is Standard" as "Yes"
3. Select the Module in which you want to add this report
4. In the module folder (for example if it is Accounts in ERPnext the folder will be `erpnext/accounts/report/[report-name]`) you will see that templates for the report files will be created.
5. In the `.js` file, you can set filters for the reports
6. In the `.py` file, you can write the script that will generate the report

### 2. Add Filters

You can add filters in the `.js`. See an example below:

```javascript
frappe.query_reports["Accounts Receivable"] = {
    "filters": [
        {
            "fieldname":"company",
            "label": ("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.getuserdefault("company")
        },
    ]
}
```

1. These properties are the same as you would set in a DocField in a DocType

### 3. Add the Script

In the `.py` file you can add the script for generating the report.

1. In the `execute` method, two lists `columns` and `data` are returned
2. Columns must be a list of dictionaries containing fields like fieldname, label, fieldtype, options,width. For example:

```python
[
	{
		"fieldname": "account",
		"label": _("Account"),
		"fieldtype": "Link",
		"options": "Account",
		"width": 300,
	},
	{
		"fieldname": "currency",
		"label": _("Currency"),
		"fieldtype": "Link",
		"options": "Currency",
	},
]
```

1. You can use all server side modules to build your report.
2. For example see existing reports. (Balance Sheet)

### 4. Add link for your report on the module page

![Module Page](/files/script-report-1.png)

1. In the module folder (for example if it is Accounts in ERPNext the folder will be `erpnext/config/accounts.py`) you will see labels and items for various sections. The new report can be added in the item list as show in the example:

```python
def get_data():
	return [
		{
			"label": _("Accounting Statements"),
			"items": [
				{
					"type": "report",
					"name": "Balance Sheet",
					"doctype": "GL Entry",
					"is_query_report": True,
				}
			],
		}
	]
```

## Prepared Reports

Some script reports take too long to run in the browser. **Prepared Report** moves execution to a background job so users are not blocked while the report runs.

When *Prepared Report* is checked on a **Report**, each run is queued instead of executed synchronously. The user sees a progress indicator and gets a notification when the result is ready. Completed results are stored as **Prepared Report** documents and can be reopened later with the same filters.

*Prepared Report* also unlocks:

- *Generate CSV* — optionally produce a CSV attachment alongside the JSON result
- *Timeout (In Seconds)* — how long the background job may run before it is considered failed (default: 1500 seconds)

Prepared reports are intended for reports that are slow but stable. Users should expect to wait and come back for the result, not get an instant table in the browser.

