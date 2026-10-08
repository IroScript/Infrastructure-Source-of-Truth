---
title: "Custom Module Icon"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/guides/app-development/custom-module-icon"
updated: "2026-02-17"
---


If you want to create a custom icon for your module, you will have to create an SVG file for your module and set the path to this file in the `desktop/config.py` of your app.  


This icon is loaded via AJAX first time, then it will be rendered.

Example:

```py
from frappe import _

 def get_data():
    return {
     "Frappe Apps": {
     "color": "orange",
     "icon": "assets/frappe/images/frappe.svg",
     "label": _("Frappe.io Portal"),
     "type": "module"
    }
  }
 ```

> PS: A great place to buy SVG icons for a low cost is the awesome [Noun Project](http://thenounproject.com/)


