---
title: "bench generate-pot-file"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/bench-generate-pot-file"
updated: "2026-02-17"
---

### Usage


```
bench generate-pot-file [OPTIONS]
```
### Description

This generates a template file for translations, holding all translatable strings of an app (but no translations). The template file will be written to the file `[app_module]/locale/main.pot`.

For many of our apps, this command is run automatically on a regular basis via *GitHub Actions*.

### Options

* `--app` This parameter let's you specify an app, if you want to generate the POT file for one app only. Default: all apps.

### Examples

Re-generate the POT file for ERPNext:


```
bench generate-pot-file --app erpnext
```
This will extract all translatable strings from `apps/erpnext` and write them to `apps/erpnext/erpnext/locale/main.pot`

