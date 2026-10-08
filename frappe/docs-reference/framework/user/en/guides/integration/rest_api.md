---
title: "Introduction"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/guides/integration/rest_api"
updated: "2026-05-10"
---


Frappe ships with an HTTP API that can be classified into *Remote Procedure Calls* (RPC), to call whitelisted methods and *Representational State Transfer* (REST), to manipulate resources.

The base URL is `https://{your frappe instance}`. Every request shown here should be added to the end of your base URL. For example, if your instance is `demo.erpnext.com`, `GET /api/resource/User` means `GET https://demo.erpnext.com/api/resource/User`.

# API v1

All v1 API endpoints are prefixed with `/api/`. Starting from Frappe Framework version 15, they can instead be prefixed with `/api/v1/`.

## RPC

A request to an endpoint `/api/method/dotted.path.to.method` will call a whitelisted python method.

For example, `GET /api/method/frappe.auth.get_logged_user` will call [this function](https://github.com/frappe/frappe/blob/28b909435320e3d6d1a3b2e7c02f286984dc39b3/frappe/auth.py#L347-L349) from frappe's auth module:

```python
@frappe.whitelist()
def get_logged_user():
 return frappe.session.user
```

Response:

```json
{
 "message": "Administrator"
}
```

## REST

All documents in Frappe are available via a RESTful API with prefix `/api/resource/`. You can perform all CRUD operations on them:

* Create

 You can create a document by sending a `POST` request to the endpoint, `/api/resource/{doctype}`.

* Read

 You can get a document by its name using the endpoint, `/api/resource/{doctype}/{name}`

* Update

 You can update a document by sending a `PUT` request to the endpoint, `/api/resource/{doctype}/{name}`. This acts like a `PATCH` HTTP request in which you do not have to send the whole document but only the parts you want to change.

* Delete

 You can delete a document by its name by sending a `DELETE` request to the endpoint, `/api/resource/{doctype}/{name}`.
 
# API v2

&gt; API v2 is available starting from Frappe Framework v15

All v2 API endpoints are prefixed with `/api/v2/`.

## RPC v2

Similar to v1, RPC endpoints are available at `/api/v2/method/` prefix. The following endpoints are available:

* `/api/v2/method/login` - Handle user login (implicit)
* `/api/v2/method/logout` - Log out current user
* `/api/v2/method/ping` - Check server status
* `/api/v2/method/upload_file` - Upload a file
* `/api/v2/method/dotted.path.to.method` - Call any whitelisted method
* `/api/v2/method/&lt;doctype&gt;/&lt;method&gt;` - Call whitelisted method from doctype controller
* `/api/v2/method/run_doc_method` - Run a whitelisted method on a document

## REST v2

API v2 provides a more RESTful interface with the prefix `/api/v2/document/` and `/api/v2/doctype/`. The following operations are supported:

### Document Operations

* Create
  
  Create a document by sending a `POST` request to `/api/v2/document/{doctype}`

* Read
  
  Get a document by sending a `GET` request to `/api/v2/document/{doctype}/{name}/`

* Update
  
  Update a document by sending a `PATCH` or `PUT` request to `/api/v2/document/{doctype}/{name}/`

* Delete
  
  Delete a document by sending a `DELETE` request to `/api/v2/document/{doctype}/{name}/`

* Copy
  
  Get a clean copy of a document by sending a `GET` request to `/api/v2/document/{doctype}/{name}/copy`

* Execute Method
  
  Execute a method on a document by sending a `GET` or `POST` request to `/api/v2/document/{doctype}/{name}/method/{method}`

  Common values for `method`: `add_comment?text=hello`, `submit`, `cancel`, `rename?name=newname`. 

### DocType Operations

* Get Metadata
  
  Get doctype metadata by sending a `GET` request to `/api/v2/doctype/{doctype}/meta`

* Get Count
  
  Get total count of records by sending a `GET` request to `/api/v2/doctype/{doctype}/count`

* List Documents
  
  List documents by sending a `GET` request to `/api/v2/document/{doctype}`. Supports pagination and field selection through query parameters.

