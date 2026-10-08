---
title: "bench set-config"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/bench/reference/set-config"
updated: "2026-09-21"
---

## Usage

```bash
bench set-config [OPTIONS] KEY VALUE
```

## Description

Bench provides a wrapper command to insert or update values in the site config  
files. You can update values in your site's `site_config.json`, along with the  
bench directory's `common_site_config.json` through the same command.

To read more about site configuration and understanding key precedence, refer to  
the docs [here](/framework/v14/user/en/basics/site_config).

## Flags

- `-g`, `--global` Set value in the Bench's Common Site Config
- `-p`, `--parse` Parse given value instead of string. You can use this to set  
 dict and list values. This was `--as-dict` in earlier versions.



> ###### **Note:** `bench set-config` recognizes lowercase `true` and `false` as boolean values. It also recognizes `1` and `0`, which are stored as integers. Although many boolean configuration flags treat `1` and `0` like `true` and `false`, lowercase `true` and `false` are recommended because they clearly express the intended type. Avoid uppercase `True` and `False` unless using `--parse`, as they may otherwise be stored as strings.

## Examples

1. Enable tests for given site.
  ```bash
  bench --site {site} set-config allow_tests true
  ```
2. Enable tests for all sites.
  ```bash
  bench --site all set-config allow_tests true
  ```

  Using the above command, each site's `site_config.json` will have the  
  key-value `"allow_tests": true`. This allows running tests on all of the  
  sites.
  ```bash
  bench set-config -g allow_tests true
  ```

  Using the above command, the bench's `common_site_config.json` will have the  
  key-value `"allow_tests": true`. This will allow each site on the bench to  
  have tests run unless they have a value defined for the same key in their  
  `site_config.json`.
3. Set a dict value in your site's `frappe.conf`
  ```bash
  bench --site {site} set-config backup '{"includes": ["Not", "ToDo"]}' --parse
  ```

  You can now access the list in code as `frappe.conf.backup.get("includes")`.