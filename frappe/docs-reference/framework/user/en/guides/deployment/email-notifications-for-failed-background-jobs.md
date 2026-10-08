---
title: "Email Notifications For Failed Background Jobs\n"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/guides/deployment/email-notifications-for-failed-background-jobs"
updated: "2026-02-17"
---



Frappe handles failure of jobs in the following way,

1) If a job fails, (raises exception), it's logged in Scheduler Log and  `logs/worker.error.log`.  
2) Keeps a lock file and would not run anymore if lock file is there.  
3) Raises LockTimeoutError in case the lock file is more than 10 minutes old.


You can configure email notification for scheduler errors. By writing a file, `sites/common_site_config.json` with content  




```
{
  "celery_error_emails": {
 "ADMINS": [
 [
 "Person 1",
 "person1@example.com"
 ],
 [
 "Person2 ",
 "person2@example.com"
 ]
 ],
 "SERVER_EMAIL": "exceptions@example.com"
 }
}
```

One limitation is that it'll use local mailserver on port 25 to send the emails.


