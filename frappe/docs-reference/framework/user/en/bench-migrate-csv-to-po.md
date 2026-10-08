---
title: "bench migrate-csv-to-po"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/bench-migrate-csv-to-po"
updated: "2026-02-17"
---

### **Usage**


```
bench migrate-csv-to-po [OPTIONS]
```
### **Prerequisites**

Please make sure your app has a POT file already. If not, you can [generate one](https://frappeframework.com/docs/user/en/bench-generate-pot-file).

**Description**

This command reads in your existing translations from CSV files, matches them with the existing POT file and writes the result into`[app_module]/locale/[locale].po`.

You will only need this command while switching from the old translation system to the new one.

### **Options**

* `--app` This parameter let's you specify an app, in case you want to migrate translations for one app only. Default: all apps.
* `--locale` This parameter let's you specify a locale, in case you want to migrate translations for one locale only. Default: all locales.

### **Examples**

Migrate ERPNext's german translations from CSV to PO.


```
bench migrate-csv-to-po --app erpnext --locale de
```
This reads translations from `apps/erpnext/erpnext/translations/de.csv` and translatable strings from `apps/erpnext/erpnext/locale/main.pot`. The result is saved to `apps/erpnext/erpnext/locale/de.po`. If you're happy with the result, you can now delete the CSV file.

