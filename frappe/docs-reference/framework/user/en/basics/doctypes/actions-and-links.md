---
title: "Actions and Links"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/basics/doctypes/actions-and-links"
updated: "2026-03-12"
---

> Added in Version 12.1  
>  
> 

Action and Links (also called Connections) are two ways to provide the end user more interaction with the document. The image below shows what they are :

![Action and Link View](/files/action-link.png)



## Actions

A DocType may have some `DocType Action` that will result in a button creation on the DocType View. Supported actions are:

1. **Server Action**: This will trigger a whitelisted server action.
2. **Route**: This will redirect to a given route.

### Configuration of Action

![Action Configuraton](/files/action-config.png)



### Configuration of Action in custom app

To call an Action in you own app, you will need a python function decorated with `frappe.whitelist` :

```
import frappe

@frappe.whitelist()
def execute_function(*args,**kwargs):
    """
 This function will be executed when the Execute Action Button will be clicked
 """
    print('Hello World')
    # The data is transmitted via keyword argument
    print(kwargs)
  

```

This code should go somewhere inside you app, typically in a file like `apps/my_app/my_app/api.py`

And then, configure the correspondant Action path :

![Custom Action Configuraton](/files/custom-app-action-config.png)



## Connections (Linked Documents)

A standard navigation aid to the DocType view is the `Connections` section on the dashboard. This helps the viewer identify at a glance which document types are connected to this DocType and can quickly create new related documents.

These links also support adding internal links (links to DocType in child tables).

### Configuration Connections

![Link Configuration](/files/link-config.png)



![Internal Link](/files/internal-link.png)



### Via script

To configure connections for a doctype in your app, create a `get_data()` function inside `<doctype>_dashboard.py`. Here's an example from the `sales_invoice_dashboard.py` of the Sales Invoice doctype from ERPNext:

```
from frappe import _


def get_data():
	return {
		"fieldname": "sales_invoice",
		"non_standard_fieldnames": {
			"Delivery Note": "against_sales_invoice",
			"Journal Entry": "reference_name",
			"Payment Entry": "reference_name",
			"Payment Request": "reference_name",
			"Sales Invoice": "return_against",
			"Auto Repeat": "reference_document",
			"Purchase Invoice": "inter_company_invoice_reference",
		},
		"internal_links": {
			"Sales Order": ["items", "sales_order"],
			"Timesheet": ["timesheets", "time_sheet"],
		},
		"internal_and_external_links": {
			"Delivery Note": ["items", "delivery_note"],
		},
		"transactions": [
			{
				"label": _("Payment"),
				"items": [
					"Payment Entry",
					"Payment Request",
					"Journal Entry",
					"Invoice Discounting",
					"Dunning",
				],
			},
			{"label": _("Reference"), "items": ["Timesheet", "Delivery Note", "Sales Order"]},
			{"label": _("Returns"), "items": ["Sales Invoice"]},
			{"label": _("Subscription"), "items": ["Auto Repeat"]},
			{"label": _("Internal Transfers"), "items": ["Purchase Invoice"]},
		],
	}
```

- `transactions` define all the connections and the respective groups to put them under.
- `internal_links` define the connections where the doctype has internal links. For example, Sales Invoice has internal links through its Item child table to the Sales Order doctype.
- `internal_and_external_links` define the connections where the doctype has both internal and external links. For example, Sales Invoice has internal links through its Item child table to the Delivery Note doctype and Sales Invoice also has external links to the Delivery Note doctype through its Item child table.
- `fieldname` defines the default fieldname to be searched while finding external links for the doctype.
- `non_standard_fieldnames` define the fieldnames and their respective doctypes to be searched while finding external links for the doctype.

This would result in the following connections:

![](/files/EgU4Cnp.png)



### Customization of Actions and Links

DocType Actions and Links are extensible via [Customize Form](customize)