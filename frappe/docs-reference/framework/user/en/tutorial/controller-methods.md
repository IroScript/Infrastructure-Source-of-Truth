---
title: "Controller Methods"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/tutorial/controller-methods"
updated: "2026-02-17"
---

Controller methods allow you to write business logic during the lifecycle of a document.

Let's create our second doctype: **Library Member**. It will have the following fields:

1. First Name (Data, Mandatory)
2. Last Name (Data)
3. Full Name (Data, Read Only)
4. Email Address (Data)
5. Phone (Data)

![](/files/TqEJOjO.gif)

After you have created the doctype, go to Library Member list, clear the cache from **Settings > Reload** and create a new Library Member.

If you notice, the Full Name field is not shown in the form. This is because we set it as Read Only. It will be shown only when it has some value.

Let's write code in our python controller class such that Full Name is computed automatically from First Name and Last Name.

Open your code editor and open the file `library_member.py` and make the following changes:

**librarymember.py**

```
class LibraryMember(Document):
    #this method will run every time a document is saved
    def before_save(self):
        self.full_name = f'{self.first_name} {self.last_name or ""}'
```

---

**NOTE**

If the above snippet doesn't work for you , make sure server side scripts are enabled, and then restart bench

```
bench set-config -g server_script_enabled true
```

---

We wrote the logic in the `before_save` method which runs every time a document is saved. This is one of the many hooks provided by the `Document` class. You can learn more about all the available hooks at [Controller](https://docs.frappe.io/framework/user/en/basics/doctypes/controllers) docs.

Now, go back and create another Library Member and see the Full Name show up after save.

Next: [Types of DocType](/framework/v14/user/en/tutorial/types-of-doctype)