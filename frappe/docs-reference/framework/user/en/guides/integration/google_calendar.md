---
title: "Google Calendar Integration\n"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/guides/integration/google_calendar"
updated: "2026-02-17"
---


Frappe provides an integration with Google Calendar in order for all users to synchronize their events.


## Setup

In order to allow a synchronization with Google Calendar you need to connect to your application in Google Cloud Platform and then create an account for each of your users:

1. Create a new project on [Google Cloud Platform](https://cloud.google.com/) and generate new OAuth 2.0 credentials
2. Add `https://{yoursite}` to Authorized JavaScript origins
3. Add `https://{yoursite}?cmd=frappe.integrations.doctype.gcalendar_settings.gcalendar_settings.google_callback` as an authorized redirect URI
4. Add your Client ID and Client Secret in the Gcalendar application: in "Modules>Integrations>Google Calendar>GCalendar Settings"

Once this step is successfully completed, each user can create their own account in `Google Calendar > GCalendar Account`.
They will be requested to authorize your Google application to access their calendar information and will then be redirected to a success page.


## Features

1. Creation of a new calendar in Google Calendar
 - Each User can choose a dedicated name for their Google Calendar.

2. Events synchronization from Frappe to GCalendar
 - All Events created in Frappe are created in Google Calendar.
 - Recurring Events are created as recurring events too.
 - You can optionally add a Google Meet conference link to the Event.
 - All participants (User email) will be added to the Event.
 - Events modified in Frappe are updated in Google Calendar.
 - Events deleted in Frappe are deleted in Google Calendar.

3. Events synchronization from GCalendar to Frappe
 - Events created in Google Calendar are created in Frappe.
 - Events updated in Google Calendar are updated in Frappe.

The synchronization module follows Frappe's authorization rule: An event will be only synchronized if it is public or if the user is the owner.


## Limitations

Currently, if an instance of a recurring event is cancelled in Google Calendar, this change will not be reflected in Frappe.

