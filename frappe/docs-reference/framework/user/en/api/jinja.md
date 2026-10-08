---
title: "Jinja API\n"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/api/jinja"
updated: "2026-02-17"
---


These are the whitelisted methods that frappe provides to use them in Jinja
Templates.

## frappe.format
`frappe.format(value, df, doc)`

Formats a raw value (stored in database) to a user presentable format.
For example, convert 2019-09-08 to 08-09-2019

Usage
```html
{{ frappe.format('2019-09-08', {'fieldtype': 'Date'}) }}

09-08-2019
```

## frappe.format_date
`frappe.format_date(date_string)`

Formats date into a human readable long format.

Usage

```html
{{ frappe.format_date('2019-09-08') }}

September 8, 2019
```

## frappe.get_url
`frappe.get_url()`

Returns the site url

Usage
```html
{{ frappe.get_url() }}

https://frappe.io
```

## frappe.get_doc
`frappe.get_doc(doctype, name)`

Returns a document by its name.

Usage
```html

 {% set doc = frappe.get_doc('Task', 'TASK00002') %}
 {{ doc.title }} - {{ doc.status }}



 Buy Eggs - Open

```

## frappe.get_all
`frappe.get_all(doctype, filters, fields, order_by, start, page_length, pluck)`

Returns a list of all records of a DocType. Only returns the document `name`s if the `fields` argument is not given.

Signature
```python
frappe.get_all(doctype, filters, fields, order_by, start, page_length)
```

Usage

```html

 {% set tasks = frappe.get_all('Task', filters={'status': 'Open'}, fields=['title', 'due_date'], order_by='due_date asc') %}
 {% for task in tasks %}
 
### {{ task.title }}


Due Date: {{ frappe.format_date(task.due_date) }}



 {% endfor %}




### Redesign Website


Due Date: September 8, 2019




### Add meta tags on websites


Due Date: September 22, 2019




```

## frappe.get_list
`frappe.get_list(doctype, filters, fields, order_by, start, page_length)`

Similar to `frappe.get_all` but will filter records for the current session user
based on permissions.

## frappe.db.get_value
`frappe.db.get_value(doctype, name, fieldname)`

Returns a single field value (or a list of values) from a document.

Usage

```html


 {% set company_abbreviation = frappe.db.get_value('Company', 'TennisMart', 'abbr') %}
 {{ company_abbreviation }}
 

 {% set title, description = frappe.db.get_value('Task', 'TASK00002', ['title', 'description']) %}
 ### {{ title }}


{{ description }}






TM

```

## frappe.db.get_single_value
`frappe.db.get_single_value(doctype, fieldname)`

Returns a field value from a Single DocType.

Usage
```html


 {% set timezone = frappe.db.get_single_value('System Settings', 'time_zone') %}
 {{ timezone }}
 




 Asia/Kolkata
 

```

## frappe.get_system_settings
`frappe.get_system_settings(fieldname)`

Returns a field value from System Settings.

Usage
```html

 {% if frappe.get_system_settings('country') == 'India' %}
 Pay via Razorpay
 {% else %}
 Pay via PayPal
 {% endif %}



Pay via Razorpay

```

## frappe.get_meta
`frappe.get_meta(doctype)`

Returns a doctype meta. It contains information like fields, title_field,
image_field, etc.

Usage
```html


 {% set meta = frappe.get_meta('Task') %}
 Task has {{ meta.fields | len }} fields.
 {% if meta.get_field('status') %}
 It also has a Status field.
 {% endif %}
 




 Task has 18 fields. It also has a Status field.
 

```

## frappe.get_fullname
`frappe.get_fullname(user_email)`

Returns the fullname of the user email passed. If user is not passed, assumes
current logged in user.

Usage
```html

The fullname of faris@erpnext.com is {{ frappe.get_fullname('faris@erpnext.com') }}
The current logged in user is {{ frappe.get_fullname() }}



The fullname of faris@erpnext.com is Faris Ansari
The current logged in user is John Doe

```

## frappe.render_template
`frappe.render_template(template_name, context)`

Render a jinja template string or file with context.

Usage
```html


 {{ frappe.render_template('templates/includes/footer/footer.html', {}) }}

 
{{ frappe.render_template('{{ foo }}', {'foo': 'bar'}) }}








bar



```

## frappe._
`frappe._(string)` or `_(string)`

Usage
```html

{{ _('This string should get translated') }}





इस तार का अनुवाद होना चाहिए



```

## frappe.session.user

Returns the current session user

## frappe.session.csrf_token

Returns the current session's CSRF token

## frappe.form_dict

If the template is being evaluated in a web request, `frappe.form_dict` is a
dict of query parameters, else it is `None`.

## frappe.lang

Current language used by the translation function. Two letter, lowercase code.
