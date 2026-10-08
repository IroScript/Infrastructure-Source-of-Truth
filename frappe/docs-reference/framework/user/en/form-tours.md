---
title: "Form Tours"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/form-tours"
updated: "2026-02-17"
---

Frappe provides an easy way to generate form tutorials for your complex doctype with very little configuration.

![Form Tour](/files/form-tour-display.png)  


Creating a Form Tour
--------------------

To create a Form Tour, type "new form tour" in awesomebar and hit enter.

1. Enter Title. For eg., 'Creating a Custom Field'
2. Select Reference DocType.
3. Add steps defining each fields.
4. Save the document.

![Custom Field Form Tour](/files/custom-field-form-tour.png) *A Tour to explain creation of Custom Fields*

Configuration Options
---------------------

### Form Tour

1. **Is Standard**: To make a standard Form Tour which will be stored as JSON. Can only be set while developer mode is on.
2. **Save on Completion**: If checked, the last step of the Form Tour will prompt the user to save the document.
3. **Show First Document Tour**: If you want to show the tour of an existing document instead of a new form, enable this. As the name suggests, it gives the tour of the very first document created for this DocType.
4. **Include Name Field**: For some doctypes, the name is set by the user. On enabling this, the name field becomes the first step of the tour.

### Form Tour Steps

1. **Field**: A field from the selected doctype. This will be highlighted with a Title & Description.
2. **Title** & **Description**: To describe the field for its use, impact, and other hidden wirings of the field.
3. **Position**: The position of the highlighting popover is decided by this field. There are multiple options to choose depending upon the position of the highlighted field.
4. **Next Condition**: A code field which expects a valid JS condition which applies on the document. For eg., for a Task DocType Tour, we can check if task priority is set before going to the next condition by setting next condition as follows:

`eval: doc.priority != ""`
5. **Is Table Field**: To be checked if the field to be highlighted is under a child table.
6. **Parent Field**: Table field from the selected doctype. Only visible if **Is Table Field** is checked. Allows user to select a child table field.

Triggering the Tours
--------------------

Once you are done describing the Form & its fields, you are now ready to trigger the tour by using Form API. You just have to initialize the tour with appropriate `tour_name` and then simply start the tour with `frm.tour.start()`.


```
frappe.ui.form.on('Your DocType', {
    onload: function(frm) {
        const tour_name = 'Your Form Tour Name';
        frm.tour.init({ tour_name }).then(() => frm.tour.start());
    }
});
```
