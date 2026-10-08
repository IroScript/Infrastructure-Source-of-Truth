---
title: "Rate Limiting"
space: "Framework"
url: "https://docs.frappe.io/framework/deployment/rate-limiting"
updated: "2026-09-29"
---

Frappe framework has out of the box support for rate-limiting HTTP requests.

Frappe framework implements fixed window rate-limiting based on time consumed by requests. The limit is enforced on the sum of time taken by all HTTP requests made in the configured window. The cycle resets after every `window` seconds, for instance, setting `window` to 3600 seconds will reset the usage counter to 0 at the beginning of every hour based on site's timezone.

**Note:** Requests over limit are not processed and are sent HTTP `429` (Too Many Requests) response.

You can enable rate limiting on your site by adding configuration similar to the following in `site_config.json`:

```json
{
 "rate_limit": {
 "limit": 600,
 "window": 3600
 }
}
```


| Key      | Description                                                                    |
| -------- | ------------------------------------------------------------------------------ |
| `limit`  | Maximum amount of time permitted to use in the rate limit window (in seconds). |
| `window` | Size of the rate limit window (in seconds).                                    |


The returned HTTP headers of every HTTP request show the current rate limit status, e.g.

```
curl -i https://frappe.io/docs
HTTP/1.1 200 OK
X-RateLimit-Limit: 600000000
X-RateLimit-Remaining: 518060453
X-RateLimit-Reset: 3513
X-RateLimit-Used: 100560
```

In case of requests made after configured limits are exhausted, HTTP `429` response is returned along with the rate limit status:

```
curl -i https://frappe.io/docs
HTTP/1.1 429 TOO MANY REQUESTS
X-RateLimit-Limit: 600000000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1242
Retry-After: 1242
```


| Header                | Description                                                                     |
| --------------------- | ------------------------------------------------------------------------------- |
| Retry-After           | Time remaining till the current rate limit window resets (in seconds).          |
| X-RateLimit-Limit     | Time permitted to use in a rate limit window (in microseconds).                 |
| X-RateLimit-Remaining | Time remaining (to be used) in the current rate limit window (in microseconds). |
| X-RateLimit-Reset     | Time remaining till the current rate limit window resets (in seconds).          |
| X-RateLimit-Used      | Time used for processing the current request (in microseconds).                 |


### **Endpoint-Specific Rate Limiting**

While the site-wide configuration limits the total processing time of requests, developers can apply strict request-count limits to specific whitelisted Python methods using the `@rate_limit` decorator located in `frappe.rate_limiter`.

**Decorator Arguments:**


| **Argument** | **Type**            | **Default** | **Description**                                                                                                       |
| :------------ | :------------------- | :----------- | :--------------------------------------------------------------------------------------------------------------------- |
| `key`        | `str`               | `None`      | A specific key from `frappe.form_dict` to uniquely identify the request.                                              |
| `limit`      | `int` or `Callable` | `5`         | Maximum number of requests allowed within the time window.                                                            |
| `seconds`    | `int`               | `86400`     | The time window in seconds (default is 24 hours).                                                                     |
| `methods`    | `str` or `list`     | `"ALL"`     | HTTP methods to rate limit (e.g., `"POST"` or `["GET", "POST"]`).                                                     |
| `ip_based`   | `bool`              | `True`      | Tracks the limit by the requester's IP address (Network-aware).                                                       |
| `endpoint`   | `str`               | `None`      | *(Added in v17)* Custom counter name. Required if the callable has no stable dotted path (e.g., `functools.partial`). |
| `user_based` | `bool`              | `False`     | *(Added in v17)* Tracks the limit by the authenticated user's session ID (Identity-aware).                            |


**Tracking Behavior and Mutual Exclusivity** *(Identity-aware tracking and secure guest fallbacks are available starting in Version 17. Using* `user_based` *or* `endpoint` *in v15 or v16 will raise a* `TypeError`*).*

The rate limiter is designed to track a request by *either* network identity *or* user identity, never both simultaneously.

- **Identity-Aware (**`user_based=True`**):** The limit is strictly applied to the authenticated `frappe.session.user`. The requester's IP address is entirely ignored, allowing users on shared corporate networks (NAT) to avoid inadvertently blocking each other.
- **Network-Aware (**`ip_based=True, user_based=False`**):** The limit is strictly applied to the `request_ip`. The user's session ID is ignored. This is the default legacy behavior.
- **Guest Fallback:** If an endpoint is configured with `user_based=True`, unauthenticated "Guest" traffic will securely fall back to being tracked by their IP address. This prevents a single malicious guest from exhausting a global guest bucket and causing a Denial of Service for all other anonymous users.

**Example Implementation:**

```python
from frappe.rate_limiter import rate_limit

# Limits authenticated users to 10 requests per minute per account.
# Guests hitting this mixed-auth endpoint are limited to 10 requests per minute per IP.
@frappe.whitelist()
@rate_limit(limit=10, seconds=60, user_based=True)
def generate_heavy_report():
    pass
```