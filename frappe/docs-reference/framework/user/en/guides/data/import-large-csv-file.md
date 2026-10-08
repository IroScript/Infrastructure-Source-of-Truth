---
title: "Bulk Data Import Guide"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/guides/data/import-large-csv-file"
updated: "2026-02-17"
---

When importing very large datasets (e.g., more than 5,000 documents), it's recommended to use the command-line utility `bench data-import` instead of the web interface. This approach avoids web request timeouts and ensures a more reliable import process.

## Example Command:

> `bench --site test.erpnext.com data-import ~/Downloads/Activity_Type.csv`

## Command Help

> `bench data-import --help`

### Command Usage: 
> `bench  data-import [OPTIONS]`

This command allows bulk import of documents into your site from CSV or XLSX files.

### Options:
| Option|Description |
|----|--|
| `--file FILE` | Path to import file (.csv, .xlsx).Consider that relative paths will resolve from 'sites' directory *[required]* |
| `--doctype TEXT` | DocType target to import *[required]* |
| `--type [Insert\|Update]` | Insert New Records or Update Existing Records |
| `--submit-after-import` | Submit document after importing it |
| `--mute-emails` | Mute emails during import |
| `--help` | Show this message and exit. |

### Note:
* The `--file` option can be omitted if the file path is provided as a positional argument.



