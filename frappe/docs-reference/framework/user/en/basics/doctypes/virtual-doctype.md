---
title: "Virtual DocTypes"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/basics/doctypes/virtual-doctype"
updated: "2026-02-17"
---

Virtual DocType is a feature-extension for DocType which allows developers to create DocTypes with custom data sources and DocType controller. The purpose is to define custom DocTypes in the system without creating a table in the database, while utilizing the frontend, resource APIs, and roles and permissions from the framework.

These Virtual DocTypes function exactly like normal DocTypes in the frontend and are indistinguishable for the end-user, but gives more control to the developer over the DocType's data source. With this, the data source for a Virtual DocType can be anything: an external API, a secondary database, JSON or CSV files, etc. This enables the developers to plug-in database backends other than MariaDB and Postgres, and makes the Frappe Framework even more powerful!

Note: `frappe.db.*` calls work only with site's database connection. You'll need to implement methods to achieve direct query to data store used by Virtual DocType.

Creating a Virtual DocType
--------------------------

To create a Virtual DocType, just select the Virtual DocType checkbox while creating the DocType:

![Virtual DocType](/files/virtual_doctype.png)  


#### Creating a Custom Controller

As an example, the following controller code uses a JSON file as the DocType datasource:


```
class VirtualDoctype(Document):
    """This is a virtual doctype controller for demo purposes.

 - It uses a single JSON file on disk as "backend".
 - Key is docname and value is the document itself.

 Example:
 {
 "doc1": {"name": "doc1", ...}
 "doc2": {"name": "doc2", ...}
 }
 """

    DATA_FILE = "data_file.json"

 @staticmethod
    def get_current_data() -> dict[str, dict]:
        """Read data from disk"""
        if not os.path.exists(VirtualDoctype.DATA_FILE):
            return {}

        with open(VirtualDoctype.DATA_FILE) as f:
            return json.load(f)

 @staticmethod
    def update_data(data: dict[str, dict]) -> None:
        """Flush updated data to disk"""
        with open(VirtualDoctype.DATA_FILE, "w+") as data_file:
            json.dump(data, data_file)

    def db_insert(self, *args, **kwargs):
        d = self.get_valid_dict(convert_dates_to_str=True)

        data = self.get_current_data()
        data[d.name] = d

        self.update_data(data)

    def load_from_db(self):
        data = self.get_current_data()
        d = data.get(self.name)
        super(Document, self).__init__(d)

    def db_update(self, *args, **kwargs):
        # For this example insert and update are same operation,
        # it might be different for you.
        self.db_insert(*args, **kwargs)

    def delete(self):
        data = self.get_current_data()
        data.pop(self.name, None)
        self.update_data(data)

 @staticmethod
    def get_list(args):
        data = VirtualDoctype.get_current_data()
        return [frappe._dict(doc) for name, doc in data.items()]

 @staticmethod
    def get_count(args):
        data = VirtualDoctype.get_current_data()
        return len(data)

 @staticmethod
    def get_stats(args):
        return {}
  

```
You can read about the interface requriements and explanation in the [interface file](https://github.com/frappe/frappe/blob/develop/frappe/model/virtual_doctype.py). To integrate other datasources with the Virtual DocType, you will need to add controller methods defining the database access.

#### Outcome

The frontend for Virtual DocTypes remain unchanged

![Virtual DocType Form](/files/virtual_doctype_form.png)  


All the /api/resource methods defined by the framework are compatible with Virtual DocTypes.


> Added in Version 13
> 
> 

