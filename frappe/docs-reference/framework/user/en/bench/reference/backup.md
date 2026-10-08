---
title: "bench backup"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/bench/reference/backup"
updated: "2026-02-17"
---

Usage
-----


```
bench backup [OPTIONS]
```
Description
-----------

Backup sites specified. Executing the vanilla command will create a database dump, compress it and save the data under the default backup location `./sites/{site}/private/backups`.

In case a current site is set, simply running `bench backup` command will backup that site.

Options
-------

* `--backup-path` Set path for saving all the files in this operation
* `--backup-path-db` Set path for saving database file
* `--backup-path-conf` Set path for saving config file
* `--backup-path-files` Set path for saving public file
* `--backup-path-private-files` Set path for saving private file
* `--exclude`, `-e` Specify the DocTypes to not backup seperated by commas
* `--only`, `--include`, `-i` Specify the DocTypes to backup seperated by commas

Flags
-----

* `--ignore-backup-conf` Ignore excludes/includes set in config
* `--with-files` Take backup with private and public files
* `--compress` Compress private and public files
* `--verbose` Add verbosity

Examples
--------

1. Backing up with the site's private and public files.


```
bench --site {site} backup --with-files
```
2. Compress the public and private files (if required). This saves the file under a `tgz` format instead of the default `tar` format.


```
bench --site {site} backup --with-files --compress
```
3. Change the path where the files backed up will be saved.


```
bench --site {site} backup --backup-path {backup_path}
```
4. Change the path for a specific backup file. For each unspecified option, the respective file will be saved in the default location.


```
bench --site {site} backup --with-files
   --backup-path-conf {conf_path}
   --backup-path-db {db_path}
   --backup-path-files {files_path}
   --backup-path-private-files {private_path}
```
5. Add verbosity for the various stages managed internally via the Bench CLI.


```
bench --site {site} backup --verbose
```
6. Backup only certain doctypes on the site.


```
bench --site {site} backup --only 'ToDo,Note,Task,Project,Sales Invoice'
```
7. Backup all tables except certain doctypes.


```
bench --site {site} backup --exclude 'Error Log,Access Log,Activity Log,Version'
```
8. Backup complete site ignoring the `frappe.conf.backup.*` values if specified.


```
bench --site {site} backup --ignore-backup-conf
```

If the backup process happens to fail (any exception is raised) - the files will be deleted to avoid using extra disk space.

