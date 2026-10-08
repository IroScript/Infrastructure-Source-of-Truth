---
title: "Zero* downtime migrations"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/zero*_downtime_migrations"
updated: "2026-09-18"
---

Zero\* downtime migrations let the site run in read-only mode during the site upgrade process. This means your static site, dynamic pages that only need to read data can continue to work without any noticeable difference. Any actions that require writing to the database will be disabled and only resume when the upgrade is finished.

### How does this work

Zero downtime migration utilizes one of the following two means to enable read-only mode:

1. Using read-replicas.
2. Using "read only transactions" which are provided by databases.

In either case, writes on your database are disabled until maintenance mode is lifted.

Both web pages and Desk will show persistent read-only warnings during updates. All forms are also made read-only so you can not modify any data.

### Caveats to keep in mind

- Not all apps automatically support this feature. They might behave erratically if they are not designed to work in read-only mode.
- During database schema updates, the client-side app is updated so you'll occasionally face some glitches. These can not be fully avoided; the intent behind this feature is only to reduce the impact of downtime.

### Enabling Read Only Mode during upgrades

1. \[Optional\] - Set up a read replica by following the [replication guide](https://frappeframework.com/docs/v14/user/en/guides/database-settings/setup-read-from-secondary-db)
2. Edit your site config to enable this feature. `bench --site develop set-config allow_reads_during_maintenance 1`

### Supporting read-only mode in your app

If you are an app developer and want to add support for this feature in your app, then you need to modify your app

#### Server-side changes

You can use `frappe.flags.read_only` to disable or modify behaviour in read-only mode.

Example: Logging page visits

```
@frappe.whitelist()
def log_visit():
    if frappe.flags.read_only:
        return

    doc = frappe.new_doc("Doc Visit")
    doc.insert()

```

#### Jinja / Client-side page changes

You should ideally update the UI to indicate that your app is in read-only mode and write actions cannot be performed right now.

Website context includes `read_only_mode` key in context by default; you can use this to add warning or toggle features on your pages conditionally. Example:

```
<!-- some html page -->
{% if read_only_mode %}
    <div class="alert">Site is running in read only mode. Full functionality will be restored soon.</div>
{% endif %}
<!-- other content -->

```