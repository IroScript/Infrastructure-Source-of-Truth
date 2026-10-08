---
title: "Controllers"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/basics/doctypes/controllers"
updated: "2026-02-17"
---

A Controller is a normal Python class which extends from `frappe.model.Document` base class. This base class is the core logic of a DocType. It handles how values are loaded from the database, how they are parsed and saved back to the database.

When you create a DocType named `Person`, a python file is created by the name `person.py` and the contents look like:


```
import frappe
from frappe.model.document import Document

class Person(Document):
    pass

  

```
All the fields are available to the class as attributes.

### Controller Methods

You can add custom methods to your Controller and it will be callable using the `doc` object. For example,


```
# controller class
class Person(Document):
    def get_full_name(self):
        """Returns the person's full name"""
        return f"{self.first_name} {self.last_name}"

# somewhere in your code
>>> doc = frappe.get_doc("Person", "000001")
>>> doc.get_full_name()
John Doe
  

```
### Controller Hooks

To add custom behaviour during the lifecycle of a document, we have controller hooks.



| Method Name | Description | Insert | Save | Submit | Cancel | Update after submit |
| --- | --- | --- | --- | --- | --- | --- |
| `before_insert` | This is called before a document is prepared for insertion. | X |  |  |  |  |
| `before_naming` | This is called before the `name` property of the document is set. | X |  |  |  |  |
| `autoname` | If defined in the controller, this method is used to set `name` property of the document. | X |  |  |  |  |
| `before_validate` | This hook is called before validation, use this for auto setting missing values. | X | X | X |  |  |
| `validate` | Use this method to throw any validation errors and prevent the document from saving. | X | X | X |  |  |
| `before_save` | This method is called before the document is saved. | X | X |  |  |  |
| `before_submit` | This method is called before the document is submitted. | X |  | X |  |  |
| `before_cancel` | This method is called before the document is cancelled. |  |  |  | X |  |
| `before_update_after_submit` | This method is called when doc fields are updated on submitted document. |  |  |  |  | X |
| `db_insert` | This method inserts document in database, do not override this unless you're working on virtual DocType. | X |  |  |  |  |
| `after_insert` | This is called after the document is inserted into the database. | X |  |  |  |  |
| `db_update` | This method updates document in database, do not override this unless you're working on virtual DocType. |  | X | X | X | X |
| `on_update` | This is called when values of an existing document is updated. | X | X | X |  |  |
| `on_submit` | This is called when a document is submitted. |  |  | X |  |  |
| `on_cancel` | This is called when a submitted document is cancelled. |  |  |  | X |  |
| `on_update_after_submit` | This is called *when* a submitted document values are updated. |  |  |  |  | X |
| `on_change` | This is called when a document's values has been changed. This method is also called when db_set is performed, so operation performed in this method should be idempotent. | X | X | X | X | X |

Apart from doc events for typical actions, you can also hook into other actions.



| Method Name | Description |
| --- | --- |
| `before_rename` | This is called before a document is renamed. |
| `after_rename` | This is called after a document is renamed. |
| `on_trash` | This is called when a document is being deleted. |
| `after_delete` | This is called after a document has been deleted. |

To use a controller hook, just define a class method with that name. For e.g


```
class Person(Document):
    def validate(self):
        if self.age <= 18:
            frappe.throw("Person's age must be at least 18")

    def after_insert(self):
        frappe.sendmail(recipients=[self.email], message="Thank you for registering!")
  

```
You can also override the pre-defined document methods to add your own behaviour if the hooks aren't enough for you. For e.g to override the `save()` method,


```
class Person(Document):
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs) # call the base save method
        do_something() # eg: trigger an API call or a Rotating File Logger that "User X has tried updating this particular record"
  

```
There are a lot of methods provided by default on the `doc` object. You can find the complete [list here](/framework/v14/user/en/api/document#document-methods).

#### 1. Create a document

To create a new document and save it to the database,


```
doc = frappe.get_doc({
    'doctype': 'Person',
    'first_name': 'John',
    'last_name': 'Doe'
})
doc.insert()

doc.name # 000001
  

```
#### 2. Load a document

To get an existing document from the database,


```
doc = frappe.get_doc('Person', '000001')

# doctype fields
doc.first_name # John
doc.last_name # Doe

# standard fields
doc.creation # datetime.datetime(2018, 9, 20, 12, 39, 34, 236801)
doc.owner # john.doe@frappeframework.com
  

```
### Document

A Document is an instance of a DocType. It usually maps to a single row in the database table. We refer to it as `doc` in code.

**Example**

Let's say we have a DocType **ToDo** with the following fields:

* `description`
* `status`
* `priority`

Now, if we want to query a document from the database, we can use the [ORM](#orm).


```
>>> doc = frappe.get_doc("ToDo", "0000001")
<todo: 0000001="">

>>> doc.as_dict()
{'name': '0000001',
 'owner': 'Administrator',
 'creation': datetime.datetime(2022, 3, 28, 18, 20, 23, 275229),
 'modified': datetime.datetime(2022, 3, 28, 18, 20, 23, 275229),
 'modified_by': 'Administrator',
 'docstatus': 0,
 'idx': 0,
 'status': 'Open',
 'priority': 'Medium',
 'color': None,
 'date': None,
 'allocated_to': None,
 'description': 'Test',
 'reference_type': None,
 'reference_name': None,
 'role': None,
 'assigned_by': 'Administrator',
 'assigned_by_full_name': 'Administrator',
 'sender': None,
 'assignment_rule': None,
 'doctype': 'ToDo'}
  

```
You get the values of `description`, `status` and `priority`, but you also get fields like `creation`, `owner` and `modified_by` which are fields added by default by the framework on all `docs`.

### Type Annotations


> Introduced in Version 15.
> 
> 

Frappe support automatically generating Python type annotations in controller files. These annotations can be used for auto-completion, reference and type-checking inside the controller file.


```
class Person(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        first_name: DF.Data
        last_name: DF.Data 
        user: DF.Link
    # end: auto-generated types
    pass
  

```
Note: These annotations are generated when creating or updating doctypes. If you modify the code block, it will get overridden on the next update.

You can configure automatic exporting in your app by adding the following hook.


```
# hooks.py

export_python_type_annotations = True
```
  


Learn more about type annotations:

* <https://docs.python.org/3/library/typing.html>
* VS Code users can install Python extension for better auto-complete - <https://code.visualstudio.com/docs/languages/python>
* Most other editors have an equivalent plugin system using LSP.
