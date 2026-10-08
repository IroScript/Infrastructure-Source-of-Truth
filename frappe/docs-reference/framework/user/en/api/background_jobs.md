---
title: "Background Jobs"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/api/background_jobs"
updated: "2026-02-17"
---

Frappe ships with a system for running jobs in the background. It is implemented by using the [schedule package](https://pypi.org/project/schedule/) and a simple long-running infinite [while loop](https://github.com/frappe/frappe/blob/d0efa8e3ff734268a30b4804427641d2a5ed643e/frappe/utils/scheduler.py#L36-L46).

You can enqueue a python method to run in the background by using the `frappe.enqueue` method:


```
def long_running_job(param1, param2):
    # expensive tasks
    pass

# directly pass the function
frappe.enqueue(long_running_job, queue='short', param1='A', param2='B')

# or pass the full module path as string
frappe.enqueue('app.module.folder.long_running_job', queue='short', param1='A', param2='B')
```
Here are all the possible arguments you can pass to the `enqueue`:


```
frappe.enqueue(
    method, # python function or a module path as string
    queue="default", # one of short, default, long
    timeout=None, # pass timeout manually
    is_async=True, # if this is True, method is run in worker
    now=False, # if this is True, method is run directly (not in a worker) 
    job_name=None, # specify a job name
    enqueue_after_commit=False, # enqueue the job after the database commit is done at the end of the request
    at_front=False, # put the job at the front of the queue
    **kwargs, # kwargs are passed to the method as arguments
)
```
You can also enqueue a [Document](https://frappeframework.com/docs/v14/user/en/api/document) method by using `frappe.enqueue_doc`:


```
frappe.enqueue_doc(
    doctype,
    name,
    "do_something", # name of the controller method
    queue="long",
    timeout=4000,
    param="value"
)
```
Queue
-----

There are 3 default queues that are configured with the framework: `short`, `default`, and `long`. Each queue has a default timeout as follows:

* short: 300 seconds
* default: 300 seconds
* long: 1500 seconds

You can also pass a custom timeout to the `enqueue` method.

### Custom Queues

You can add custom queues by configuring them in `[common_site_config.json](https://frappeframework.com/docs/v14/user/en/basics/site_config#common-site-config)`:


```
{
    ...
    "workers": {
        "myqueue": {
            "timeout": 5000, # queue timeout
            "background_workers": 4, # number of workers for this queue
        }   
    }
}
```
Workers
-------

By default Frappe sets up 3 worker types for consuming from each queue. The default configuration looks like this:


```
bench worker --queue short
bench worker --queue default
bench worker --queue long
```
In production these 3 worker processes are replicated to configured number of background workers to handle higher workloads.

NOTE: This way of mapping workers to single queue is just a convention and it's not necessary to follow it.

### Multi-queue consumption

You can specify more than one queue for workers to consume from by specifying a comma separate string of queue names.

Example: If you wanted to combine short and default workers and only use two types of workers instead of default configuration then you can modify your worker configuration like this:


```
bench worker --queue short,default
bench worker --queue long
```
NOTE: The examples shown here are for Procfile format but they can be applied to supervisor or systemd configurations easily too.

### Burst Mode using `--burst`


```
bench worker --queue short --burst
```
This command will spawn a tempoary worker that will start consuming short queue and quit once queue is empty. If you periodically need higher amount of workers then you can use your OS's crontab to setup burst workers at specific times.

Scheduler Events
----------------

You can use Scheduler Events for running tasks periodically in the background using the `scheduler_events` hook.

**app/hooks.py**


```
scheduler_events = {
    "hourly": [
        # will run hourly
        "app.scheduled_tasks.update_database_usage"
    ],
}
```
**app/scheduled_tasks.py**


```
def update_database_usage():
    pass
```

> After changing any scheduled events in hooks.py, you need to run bench migrate for changes to take effect.
> 
> 

### Available Events

* `hourly`, `daily`, `weekly`, and `monthly`

These events will trigger every hour, day, week, and month respectively.
* `hourly_long`, `daily_long`, `weekly_long`, `monthly_long`

Same as above but these jobs are run in the [long worker](https://frappeframework.com/docs/v14/user/en/basics/directory-structure#worker_long) suitable for long-running jobs.
* `all`

The `all` event is triggered every 4 minutes. This can be configured via the `scheduler_interval` key in [common_site_config.json](https://frappeframework.com/docs/v14/user/en/basics/sites#scheduler_tick_interval)
* `cron`

A valid cron string that can be parsed by [croniter](https://pypi.org/project/croniter/).

Usage Examples:


```
scheduler_events = {
    "daily": [
        "app.scheduled_tasks.manage_recurring_invoices"
    ],
    "daily_long": [
        "app.scheduled_tasks.take_backups_daily"
    ],
    "cron": {
        "15 18 * * *": [
            "app.scheduled_tasks.delete_all_barcodes_for_users"
        ],
        "*/6 * * * *": [
            "app.scheduled_tasks.collect_error_snapshots"
        ],
        "annual": [
            "app.scheduled_tasks.collect_error_snapshots"
        ]
    }
}
```


Configurable Scheduler Events
----------------

On scenarios that require a user configurable trigger interval, Create a `Scheduler Event` record and create a `Scheduled Job Type` entry against that record. This doesn't require `scheduler_event` hook.

Example:
```
# Create `Scheduler Event` record
sch_eve = frappe.new_doc("Scheduler Event")
sch_eve.scheduled_against = "Process Payment Reconciliation"
sch_eve.save()

# Create `Scheduled Job Type`
job = frappe.new_doc("Scheduled Job Type")
job.frequency = "Cron"
job.scheduler_event = sch_eve.name
job.cron_format = "0/5 * * * *"     # runs every five minutes
job.save()
```

The `Scheduled Job Type`s trigger interval can be modified later, which persits across bench migration.

> The jobs triggered by scheduler are run by **Administrator** user. This also means any docs you create via scheduled job will be owned by the **Administrator** user unless specified otherwise.
> 
> 

