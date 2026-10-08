---
title: "Dialog API"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/api/py-dialog"
updated: "2026-02-17"
---

Frappe provides a group of standard, interactive and flexible dialogs that are easy to configure and use. There's also a more extensive API for [Javascript](/framework/v14/user/en/api/dialog).

### frappe.msgprint

`frappe.msgprint(msg, title, raise_exception, as_table, as_list, indicator, primary_action, is_minimizable, wide, realtime)`

This method works only within a request / response cycle. It shows a message to the user logged in to Desk who initiated the request.

The argument list includes:

* `msg`: The message to be displayed
* `title`: Title of the modal
* `as_table`: If `msg` is a list of lists, render as HTML table
* `as_list`: If `msg` is a list, render as HTML unordered list
* `primary_action`: Bind a primary server/client side action.
* `raise_exception`: Exception
* `is_wide`: Show a wide modal
* `is_minimizable`: Allow users to minimize the modal
* `realtime`: publish immediately using websocket instead of adding to response message log


```
frappe.msgprint(
    msg='This file does not exist',
    title='Error',
    raise_exception=FileNotFoundError
)
  

```
![frappe.msgprint](/files/dialog-api-msgprint-py.png) *frappe.msgprint*

`primary_action` can contain a `server_action` **or** `client_side` action which must contain dotted paths to the respective methods. The JavaScript function must be a globally available function. You can also pass `hide_on_success` to close the message after the action is successfully completed.


```
# msgprint with server and client side action
frappe.msgprint(msg='This file does not exist',
    title='Error',
    raise_exception=FileNotFoundError
    primary_action={
        'label': _('Perform Action'),
        'server_action': 'dotted.path.to.server.method',
        'client_action': 'dotted.path.to.client.method',
        'hide_on_success': True,
        'args': args
    }
)
  

```
![frappe.msgprint with primary action](/files/dialog-api-msgprint-py-with-primary-action.png) *frappe.msgprint with primary action*

### frappe.throw

`frappe.throw(msg, exc, title, is_minimizable, wide, as_list, primary_action)`

This method will raise an exception as well as show a message in Desk. It is essentially a wrapper around `frappe.msgprint`.

`exc` can be passed an optional exception. By default it will raise a `ValidationError` exception.


```
frappe.throw(
    title='Error',
    msg='This file does not exist',
    exc=FileNotFoundError
)
  

```
![Throw-py](/files/dialog-api-msgprint-py.png) *frappe.throw*

