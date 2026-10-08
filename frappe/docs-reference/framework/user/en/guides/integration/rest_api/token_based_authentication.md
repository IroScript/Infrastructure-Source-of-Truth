---
title: "Token Based Authentication"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/guides/integration/rest_api/token_based_authentication"
updated: "2026-02-17"
---


> Available starting with v11.0.3
> 
> 

The HTTP Authorization request header contains the credentials to authenticate a user with a server. It consists of the authorization type (`token` or `Basic`) and the corresponding token.


```
Authorization: <type> <token>
```
The token consists of `api-key` and `api-secret` joined by a colon.

Generating API Key and API Secret
---------------------------------

1. Go to User list and open a user.
2. Click on the "Settings" tab. (skip this step if you don't see tabs)
3. Expand the API Access section and click on Generate Keys.
4. You will get a popup with the API Secret. Copy this value and keep it somewhere safe (Password Manager).
5. You will also see another field "API Key" in this section.

Now, using these two keys you can authenticate your API requests. Every request you make with these keys will be logged against the user you selected in Step 1. This also means that roles will be checked against this user. You can also create a new user just for API calls.

Token
-----

HTTP header:


```
Authorization: token <api_key>:<api_secret>

```
Example in python:


```
import requests

url = "http://frappe.local:8000/api/method/frappe.auth.get_logged_user"
headers = {
    'Authorization': "token <api_key>:<api_secret>"
}
response = requests.request("GET", url, headers=headers)

```
Basic
-----

If the "Basic" authentication scheme is used, the credentials are a combination of api_key and api_secret and are constructed like this:

1. The values are combined with a colon `<api_key>:<api_secret>`
2. The resulting string is base64 encoded. `base64encode(<api_key>:<api_secret>)`

HTTP header:


```
Authorization: Basic base64encode("<api_key>:<api_secret>")

```
Example in python:


```
import requests
import base64

url = "http://frappe.local:8000**/api/method/frappe.auth.get_logged_user**"
headers = {
    'Authorization': "Basic %s" % base64.b64encode(<api_key>:<api_secret>)
}
response = requests.request("GET", url, headers=headers)

```
Access Token
------------

If the OAuth 2 Access Token is used to authenticate request, the token is opaque `access_token` string provided by Frappe Server after setting up OAuth 2 and generating token. Check `Guides / Integration / How To Use OAuth 2`

HTTP header:


```
Authorization: Bearer access_token

```
Example in python:


```
import requests
import base64

url = "http://frappe.local:8000**/api/method/frappe.auth.get_logged_user**"
headers = {
    "Authorization": "Bearer %s" % access_token
}
response = requests.request("GET", url, headers=headers)

```
Further resources
-----------------

* [Authorization Header](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Authorization)

