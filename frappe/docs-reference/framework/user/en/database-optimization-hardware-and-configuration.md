---
title: "Database Optimization - Hardware and Configuration"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/database-optimization-hardware-and-configuration"
updated: "2026-05-10"
---

A major part of optimizing performance while using Frappe Framework is optimizing the performance of the database. Thankfully, the performance of MariaDB/MySQL is a well understood concept with many resources to understand it in depth. Frappe is no different from many other web apps that are built on the same database, so if you know how to optimize for MySQL, you already know how to do it when using Frappe Framework.

Architecture and Hardware 
-------------------------

We recommend separating the database server from the application server. The following are some reasons for this recommendation:

* Application server can often have load spikes and dynamic memory usage patterns. Hosting it next to Database server affects overall performance.
* Database like to have consistent availability of hardware resources to perform well. This includes access to as much RAM and IOPS available as possible.
* Database and Application server often benefit from different type of hardware tuning and configuration.

### CPU

We recommend starting with at least 2vCPU. Numbers of vCPU determines how much "true parallel" work your database server can perform. You should setup some monitoring on database server (see monitoring section below). When your utilization is constantly hitting 60% or stays above 50% for prolonged period then you might need to upgrade vCPU count to allow more parallel compute resources.

### RAM

Accessing data from disk is orders of magnitude slower than accessing it from memory. Databases use RAM for "Buffer Pool" which acts as cache for actual data on disk. A well tuned and well equipped database will not be accessing disk for reading data &gt;99% of the time. As your database grows and you need a lot of data accessible very fast then you might have to consider adding more RAM and reconfiguring the server to utilize available RAM.

We recommend starting with at least 8GB RAM.


&gt; Note: It is recommended to not rely on SWAP for database server. Databases already implement all the logic necessary to work with limited memory, adding swap just duplicates that effort. You should keep small amount of SWAP memory for safety but lower swappiness to minimum possible value.
&gt; 
&gt; 

### Disk and IOPS

Do not cheap out on disk storage and IOPS. Consider getting at least 3x storage than what's actually being used. Your database will naturally grow over time and you don't want to upgrade every time it runs out of disk. AWS for instance, also gives you more IOPS with additional storage. We recommend starting with ~2000-3000 IOPS and monitoring usage to check if you need more or can do with less.

Start with at least 50GB disk and consider ~3x of your current database size. E.g. If your database is 20 GB then consider getting a server with 60GB storage or attachable volume.

### Scaling resources

We recommend scaling vertically for as long as possible, roughly this means vertically scaling till at least 64vCPU/128GB RAM. You can use insights from monitoring setup to decide what component needs to be upgraded. Keep in mind that most cloud providers will bundle resources into "instances" so it's not straightforward to just upgrade one part of the system.

If you think you've hit the limit of what you can achieve with single machine then you can consider setting up a database replica. Frappe Framework can be configured to route all the heavy reads to a replica of the database to reduce load on the main server.

Configuration
-------------

Databases provide 100s of knobs out of the box for tweaking different parameters of database performance. It is essential to at least have the most important knobs tuned properly so you can maximize your hardware capabilities.

### Bufferpool - `innodb-buffer-pool-size = 5G`

The most important parameter you need to tweak is Bufferpool size. This also has the worst default configuration for historical reasons, so if it is left unconfigured, you're not utilizing your hardware at all.

Bufferpool as previously mentioned acts as a cache for data present on disk. The rule of thumb for size of Bufferpool is:


&gt; "Bufferpool size should fit your working set of data"
&gt; 
&gt; 

It's simple to state yet quite hard to quantify. Your "working set" of data is data that you access every day, data you want to access really fast and won't accept random slow downs for. Let's take example of ERPs to understand how to pick somewhat ideal bufferpool size and consequently RAM size.

1. Your site has database of 80GB.
2. This database is generated over 4 years.
3. You believe last year the DB size grew by 20GB and in ERPs mostly you're accessing 1 year's data for all kinds of reporting and validations.
4. So ideal bufferpool size to start with is 20GB.
5. Ideally, bufferpool should consume ~60% of RAM. So you should go for 20 / 0.6 ~= 33GB RAM.

You can setup monitoring on bufferpool usage and understand if you need more or less. Two most important metrics:

1. Bufferpool hit ratio: If it's more than 99% then most likely you do not need to add more bufferpool size.
2. Utilization: If your utilization is not close to 95%-100% then you definitely don't need to add more bufferpool.

Bufferpool cache fills up over time, so you need to measure this after few days of operation. You can type `SHOW ENGINE INNODB STATUS` to find these stats. This gives a lot of output but here is the important part:


```
----------------------
BUFFER POOL AND MEMORY
----------------------
Buffer pool size   2790528
Free buffers       1594
Buffer pool hit rate 999 / 1000
  

```
### Other parameters

Following is the configuration we use at Frappe. You can start with this and tweak certain parameters. Most important parameters are explained in some more detail below.

* `innodb-flush-method = O_DIRECT`: Bypass certain operation and do "direct IO".
* `innodb-flush-log-at-trx-commit = 1`: Improves durability of system by writing to log at every commit. Do not compromise on this durability for small gain in performance.
* `innodb-file-per-table = 1` : Create one file for each table.
* `slow-query-log = 1` and `slow-query-log-file = /var/lib/mysql/mysql-slow.log`: Store any query that runs for too long in log file. This is useful for retrospectively finding out which queries should be optimized.
* `query-cache-type = 0` and `query-cache-size = 0`: This disables query cache, which despite the name is now widely considered to be detrimental to performance.


```
[mysqld]
# GENERAL #
default-storage-engine          = InnoDB

# MyISAM #
key-buffer-size                 = 32M
myisam-recover                  = FORCE,BACKUP

# SAFETY #
max-allowed-packet              = 256M
max-connect-errors              = 1000000
innodb                          = FORCE

# DATA STORAGE #
datadir                         = /var/lib/mysql/

# BINARY LOGGING #
log-bin                         = /var/lib/mysql/mysql-bin
log_bin_index                   = /var/lib/mysql/mysql-bin.index
expire-logs-days                = 14
sync-binlog                     = 1

# CACHES AND LIMITS #
tmp-table-size                  = 32M
max-heap-table-size             = 32M
query-cache-type                = 0
query-cache-size                = 0
max-connections                 = 500
thread-cache-size               = 50
open-files-limit                = 65535
table-definition-cache          = 4096
table-open-cache                = 10240
tmp-disk-table-size             = 5120M
max-statement-time              = 10800

# INNODB #
innodb-flush-method             = O_DIRECT
innodb-log-files-in-group       = 2
innodb-log-file-size            = 512M
innodb-flush-log-at-trx-commit  = 1
innodb-file-per-table           = 1
# NOTE: This has to be configured based on RAM. Consider ~60% of available RAM. This example assumes 8GB RAM.
innodb-buffer-pool-size         = 4.8G
innodb-file-format              = barracuda
innodb-large-prefix             = 1
innodb-old-blocks-time          = 5000
collation-server                = utf8mb4_unicode_ci
character-set-server            = utf8mb4
character-set-client-handshake  = FALSE
max_allowed_packet              = 512M

# LOGGING #
log-error                       = /var/lib/mysql/mysql-error.log
log-queries-not-using-indexes   = 0
slow-query-log                  = 1
slow-query-log-file             = /var/lib/mysql/mysql-slow.log

[mysql]
default-character-set           = utf8mb4

[mysqldump]
max_allowed_packet              = 512M
  

```
Monitoring
----------

Frappe doesn't have any specific monitoring tool for MariaDB, we recommend setting up observability tools like Prometheus with Grafana for dashboards.

* Inbuilt slow query log: See how often slow queries get logged and find most common slow queries using tool like `pt-query-digest` from Percona toolkit.
* Set up Prometheus and Grafana with following exporters:


	+ [Node Exporter](https://github.com/prometheus/node_exporter) - Provides overall system stats. Useful for monitoring CPU, RAM and I/O.
	+ [MySQLD Exporter](https://github.com/prometheus/mysqld_exporter) - Provides ton of useful metric from MariaDB's database engine.
	+ [PMM](https://docs.percona.com/percona-monitoring-and-management/setting-up/client/mysql.html) - Percona's toolkit with pre-built dashboards.

We consider following metrics worth tracking:

1. CPU usage - Constant near 100% usage implies you might need more CPU power to handle the load.
2. RAM - RAM usage of well configured database will hover around 90%. Usage close to 100% means you're likely to swap or crash the system. Usage significantly less than 90% implies you are not utilizing all available RAM for bufferpool cache.
3. Disk I/O - Once database server has sufficiently warmed up, disk reads should be minimal. All read load will get served up from bufferpool and only updates need to be written to the disk. If you see a lot of disk I/O that could imply insufficient bufferpool size or queries that require temporary files to be written on disk.
4. "InnoDB row reads" - A sudden increase in number of reads might imply increase in traffic or introduction of unoptimized query.
5. "BP Miss ratio" - Should be &lt;1% for the most part. If it's high then your bufferpool size is likely not adequate.
6. "Innodb Row Lock Wait Load" - A high lock wait load implies you have contention problem where multiple workers are trying write to same resources but getting blocked. Typical solution to this problem is to queue work instead of doing it in parallel. There might also be unoptimized queries causing locks to be held for long durations.
7. "InnoDB Buffer Pool LRU Sub-Chain Churn" - Bufferpool maintains list of database pages as an approximate LRU. Activities like logical backups can potentially read entire database on disk into bufferpool causing eviction of most used pages. It's ideal to take backups during non-working hours to avoid this.

### Further reading and references

* &lt;https://mariadb.com/kb/en/innodb-system-variables/&gt;
* &lt;https://mariadb.com/kb/en/server-system-variables/&gt;
* &lt;https://www.percona.com/blog/innodb-performance-optimization-basics-updated&gt;
* &lt;https://dev.mysql.com/doc/refman/8.0/en/innodb-buffer-pool.html&gt;
* &lt;https://docs.percona.com/percona-toolkit/&gt;

  


