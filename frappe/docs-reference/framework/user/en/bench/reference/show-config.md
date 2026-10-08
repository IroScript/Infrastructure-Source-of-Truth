---
title: "bench show-config"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/bench/reference/show-config"
updated: "2026-02-17"
---

Usage
-----


```
bench show-config [OPTIONS]
```
Description
-----------

The applied configuration for your sites gets applied as a combination of the bench directory's `common_site_config.json` and the site's own `site_config.json`. Bench provides an interface to view the applied `frappe.conf` values for your sites. You may choose to access this information in tabular or JSON formats.

To read more about site configuration and understanding key precedence, refer to the docs [here](/framework/v14/user/en/basics/site_config).

Flags
-----

* `-f`, `--format` Choose the format for listing apps installed on the specified site, options being "text" and "json". Default is "text".

Examples
--------

1. Show site config for all sites in JSON format.


```
bench --site all show-config -f json
```
2. Show the site config in tabular form.


```
bench --site {site} show-config --format text
```

```
bench --site {site} show-config -f text
```

```
bench --site {site} show-config
```
