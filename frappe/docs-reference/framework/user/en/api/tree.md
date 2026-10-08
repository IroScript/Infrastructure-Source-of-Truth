---
title: "Tree\n"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/api/tree"
updated: "2026-02-17"
---

The Tree View is generated for all DocTypes that has Is Tree enabled.

![Tree View](/files/treeview.png)
*Tree View*

## Standard Tree JS

To customize the Tree View you must have a `{doctype}_tree.js` file in the doctype directory.
Below are all the options that can be customized.

For instance, if you want to configure the Account DocType, you'll have to create a file `account_tree.js` with the following contents.

```js
frappe.treeview_settings["Account"] = {
	breadcrumb: "Accounting",
	title: "Chart of Accounts",

	filters: [
		{
			fieldname: "company",
			fieldtype: "Select",
			label: "Company",
			options: "Company 1\nCompany 2",
			on_change: handle_company_change(),
		},
	],

	get_tree_nodes: "path.to.whitelisted_method.get_children",
	add_tree_node: "path.to.whitelisted_method.handle_add_account",

	fields: [
		{
			fieldtype: "Data",
			fieldname: "account_name",
			label: "New Account Name",
			reqd: true,
		},
		{
			fieldtype: "Link",
			fieldname: "account_currency",
			label: "Currency",
			options: "Currency",
		},
		{
			fieldtype: "Check",
			fieldname: "is_group",
			label: "Is Group",
		},
	],

	ignore_fields: ["parent_account"],

	menu_items: [
		{
			label: "New Company",
			action: function () {
				frappe.new_doc("Company", true);
			},
			condition: "frappe.boot.user.can_create.indexOf('Company') !== -1",
		},
	],

	onload: function (treeview) {},

	post_render: function (treeview) {},

	onrender: function (node) {},

	on_get_node: function (nodes) {},

	extend_toolbar: true,

	toolbar: [
		{
			label: "Add Child",
			condition: function (node) {
				return node && node.is_group;
			},
			click: function (node) {
				frappe.treeview_settings["Account"].add_node(node);
			},
			btnClass: "hidden-xs",
		},
	],
};
```

