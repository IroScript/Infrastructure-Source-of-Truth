---
title: "Caching"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/guides/caching"
updated: "2026-08-28"
---

One of the batteries included in Frappe Framework is inbuilt caching using Redis. Redis is fast, simple to use, in-memory key-value storage. Redis with Frappe Framework can be used to speed up repeated long-running computations or avoid database queries for data that doesn't change often.

Redis is spawned as a separate service by the bench and each Frappe web/background worker can connect to it using `frappe.cache`.

Note: On older versions of Frappe, you may need to use `frappe.cache()` instead of `frappe.cache` to access Redis connection. 

### Redis Data Types and Usage

Redis supports many data types, but here we will only cover a few most used datatypes:

1. **Strings** are the most popular and most used datatype in Redis. They are stored as key-value pairs.

```
In [1]: frappe.cache.set_value("key", "value")

In [2]: frappe.cache.get_value("key")
Out[2]: 'value'

```

2. **Hashes** are used to represent complicated objects, fields of which can be updated separately without sending the entire object. You can imagine Hashes as dictionaries stored on Redis.

```
# Get fields separately
In [1]: frappe.cache.hset("user|admin", "name", "Admin")
In [2]: frappe.cache.hset("user|admin", "email", "admin@example.com")

# Get single field value
In [3]: frappe.cache.hget("user|admin", "name")
Out[3]: 'Admin'

# Or retrieve all fields at once.
In [4]: frappe.cache.hgetall("user|admin")
Out[4]: {'name': 'Admin', 'email': 'admin@example.com'}

```

### Cached Documents

Frappe has an inbuilt function for getting documents from the cache instead of the database.

Getting a document from the cache is usually faster, so you should use them when the document doesn't change that often. A common usage for this is getting user configured settings.

```
system_settings = frappe.get_cached_doc("System Settings")

```

Cached documents are automatically cleared using "best-effort" cache invalidation.

Whenever Frappe's ORM encounters a change using `doc.save` or `frappe.db.set_value`, it clears the related document's cache. However, this isn't possible if a raw query to the database is issued.

Note: Manual cache invalidation can be done using `frappe.clear_document_cache(doctype, name)`.

### Implementing Custom Caching

When you're dealing with a long expensive computation, the outcome of which is deterministic for the same inputs then it might make sense to cache the output.

Let's attempt to implement a custom cache in this toy function which is slow.

```
def slow_add(a, b):
    import time; time.sleep(1) # Fake workload
    return a + b

```

The most important part of implementing custom caching is generating a unique key. In this example the outcome of the cached value is dependent on two input variables, hence they should be part of the key.

```
def slow_add(a, b):
    key = f"slow_addition|{a}+{b}" # unique key representing this computation

    # If this key exists in cache, then return value
    if cached_value := frappe.cache.get_value(key):
        return cached_value

    import time; time.sleep(1) # Fake workload
    result = a + b

    # Set the computed value in cache so next time we dont have to do the work
    frappe.cache.set_value(key, result)

    return result

```

#### Cache Invalidation

Two strategies are recommended for avoiding stale cache issues:

1. Setting short TTL while setting cached values.

```
# This cached value will automatically expire in one hour
frappe.cache.set_value(key, result, expires_in_sec=60*60)

```

2. Manually clearing the cache when cached values are modified.

```
frappe.cache.delete_value(key) # `frappe.cache.hdel` if using hashes.

```

### `@redis_cache` decorator

Frappe provides a decorator to automatically cache the results of a function call.

You can use it to quickly implement caching on top of any existing function which might be slow.

```
In [1]: def slow_function(a, b):
   ...:     import time; time.sleep(1)  # fake expensive computation
   ...:     return a + b
   ...:

In [2]: # This takes 1 second to execute every time.
   ...: %time slow_function(40, 2)
   ...:
Wall time: 1 s
Out[2]: 42

In [3]: %time slow_function(40, 2)
Wall time: 1 s
Out[3]: 42

In [4]: from frappe.utils.caching import redis_cache
   ...:

In [5]: @redis_cache
   ...: def slow_function(a, b):
   ...:     import time; time.sleep(1)  # fake expensive computation
   ...:     return a + b
   ...:


In [6]: # Now first call takes 1 second, but all subsequent calls return instantly.
   ...: %time slow_function(40, 2)
   ...:
Wall time: 1 s
Out[6]: 42

In [7]: %time slow_function(40, 2)
   ...:
Wall time: 897 µs
Out[7]: 42

```

#### Cache Invalidation

There are two ways to invalidate cached values from `@redis_cache`.

1. Setting appropriate expiry period (TTL in seconds) so cache invalidates automatically after some time. Example: `@redis_cache(ttl=60)` will cause cached value to expire after 60 seconds.
2. Manual clearing of cache. This is done by calling function's `clear_cache` method.

```
from frappe.utils.caching import redis_cache

@redis_cache
def slow_function(...):
    ...


def invalidate_cache():
    slow_function.clear_cache()

```

### Frappe's Redis Setup

Bench sets up Redis by default. You will find Redis config in `{bench}/config/` directory.

Bench also configures `Procfile` and supervisor configuration file to launch Redis server when the bench is started.

```
redis_cache: redis-server config/redis_cache.conf

```

A sample config looks like this:

```
dbfilename redis_cache.rdb
dir /home/user/benches/develop/config/pids
pidfile /home/user/benches/develop/config/pids/redis_cache.pid
bind 127.0.0.1
port 13000
maxmemory 737mb
maxmemory-policy allkeys-lru
appendonly no

save ""

```

You can modify this `maxmemory` in this config to increase the maximum memory allocated for caching. We do not recommend modifying anything else.

Refer to the official config documentation to understand more: &lt;[https://redis.io/docs/latest/operate/oss\_and\_stack/management/config-file/](https://redis.io/docs/latest/operate/oss_and_stack/management/config-file/)&gt;

### Implementation details

#### Multi-tenancy

`frappe.cache` internally prefixes keys by some site context. Hence calling `frappe.cache.set_value("key")` from two different sites on the same bench will create two separate entries for each site.

To see implementation details of this see `frappe.cache.make_key` function.

#### Complex Types

Frappe uses `pickle` module to serialize complex objects like documents in bytes. Hence when using `frappe.cache` you don't have to worry about serializing/de-serializing values.

Read more about pickling here: &lt;[https://docs.python.org/3/library/pickle.html](https://docs.python.org/3/library/pickle.html)&gt;

#### Client Side caching

Frappe implements client-side cache on top of Redis cache inside `frappe.local.cache` to avoid repeated calls to Redis.

Any repeated calls to Redis within the same request/job return data from the client cache instead of calling Redis again.

#### `RedisWrapper`

All Frappe related changes are made by wrapping the default Redis client and extending the methods. You can find this code in `frappe.utils.redis_wrapper` the module.