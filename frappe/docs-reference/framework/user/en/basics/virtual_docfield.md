---
title: "Virtual DocField"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/basics/virtual_docfield"
updated: "2026-02-17"
---

A Virtual DocField is a dynamic attribute of a given Document (or Record). It's a calculated attribute that isn't stored in the site database. This could be used for representing values that may be functions of other static Document attributes.

![Person Record](/files/Screenshot 2022-02-14 at 1.55.38 PM.png)
*Person Form*

The age of a person is a function of their date of birth ie if you know a person's birth day, you can figure out their age. Age is also a continuous value; it may change every year, or month, or day, even hour depending on what type of granularity you wish to have. Another attribute is a Person's name. Most common implementations will have a First, Middle and a Last Name, and for the view it would be all of them together like "Jon Raphael Doe". Although saving the full name as a separate attribute may not make so much sense when the strings can be easily concatenated. These are a couple of instances where Virtual DocFields make more sense.

![Person DocType](/files/Screenshot 2022-02-14 at 1.55.08 PM.png)
*Person DocType*

Here we've added three fields to Person; two for First and Last names which are stored in the site database, and one that utilizes this data to populate the third field "Full Name". In this instance, the options field takes input for the return value of the respective virtual field.

![Full Name - Virtual DocField](/files/Screenshot 2022-02-14 at 12.18.20 PM.png)
*Person DocType - DocField*

We discussed the possibility of fields that depend on attributes in the system so far. But this could easily extend to something that doesn't depend on your DocType data alone. You may also want to fetch the statuses of multiple external services in their place, or anything else that you can map here instead.

## How to use Virtual DocFields

The steps involved in making this work are:

### 1. Define a Virtual DocField

Defining a Virtual DocField is fairly straight forward. Just checking on the "Virtual" check box under the DocField's configuration does this. Virtual DocFields don't create a corresponding column in the DocType's table. This makes the field "Read Only" in the Form Views.

> Note: Avoid making existing DocFields virtual unless you know what you're doing

### 2. Define a source for the field

The first step only adds a sort of a placeholder for the values. Without adding some code that dictates what the field should show, there's no field itself. There's two ways of doing this:

* By extending the DocType controllers

Adding a Python property with the same name as the virtual field should do this. This is the most flexible way to do this; you could daisy chain an internal API request, or fetch the data from multiple data sources, sky is the limit.

```python
class Person(Document):
 @property
 def age(self):
 return frappe.utils.now_datetime() - self.creation
```

* Using the `DocField.options`

This is a bit more restrictive given it allows you to write code directly from Desk. [Utils allowed in Server Scripts](/framework/v14/user/en/desk/scripting/script-api) and Document attributes can be accessed through this. Equivalent of the above property maybe as follows:

```python
frappe.utils.now_datetime() - self.creation
```

The above mentioned `Person.full_name` example uses Python's f-string feature to achive this in a similar way.

> Note: This should be preferred for relatively smaller scripting. Lookout for in-compatible types errors while using this


## Impact on internals

If you're wellversed with the physics of the Frappe world, this feature will appear quite predictable.

### Backend API

The `DatabaseQuery` methods or `Database` APIs will not return virtual values since they don't live in the Site Database.

![](/files/Screenshot 2022-02-14 at 2.01.58 PM.png)

### REST API

The `/api/method/frappe.desk.form.load.getdoc` and `/api/resource` APIs utilize `Document.get_valid_dict` which will compute Virtual values too. These APIs are used to render the Desk Form views too.

![](/files/Screenshot 2022-02-14 at 1.58.33 PM.png)

### Database

There's no footprint of virtual fields in the respective DocType's table. However, you may find corresponding records to give some evidence of their existence in the Custom Field, DocField tables that store DocType's Meta.

![](/files/Screenshot 2022-02-14 at 2.03.18 PM.png)

## Virtual Tables on Non-virtual DocTypes

> Note: This feature is only available in nightly (v16) version. This feature is considered experimental.

A **virtual child table** is a virtual field of type "Table" that is computed at runtime. It behaves like a normal child table in many respects:

* The virtual child table appears in the form (grid) under the parent document.
* Its rows are computed dynamically (e.g. via a cached property or descriptor).
* It is read-only (you cannot write into it through the usual ORM methods).
* The parent DocType does not persist these child rows; they exist only in memory.
* The descriptor method for the virtual table can return either raw dictionaries or `Document` instances.
* When loading from the database, the virtual child table’s descriptor is triggered to populate the children rows.

Virtual tables are useful for displaying computed/aggregated data or summary of related data stored elsewhere.

### Defining a Virtual Child Table

To define a virtual child table, you add a new field entry in the parent DocType with "is virtual" set to 1. Logic for dynamically fetching the virtual table has to be defined as a cached property on the DocType controller. 

Note: You MUST NOT use `@property` for virtual tables, only `@cached_property` and other equivalent non-data descriptors are supported.



```py
class User(…) :
    # This is a cached_property (or a non-data descriptor) returning computed rows
    @cached_property
    def virtual_sessions(self):
        # return a list of dicts or list of Document instances
        sessions = get_session_logs(self.name)
        return sessions
```

In this example, when a `User` record is loaded, the framework invokes `User.virtual_sessions` to fetch child rows, then initializes a virtual child table `virtual_sessions` in the form context.