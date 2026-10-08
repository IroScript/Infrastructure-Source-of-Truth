---
title: "Frappe Ajax Call\n"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/guides/basics/frappe_ajax_call"
updated: "2026-02-17"
---


In Frappe Framework, you can manage ajax calls via frappe.call. The frappe.call works in asynchronous manner ie. send requests and handle response via callback mechanism.

## frappe.call Structure

```js
frappe.call({
 method: "",
 type: "POST",
 args: {},
 success: function(r) {},
 error: function(r) {},
 always: function(r) {},
 btn: opts.btn,
 freeze: false,
 freeze_message: "",
 async: true,
 url: "" || frappe.request.url,
});
```

#### Parameter description

- `method`: dotted path to a whitelisted backend method
- `type`: String parameter, http request type "GET", "POST", "PUT", "DELETE". Default set to "POST".
- `args`: associative array, arguments that will pass with request.
- `success`: Function parameter, code snippet, will after successful execution of request
- `error`: Function parameter, code snippet, will execute after request failure
- `always`: Function parameter, code snipper, will execute in either case
- `btn`: Object parameter, triggering object
- `freeze`: Boolean parameter, if set freeze the instance until it receives response
- `freeze_message`: String parameter, message will populate to screen while screen is in freeze state.
- `async`: Boolean parameter, default set to true. So each frappe.call is asynchronous. To make call synchronous set parameter value as false
- `url`: String parameter, location from where hitting the request


## How to use frappe.call ?

### Calling standard API

```js
frappe.call({
 method: 'frappe.client.get_value',
 args: {
 'doctype': 'Item',
 'filters': {'name': item_code},
 'fieldname': [
 'item_name',
 'web_long_description',
 'description',
 'image',
 'thumbnail'
 ]
 },
 callback: function(r) {
 if (!r.exc) {
 // code snippet
 }
 }
});
```

- Param description:

 - `doctype`: name of doctype for which you want to pull information
 - `filters`: condition specifier
 - `fieldname`: you can specify fields in array that you want back in response

### Calling whitelisted methods

- On the client side we specify the server side `method` to be called. This is a dotted path through the python modules on the server side, where the last part is the method name.

 ```js
 frappe.call({
 method: "frappe.core.doctype.user.user.get_all_roles", //dotted path to server method
 callback: function(r) {
 // code snippet
 }
 });
 ```

- The above request calls the server-side method `get_all_roles`, located in the file `$MY_BENCH/apps/frappe/frappe/core/doctype/user/user.py`:

 ```py
 @frappe.whitelist()
 def get_all_roles():
 // business logic
 return value
 ```

 > **Note**: any server side method that should be accessed via `frappe.call()` needs to be whitelisted, by using the decorator `@frappe.whitelist()`.
