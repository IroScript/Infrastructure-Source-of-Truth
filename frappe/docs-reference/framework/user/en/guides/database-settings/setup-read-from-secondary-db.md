---
title: "Setup read operations from slave/secondary mysql system\n"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/guides/database-settings/setup-read-from-secondary-db"
updated: "2026-09-18"
---

In normal, the system does read and write operations on the same database. As data size increases or the number of concurrent activities increases, you may start facing a lag in operations.

One immediate solution to avoid such delay is, separate out the read and write activities, i.e. read all data from replica / secondary database and write all information to master / primary database.

Now, in frappe, you can split read and write activities between master and replica.

## Steps to setup readonly environment

1. **Pre-requisites** :  
You should have setup for [MariaDB Master-Slave](https://mariadb.com/kb/en/library/setting-up-replication/) or [Cluster](https://mariadb.com/kb/en/library/getting-started-with-mariadb-galera-cluster/) environment.
2. **Configurations for read-only replica** :

  In your site\_config.json, add following keys to enable read from replica / secondary system.
  ```
  ...
  "read_from_replica" : 1/0 # to enable disable read from replica
  "different_credentials_for_replica" : 1/0 #if database creadetials are different on replica then set 1 else 0
  "replica_host" : "IP address for replica" ,
  "replica_db_port" : "Replica DB port",
  "replica_db_name" : "Replica DB name",
  "replica_db_password" : "Replica DB password",
  ...
  ```

  **Note**: If you have enabled MariaDB master-replica environment, then DB name and DB password are same on both.
3. [Grant access permissions](https://dev.mysql.com/doc/refman/8.0/en/grant.html) for master host on slave / secondary system.
4. **Route your reads to the replica with** `frappe.read_only`

  Setting `read_from_replica` does **not** automatically send every query to the replica. Frappe only switches to the replica connection inside functions decorated with `@frappe.read_only()`. Everything else keeps using the primary.

  Frappe already uses this decorator for its own heavy read paths: list views (`frappe.desk.reportview`), notification counts, and the report runner (`frappe.desk.query_report.run`). This means **Script Reports and Query Reports already run on the replica** without any change to their code.

  To offload your **own** slow whitelisted endpoints, add the decorator yourself:
  ```
  import frappe
  
  
  @frappe.whitelist()
  @frappe.read_only()
  def get_sales_summary(from_date, to_date):
      return frappe.db.sql(
          """
          select customer, sum(grand_total) as total
          from `tabSales Invoice`
          where docstatus = 1 and posting_date between %s and %s
          group by customer
          """,
          (from_date, to_date),
          as_dict=True,
      )
  ```
  ### How it works
  - When `read_from_replica` is enabled, the decorator opens a connection to the replica, swaps it in as `frappe.db` for the duration of the function, and restores the primary connection afterwards.
  - When `read_from_replica` is disabled, the decorator is a no-op, so it is safe to leave in place on every site.
  - Nested `@frappe.read_only()` calls reuse the existing replica connection; the connection is only swapped once.
  - Behaviour is the same on version 15 and version 16.
  - Because of replication lag, data on the replica can be a few moments behind the primary. Only decorate functions that can tolerate slightly stale data.
  > **Do not write inside a read-only function.** Any `INSERT`, `UPDATE`, `frappe.get_doc(...).save()` or similar call will go to the replica and fail. If a read-only function must perform a small write (for example, logging), wrap that part in a separate function decorated with `@frappe.write_only()`, which temporarily switches back to the primary connection.
  ```
  @frappe.write_only()
  def log_report_access(report_name):
      frappe.get_doc({"doctype": "Access Log", "report_name": report_name}).insert()
  ```
  ### What is a good candidate?
  - Whitelisted API methods that only read data
  - Dashboard and portal endpoints that scan large tables
  - Exports, aggregations and analytics queries

  Leave transactional endpoints (anything that creates, updates, submits or cancels documents) on the primary.