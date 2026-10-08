---
title: "Redirects"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/guides/portal-development/redirects"
updated: "2026-02-17"
---

You can add redirects by adding the `website_redirects` hook.

The optional field `redirect_http_status` will allow you to specify a custom HTTP status code to use for the redirect - if not specified, the fallback is 301

### Examples


```
website_redirects = [
    # absolute location
    {"source": "/from", "target": "https://mysite/from"},

    # relative location
    {"source": "/from", "target": "/main", "redirect_http_status": 307},

    # use regex
    {"source": "/from/(.*)", "target": "/main/\1"}
]
  

```
  


