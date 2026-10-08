---
title: "Where Do I Find Standard Print Formats\n"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/guides/reports-and-printing/where-do-i-find-standard-print-formats"
updated: "2026-02-17"
---

Standard Print formats are **auto generated** from the layout of the DocType. You can customize the standard format by

#### 1\. Customizing Standard Print

Go to **Setup > Customize > Customize Form View** and you can:

1. Re-arranging fields by dragging and dropping
2. Add static elements by adding **HTML** type fields and adding your HTML in **Options**
3. Hiding fields by setting the **Print Hide** property

#### 2\. Creating new layouts based on Print Formats

As there are not templates that are generated for standard Print Formats, you will have to create new templates from scratch using the [Jinja Templating Language](http://jinja.pocoo.org/) via

**Setup > Printing and Branding > Print Format**

1. [See Print Format help](https://docs.erpnext.com/docs/v14/user/manual/en/customize-erpnext/print-format).
2. You can use the [Bootstrap CSS framework](http://getbootstrap.com) to layout your print formats

**Tip: You can import [Standard Template macros](https://github.com/frappe/frappe/blob/develop/frappe/templates/print_formats/standard_macros.html) for building your print formats.**

Example, adding the standard header:

```
{%- from "templates/print_formats/standard_macros.html" import add_header -%}

{{ add_header() }}
```