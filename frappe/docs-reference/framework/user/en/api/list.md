---
title: "List"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/api/list"
updated: "2026-02-17"
---

The List View is generated for all DocTypes except Child Tables and Single DocTypes.

The List view is packed with features. Some of them are:

* Filters
* Sorting
* Paging
* Filter by tags
* Switch view to Report, Calendar, Gantt, Kanban, etc.

![List View](/files/list-view.png) *List View*

Standard List JS
----------------

To customize the List View you must have a `{doctype}_list.js` file in the doctype directory. Below are all the options that can be customized.

For instance, if you want to customize the Note DocType, you'll have to create a file `note_list.js` with the following contents.


```
frappe.listview_settings['Note'] = {
    // add fields to fetch
    add_fields: ['title', 'public'],
    // set default filters
    filters: [
        ['public', '=', 1]
    ],
    hide_name_column: true, // hide the last column which shows the `name`
    hide_name_filter: true, // hide the default filter field for the name column
    onload(listview) {
        // triggers once before the list is loaded
    },
    before_render() {
        // triggers before every render of list records
    },

    // set this to true to apply indicator function on draft documents too
    has_indicator_for_draft: false,

    get_indicator(doc) {
        // customize indicator color
        if (doc.public) {
            return [__("Public"), "green", "public,=,Yes"];
        } else {
            return [__("Private"), "darkgrey", "public,=,No"];
        }
    },
    primary_action() {
        // triggers when the primary action is clicked
    },
    get_form_link(doc) {
        // override the form route for this doc
    },
    // add a custom button for each row
    button: {
        show(doc) {
            return doc.reference_name;
        },
        get_label() {
            return 'View';
        },
        get_description(doc) {
            return __('View {0}', [`${doc.reference_type} ${doc.reference_name}`])
        },
        action(doc) {
            frappe.set_route('Form', doc.reference_type, doc.reference_name);
        }
    },
    // format how a field value is shown
    formatters: {
        title(val) {
            return val.bold();
        },
        public(val) {
            return val ? 'Yes' : 'No';
        }
    }
}
  

```
Custom List JS
--------------

You can also customize the list view by creating **Client Script** in the system. You should write Client Scripts if the logic is specific to your site. If you want to share List view customization across sites, you must include them via Apps.

To create a new Client Script, go to

**Home > Customization > Client Script > New**

![New Client Script](/files/client-script-list.png) *New Client Script for List*

The above customization will result in a list view that looks like this:

![List View Customized](/files/list-view-customized.png) *List View Customized*

Multiple Buttons in the List JS
-------------------------------


> This feature is available on [Develop](https://github.com/frappe/frappe/tree/develop) version.
> 
> 

You now have the capability to add multiple buttons within a dropdown menu in the list view row through the use of the list view client script. This feature enhances the user experience by providing convenient access to various actions directly from the list view.


```
frappe.listview_settings["ToDo"] = {
    hide_name_column: true,
    add_fields: ["reference_type", "reference_name"],

    button: {
      show: function(doc) {
        return doc.reference_name;
      },
      get_label: function() {
        return __("Open", null, "Access");
      },
      get_description: function(doc) {
        return __("Open {0}", [
          `${__(doc.reference_type)}: ${doc.reference_name}`
        ]);
      },
      action: function(doc) {
        frappe.set_route("Form", doc.reference_type, doc
          .reference_name);
      },
    },
    dropdown_button: {
      get_label: __("Dropdown"),
      buttons: [{
          get_label: __("Button 1"),
          show: function(doc) {
            return true;
          },
          get_description: function(doc) {
            return "Open Button 1 " + doc.reference_name;
          },
          action: function(doc) {
            frappe.msgprint("Dropdown Button 1 Clicked " +
              doc.reference_name);
          }
        },
        {
          get_label: __("Button 2"),
          show: function(doc) {
            return doc.status != "Closed";
          },
          get_description: function(doc) {
            return "Open Button 2 " + doc.reference_name;
          },
          action: function(doc) {
            frappe.msgprint("Dropdown Button 2 Clicked " +
              doc.reference_name);
          }
        },
        {
          get_label: __("Button 3"),
          show: function(doc) {
            return doc.status != "Cancelled";
          },
          get_description: function(doc) {
            return "Open Button 3 " + doc.reference_name;
          },
          action: function(doc) {
            frappe.msgprint("Dropdown Button 3 Clicked " +
              doc.reference_name);
          }
        },
      ]
    }
  };
```
![](/files/w7DupHw.png)  


