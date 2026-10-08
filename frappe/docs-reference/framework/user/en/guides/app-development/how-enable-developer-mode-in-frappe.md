---
title: "How to Enable Developer Mode in Frappe"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/guides/app-development/how-enable-developer-mode-in-frappe"
updated: "2026-02-17"
---

When you are in application design mode and you want the changes in your DocTypes, Reports etc to affect the app repository, you must be in **Developer Mode**.

To enable developer mode, update the `site_config.json` file of your site in the sites folder:


```
frappe-bench/sites/{your site}/site_config.json
```
Inside the `frappe-bench` folder, run


```
bench set-config -g developer_mode 1
```
OR, manually, write `"developer_mode": 1` inside the `{ .. }` of `site_config.json`


```
{
  "developer_mode": 1,
  ...
}
```
After setting developer mode, clear the cache:


```
bench --site {your site} clear-cache
```
Some apps might require additional dependencies to build and test in development mode. Install them using bench:


```
bench setup requirements --dev
```
