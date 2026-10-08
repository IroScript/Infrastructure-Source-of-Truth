---
title: "Apps Page"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/apps-page"
updated: "2026-02-17"
---

The Apps Page provides a quick navigation interface for accessing all the apps installed on your site. By default, all Frappe apps installed on your site will appear on this page.

![](/files/Apps%20Page.png)

## How can we show our custom apps on apps page?

You can include it by adding the following configuration in your app’s hooks.py. Below is the example of Frappe CRM app.

Here `has_permission` option is used to show/hide app icon based on app based business logic. E.g. Hide icon if user is a Website User.

```Python
# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [{
    "name": "crm",
    "logo": "/assets/crm/logo.png",
    "title": "CRM",
    "route": "/crm",
    "has_permission": "crm.api.check_app_permission"
}]
```

> It is supported in v15 and above

## Setting a default app

You can configure a default app, which means users will be taken directly to that app upon logging into the site. If no default app is set, users will see the Apps Page by default.

### Default app configuration can be done at two levels:
1. User Level: Allows individual users to set their preferred default app.
	![](/files/SetAsDefault.png)
    ![](/files/UserLevel.jpeg)
2.	System Level: Sets a global default app for all users.
    ![](/files/SystemLevel.png)