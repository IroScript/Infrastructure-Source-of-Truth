---
title: "Page API"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/api/page"
updated: "2026-02-17"
---

Every screen inside the Desk is rendered inside a `frappe.ui.Page` object.

frappe.ui.make_app_page
-------------------------

Creates a new Page and attaches it to parent.


```
let page = frappe.ui.make_app_page({
    title: 'My Page',
    parent: wrapper // HTML DOM Element or jQuery object
    single_column: true // create a page without sidebar
})
  

```
![New Page](/files/new-page.png) *New Page*

Page methods
------------

This section lists out the common methods available on the page instance object.

page.set_title
---------------

Set the page title along with the document title. The document title is shown in browser tab.


```
page.set_title('My Page')
  

```
![Page Title](/files/page-set-title.png) *Page Title*

page.set_title_sub
--------------------

Set the secondary title of the page. It is shown on the right side of the page header.


```
page.set_title_sub('Subtitle')
  

```
![Page Subtitle](/files/page-set-title-sub.png) *Page Subtitle*

page.set_indicator
-------------------

Set the indicator label and color.


```
page.set_indicator('Pending', 'orange')
  

```
![Page Indicator](/files/page-set-indicator.png) *Page Indicator*

page.clear_indicator
---------------------

Clear the indicator label and color.


```
page.clear_indicator()
  

```
page.set_primary_action
-------------------------

Set the primary action button label and handler. The third argument is the icon class which will be shown in mobile view.


```
let $btn = page.set_primary_action('New', () => create_new(), 'octicon octicon-plus')
  

```
![Page Primary Action](/files/page-primary-action.png) *Page Primary Action*

page.clear_primary_action
---------------------------

Clear primary action button and handler.


```
page.clear_primary_action()
  

```
page.set_secondary_action
---------------------------

Set the secondary action button label and handler. The third argument is the icon class which will be shown in mobile view.


```
let $btn = page.set_secondary_action('Refresh', () => refresh(), 'octicon octicon-sync')
  

```
![Page Secondary Action](/files/page-secondary-action.png) *Page Secondary Action*

page.clear_secondary_action
-----------------------------

Clear secondary action button and handler.


```
page.clear_secondary_action()
  

```
page.add_menu_item
--------------------

Add menu items in the Menu dropdown.


```
// add a normal menu item
page.add_menu_item('Send Email', () => open_email_dialog())

// add a standard menu item
page.add_menu_item('Send Email', () => open_email_dialog(), true)
  

```
![Page Menu Dropdown](/files/page-menu-dropdown.png) *Page Menu Dropdown*

page.clear_menu
----------------

Remove Menu dropdown with items.


```
page.clear_menu()
  

```
page.add_action_item
----------------------

Add menu items in the Actions dropdown.


```
// add a normal menu item
page.add_action_item('Delete', () => delete_items())
  

```
![Page Actions Dropdown](/files/page-actions-dropdown.png) *Page Actions Dropdown*

page.clear_actions_menu
-------------------------

Remove Actions dropdown with items.


```
page.clear_actions_menu()
  

```
page.add_inner_button
-----------------------

Add buttons in the inner toolbar.


```
// add a normal inner button
page.add_inner_button('Update Posts', () => update_posts())
  

```
![Page Inner Button](/files/page-inner-button.png) *Page Inner Button*


```
// add a dropdown button in a group
page.add_inner_button('New Post', () => new_post(), 'Make')
  

```
![Page Inner Button Group](/files/page-inner-button-group.png) *Page Inner Button Group*

### page.change_custom*button*type

Change a specific custom button type by label (and group).


```
// change type of ungrouped button
page.change_inner_button_type('Update Posts', null, 'primary');

// change type of a button in a group
page.change_inner_button_type('Delete Posts', 'Actions', 'danger');
  

```
page.remove_inner_button
--------------------------

Remove buttons in the inner toolbar.


```
// remove inner button
page.remove_inner_button('Update Posts')

// remove dropdown button in a group
page.remove_inner_button('New Posts', 'Make')
  

```
page.clear_inner_toolbar
--------------------------

Remove the inner toolbar.


```
page.clear_inner_toolbar()
  

```
page.add_field
---------------

Add a form control in the page form toolbar.


```
let field = page.add_field({
    label: 'Status',
    fieldtype: 'Select',
    fieldname: 'status',
    options: [
        'Open',
        'Closed',
        'Cancelled'
    ],
    change() {
        console.log(field.get_value());
    }
});
  

```
![Page Form Toolbar](/files/page-add-field.png) *Page Form Toolbar*

page.get_form_values
----------------------

Get all form values from the page form toolbar in an object.


```
let values = page.get_form_values()
// { status: 'Open', priority: 'Low' }
  

```
page.clear_fields
------------------

Clear all fields from the page form toolbar.


```
page.clear_fields()
  

```
