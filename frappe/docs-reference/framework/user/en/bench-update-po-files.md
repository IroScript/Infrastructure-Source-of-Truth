---
title: "bench<strong> </strong>update-po-files"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/bench-update-po-files"
updated: "2026-02-17"
---

### **Usage**


```
bench update-po-files [OPTIONS]
```
### **Prerequisites**

Existing POT file and PO files in your app's `locale` directory.

**Description**

This command syncs your existing translation files with the existing POT file, which holds all translatable strings. It removes all outdated strings and adds new ones.

You'll want to run this command after you regenerated the POT file with translatable strings. In case you are using a dedicated platform for translation management, the platform might also take care of this step for you, so that you won't need this command.

### **Options**

* `--app` This parameter let's you specify an app, in case you want to update the PO files for one app only. Default: all apps.
* `--locale` This parameter let's you specify a locale, in case you want to update the PO file for one locale only. Default: all locales.

### **Examples**

Sync ERPNext's translatable strings with the file holding german translations.


```
bench update-po-files --app erpnext --locale de
```
This reads translations from `apps/erpnext/erpnext/locale/de.po` and translatable strings from `apps/erpnext/erpnext/locale/main.pot`. The result is saved to `apps/erpnext/erpnext/locale/de.po`.

  


