---
title: "Realtime (socket.io)"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/api/realtime"
updated: "2026-09-29"
---

Frappe ships with an API for realtime events based on [socket.io](https://socket.io/). Since socket.io needs a Node server to run, we run a Node process in parallel to the main web server.

## Client APIs (JavaScript)

## frappe.realtime.on

To listen to realtime events on the client (browser), you can use the `frappe.realtime.on` method:

```
frappe.realtime.on('event_name', (data) => {
    console.log(data)
})
```

## frappe.realtime.off

Stop listening to an event you have subscribed to:

```
frappe.realtime.off('event_name')
```

## Server APIs (Python)

## frappe.publish\_realtime

To publish a realtime event from the server, you can use the `frappe.publish_realtime` method:

```
frappe.publish_realtime('event_name', data={'key': 'value'})
```

## frappe.publish\_progress

You can use this method to show a progress bar in a dialog:

```
frappe.publish_progress(25, title='Some title', description='Some description')
```

![frappe publish realtime](/files/frappe-publish-realtime.png)

## **Custom Event Handlers (Python)**

> Note: This feature is only available in nightly version. This feature is considered experimental.

You can implement custom real-time event handlers by creating a file `your_app/your_app/realtime/handlers.py` in your custom app. The syntax is fairly similar with API whitelists.



```python
from frappe.realtime import realtime

@realtime.on(
  "project_subscribe",
  frappe_context=False,   # open a Frappe context (DB + session) for the handler body
  allow_guest=False,      # if False, the event is dropped when socket.user == "Guest"
)
```

Defaults: `frappe_context=False`, `allow_guest=False`

### **Example**

```python
import frappe
from frappe.realtime import Socket, realtime

@realtime.on("project_subscribe")
def project_subscribe(socket: Socket, project: str) -> None:
    if socket.has_permission("Project", project):
        socket.join(f"project:{project}")
```



The first argument is always the typed `Socket`. The rest are the payload the client sent, positionally. The event name `"project_subscribe"` is what the browser emits with `frappe.realtime.emit(...)`.

### **Working example with frappe\_context=True**

With `frappe_context=True` the full ORM is available in the handler body — `frappe.get_doc`, `frappe.local.site`, `frappe.session.user` are all populated and reflect the authenticated socket user.



This example handler loads a doc, checks permission, and emits the result back to the client:  

```python
@realtime.on("test_get_doc", frappe_context=True)
def test_get_doc(socket: Socket, doctype: str, docname: str) -> None:
    import frappe
    try:
        doc = frappe.get_doc(doctype, docname)
        doc.check_permission()
        socket.emit(
            "test_get_doc_result",
            {
                "ok": True,
                "site": frappe.local.site,
                "user": frappe.session.user,
                "doctype": doc.doctype,
                "name": doc.name,
                "modified": str(doc.get("modified")),
            },
        )
    except Exception as e:
        socket.emit("test_get_doc_result", {"ok": False, "error": f"{type(e).__name__}: {e}"})
```



From the browser:

```js
frappe.realtime.on("test_get_doc_result", (r) => console.log(r));
frappe.realtime.emit("test_get_doc", "User", "Administrator");
```

See [Permission checks](#permission-checks-two-ways)  section for the cost and when to prefer the cheap HTTP based permission check instead.



A handler runs only if its owning app is installed on the connecting site. The owning app is detected automatically from the import.

You may have to restart the socketio server to see code changes take effect. See the [Socket.IO docs](https://socket.io/docs/v4/) for more on writing custom event handlers.

### **Socket object**

Read-only identity, populated at connect:

```python
socket.site            # the site this socket is on
socket.user            # "Guest" for anonymous
socket.user_type       # e.g. "System User"
socket.installed_apps  # list of installed apps
```



Rooms, emit and transient state:

```python
socket.join(room)                        # add this socket to a room
socket.leave(room)                       # remove it
socket.emit(event, data=None, room=None) # emit to a room, or to this client if room is None
socket.get(key, default=None)            # read transient per-socket state
socket.set(key, value)                   # persist transient per-socket state (cleared on disconnect)
```



**Permission checks**

There are two ways to perform doctype permission checks.



**A. HTTP (default, recommended)** : `socket.has_permission(doctype, name)` asks the web process, exactly like the core handlers. No DB connection in the realtime process. Cheap. Use this unless you have a reason not to.

```python
if socket.has_permission("Project", project):
    socket.join(f"project:{project}")
```



B. **In-process (**`frappe_context=True`**)** : opens a full Frappe context for the handler body so you can call `frappe.has_permission(...)`, query the DB, etc. directly. Cost: every such event pays `frappe.init -> connect -> set_user -> commit/rollback -> destroy` and forces a DB connection into the realtime process. Use sparingly.

```python
@realtime.on("project_subscribe", frappe_context=True)
def project_subscribe(socket: Socket, project: str) -> None:
    if frappe.has_permission("Project", doc=project, ptype="read"):
        socket.join(f"project:{project}")
```

Full reference: [https://github.com/frappe/frappe/blob/develop/frappe/realtime/README.md](https://github.com/frappe/frappe/blob/develop/frappe/realtime/README.md)

## **Custom Event Handlers (NodeJS)**

> **Available from v16.**  Considered experimental. This is the previous implementation and will be phased out in newer version. 
>
> Socket.IO server path; new apps should prefer the Python handlers above.



You can implement custom real-time event handlers by creating a `handlers.js` file in the `realtime` folder of your app.

You need a single export from this file — a function that sets up event handlers on the socket instance. E.g. for an app called "chat":

```javascript
// bench/apps/chat/realtime/handlers.js

function chat_app_handlers(socket) {
    socket.on("hello_chat", () => {
        console.log("hello world!");
    });
}

module.exports = chat_app_handlers;
```

Trigger this event from client-side code with `frappe.realtime.emit("hello_chat")`. You may have to restart the socketio server to see code changes take effect. See the [Socket.IO docs](https://socket.io/docs/v4/) for more on writing custom event handlers.

## **Pushing events to clients**

You do not emit from the web process directly — you publish through Redis, and the realtime server bridges it to the connected sockets. The room string you publish to must match the room your handler `join`-ed.

```python
from frappe.realtime import publish_to_room
publish_to_room("project:PROJ-0001", "project_updated", {"status": "Open"})
```



Other named helpers, each thin wrapper over `publish_realtime`.

```python
publish_to_user(user, event, message=None)
publish_to_doc(doctype, docname, event, message=None)
publish_to_doctype(doctype, event, message=None)
publish_task_progress(task_id, message=None)
publish_to_website(event, message=None)
publish_to_all(event, message=None)
publish_to_room(room, event, message=None)
```

Full reference: [https://github.com/frappe/frappe/blob/develop/frappe/realtime/README.md](https://github.com/frappe/frappe/blob/develop/frappe/realtime/README.md)



# **Custom Client**

You can write a custom client to connect to the socket.io server if you're developing a SPA or a mobile app that doesn't use the Desk interface. Refer to the official [Socket.IO client docs](https://socket.io/docs/v4/client-initialization/).



Example custom clients:

- [gameplan/frontend/src/socket.js](https://github.com/frappe/gameplan/blob/9f9332cf29496afe5e912e4f1734fbf1142cb18c/frontend/src/socket.js#L13)
- [frappe/socketio\_client.js](https://github.com/frappe/frappe/blob/8093a1d0a54900fe4b43b01ae6ffc0adf855da43/frappe/public/js/frappe/socketio_client.js#L49)

## **Authorization in custom clients**

Two ways to authenticate a connection with the socket.io server:

- **Cookies** — in a browser-like environment, the connection automatically sends cookies and the socketio server authenticates using them.
- **Authorization header** — if cookies are unavailable (e.g. mobile apps), use an `Authorization` header just like API requests. See the [REST API authentication docs](https://frappeframework.com/docs/user/en/api/rest#authentication) and [Socket.IO extraHeaders](https://socket.io/docs/v4/client-options/#extraheaders).



# **Implementation Notes**

- Realtime server uses the socket.io server, written in node.js, found in the `/realtime` directory.
- The realtime client is a wrapper around the socket.io client library, found in `public/js/frappe/socketio_client.js`.
- Python processes publish events to the node server over a Redis pub-sub channel. The realtime server subscribes to the Redis channel and republishes to all subscribed clients.
- The realtime server is multi-tenant: all site traffic is namespaced by sitename. Namespaces are created dynamically as `/{sitename}`, where `sitename` is the  site's folder name in the `sites` directory (or `frappe.local.site`).
- The realtime server uses the main Frappe web server to authenticate connections. The SID cookie or authorization header is passed to the client and used to ensure the connection is a valid user that can subscribe to DocTypes/documents per permissions.

## **Available rooms**


| Room                 | Access                                                                                                   |
| -------------------- | -------------------------------------------------------------------------------------------------------- |
| all                  | Connected by default for all System Users                                                                |
| website              | Accessible to any user, including Guests                                                                 |
| user:{username}      | Per-user room. Allowed without permission checks                                                         |
| doctype:{doctype}    | Per-DocType room. Only users with DocType permission may join; auto-subscribed on opening list/form view |
| doc:{doctype}/{name} | Per-document room. Only users with document permission may join; auto-subscribed on opening form view    |