---
title: "Profiling and Monitoring"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/profiling"
updated: "2026-02-17"
---

Recorder - SQL profiler
-----------------------

Frappe Recorder is a profiling tool built into the Frappe framework designed to capture all requests and background jobs, along with the SQL queries executed, corresponding stack traces.

Example use case: You've noticed that a certain DocType is taking too much time to save and you believe that SQL queries might be a bottleneck. In such a case starting recorder and then submitting your document will give you complete capture of all the queries that were fired for saving the document.

1. Login as Administrator. Open Recorder from Awesomebar and click on "Start".
2. You'll be asked to configure recording. Pick appropriate options and start recording. ![](/files/AiAZ6TW.png)
3. Perform the actions you want to profile (preferably in another tab.)
4. Once you've captured enough information, go to the recorder again and stop recording.

You will now see a list of all the requests or jobs that were processed and recorded. You can sort them by various columns to identify problematic requests.

![Screenshot 2023-09-25 at 8.53.42 PM](/files/Screenshot 2023-09-25 at 8.53.42 PM.png "Screenshot 2023-09-25 at 8.53.42 PM.png")  


Click on a row to open the request for extra information. Following information is available in the capture:

1. path - requested path or job name e.g. `/app`
2. cmd - dotted path to the method (empty for background jobs).
3. time - time at which request was created.
4. duration - duration for completing the request (see implementation note below).
5. number of queries - Number of SQL queries executed for fulfilling the request.
6. Time in queries - Time taken in SQL queries.
7. Request headers - HTTP headers received with the request (empty for background jobs).
8. Form Dict - form data received with the request (empty for background jobs).
9. SQL queries - table of all SQL queries that ran.

![Screenshot 2023-09-25 at 8.46.24 PM](/files/Screenshot 2023-09-25 at 8.46.24 PM.png "Screenshot 2023-09-25 at 8.46.24 PM.png")  


To know more about a particular query click on row to expand additional information. This includes the duration of the query, stack trace and SQL's `EXPLAIN` output for that query.

![Screenshot 2023-09-25 at 8.47.28 PM](/files/Screenshot 2023-09-25 at 8.47.28 PM.png "Screenshot 2023-09-25 at 8.47.28 PM.png")  



> Implementation note: Recorder adds sizable overhead for capturing the details, hence overall duration is not representative of real-world performance. Query time however is very close to real-world performance.
> 
> 

### Importing &amp; Exporting Frappe Recorder Captures

You can export recorder captures and import them on another site for further analysis.

1. Go to recorder page. Once you've recorded click on the Menu (three dots) > Export.
2. This will download a JSON file containing captured data. To view this on another site you can click on Import and select the JSON file to view the captured data.

### Python profiling using Recorder

In addition to capturing SQL queries, the recorder can also run the inbuilt Python profiler "cProfile" to give you profiling output of running Python functions. You can enable this option while starting the recorder.

![](/files/IFovCUl.png)  



> If you enable cProfiler in recorder it will add even higher overhead during recording. Make sure to disable it immdiately after debugging. You can also filter the request/jobs to avoid hindering production traffic.
> 
> 

Profiling functions using bench
-------------------------------

Bench's `execute` command runs a dotted path to method and it also supports profiling.


```
▶ bench --site [sitename] --profile execute erpnext.projects.doctype.task.task.set_tasks_as_overdue
  

```
You should be able to run most commands you can run via console with `execute` now, including *db* methods.


```
▶ bench --site [sitename] execute frappe.db.get_database_size
6784
  

```
Frappe Monitor
--------------

Monitor logs request and job metadata. To enable this feature set `"monitor": 1` in your site config.

Collected data is buffered in redis cache and periodically moved to `monitor.json.log` file in `logs` directory with a scheduled job `frappe.monitor.flush`.


```
{
    "duration": 807142,
    "request": {
        "ip": "127.0.0.1",
        "method": "GET",
        "path": "/api/method/frappe.realtime.get_user_info",
        "response_length": 9687,
        "status_code": 500
    },
    "site": "frappe.local",
    "timestamp": "2020-03-05 09:37:17.397884",
    "transaction_type": "request",
    "uuid": "83be6a4c-27a1-497a-9ce6-c815bca4e420"
}
  

```

```
{
    "duration": 1364,
    "job": {
        "method": "frappe.ping",
        "scheduled": false,
        "wait": 90204
    },
    "site": "frappe.local",
    "timestamp": "2020-03-05 09:37:40.124682",
    "transaction_type": "job",
    "uuid": "8225ab76-8bee-462c-b9fc-a556406b1ee7"
}
  

```
Background Jobs monitoring
--------------------------

Frappe uses RQ (Redis Queue) for asynchronously executing long tasks in background. You can monitor RQ using these inbuilt virtual doctypes:

### 1. RQ Worker - Monitoring a background worker

RQ worker doctype shows all background workers consuming the background jobs queue on your site. It also contrains basic statistics about the worker like name, timing, successful and failed jobs count and currently status.

### 2. RQ Job - Monitoring and controlling background jobs.

RQ Job is a virtual doctype which provides information about all background jobs. You can filter jobs by queue and status.

![rq job list](/private/files/rq_job_list.png)  


Form view of RQ job shows all information about the job.

![rq job](/private/files/rq_job.png)  


Debugging Stuck Process
-----------------------

If you believe any worker process is stuck you can send `SIGUSR1` signal to it and it will print the current stack of all of its threads to `stderr`.

Example: `kill -SIGUSR1 <PID>`

In typical deployments, you can find output written to stderr in log files:

* Web workers - `bench/logs/web.error.log`
* Background workers - `bench/logs/worker.error.log`
* Scheduler - `bench/logs/schedule.error.log`

Monitoring General Health of Services
-------------------------------------

"System Health Report" can be used to quickly check system health. This includes, but not limited to:

* Background Jobs
* Scheduler
* Database
* Cache
* Emails
* Error logs
* Storage
* Backups
* Users

Search "System Health Report" in Awesomebar to view this report. 

