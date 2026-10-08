---
title: "bench compile-po-to-mo"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/bench-compile-po-to-mo"
updated: "2026-02-17"
---

### Usage


```
bench compile-po-to-mo [OPTIONS]
```
### Prerequisites

Existing PO files in your app's `locale` directory, holding translations for at least one language.

### **Description**

The PO files hold translations in human-readable format. Before they can be used by the application, translations need to be compiled to binary files (ending with MO). The binary file is stored in the `sites/assets/locale` folder of your bench.

For efficiency, this skips compilation if there are existing MO files which are newer than the PO files.

This command is automatically executed along with `bench build` and `bench update`. You can run it explicitly in your development environment, when you just added some translations and want to see the result in the UI.

### **Options**

* `--app` This parameter let's you specify an app, in case you want to update the PO files for one app only. Default: all apps.
* `--locale` This parameter let's you specify a locale, in case you want to update the PO file for one locale only. Default: all locales.
* `--force` Force re-compilation, even if the PO files didn't change.

### **Examples**

Compile ERPNext's german translations.


```
bench compile-po-to-mo --app erpnext --locale de
```
This reads translations from `apps/erpnext/erpnext/locale/de.po` and compiles them to binary. The result is saved to `sites/assets/locale/de/LC_MESSAGES/erpnext.mo`.

