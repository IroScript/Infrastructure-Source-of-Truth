---
title: "Field Types"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/basics/doctypes/fieldtypes"
updated: "2026-07-16"
---

There are variety of fieldtypes available in Frappe Framework. Each one has its own use case and can be used to input and store different types of data in a document. Fieldtypes are used to render components in desk as well as web forms.

![Field Types Dropdown Menu](/files/fieldtypes.png)



#### Data

The data field will be a **simple text field**. It allows you to enter a value of up to 140 characters, making this the most generic field type.

You can enable validations for the following types of data:

1. Name
2. Email
3. Phone
4. URL

by setting the options to "Name", "Email", "Phone" or "URL" respectively.

![Data field types](/files/data-field-1.png)



Set the options to "IBAN" to enable formatting in blocks of 4 characters.

#### Link

Link field is connected to another master from where it fetches data. For example, in the Quotation master, the Customer is a Link field. To know more, [click here](https://erpnext.com/docs/user/manual/en/customize-erpnext/articles/creating-custom-link-field).

#### Dynamic Link

Dynamic Link field is one which can search and hold value of any document/doctype. [Click here](https://docs.frappe.io/erpnext/user/manual/en/dynamic-link-fields) to learn how Dynamic Link Field functions.

#### Check

This will enable you to have a checkbox here. You can set the `Default` value to 1 and it will be checked by default.

![Check Field Preview](/files/check-field-2.png)



![Check Field Edit](/files/check-field-1.png)



#### Select

Using the field type "Select", you can create a drop-down field. You can specify all selectable values in the *Options* field, each value separated by a new line.

One of the selectable values can be copied into the *Default* field. This value will then be selected by default in a new form.

If you enable the *Sort Options* checkbox, values will be displayed in alphabetical order (in the user's language).

The following screenshot shows how a "Select" field can be defined in the **DocType** or via **Customize Form**:

![define_select_field](/files/define_select_field.png "define_select_field.png")



And this is how it will be rendered in a new form:

![use_select_field](/files/use_select_field.png "use_select_field.png")



#### Table

With a "Table" field, you can render another DocType as a child table within your form.

First, you'll have to choose or define a DocType that has the Checkbox *Is Child Table* enabled. Then you can add a field of type "Table" and paste the name of your child table DocType into the *Options* field.

For example, ERPNext defines a child DocType called "Purchase Receipt Item" with *Is Child Table* enabled:

![define_child_table_doctype](/files/define_child_table_doctype.png "define_child_table_doctype.png")



Another DocType called "Purchase Receipt" has a field of type "Table", with *Options* set to above child doctype "Purchase Receipt Item":

![define_child_table_field](/files/define_child_table_field.png "define_child_table_field.png")



Finally, the child table will be rendered in the Purchase Receipt form:

![child_table_in_form](/files/child_table_in_form.png "child_table_in_form.png")



#### Attach

Attach field allows you to browse a field from the File Manager and attach the same herein.

![Field Types](/files/attach_fieldtype.png)



#### Attachment Gallery

The Attachment Gallery field displays files attached to the current document in a responsive gallery. Images appear as thumbnails and can be opened in a larger preview. Other file types appear as file cards and open in a new tab.

Users with write permission can upload and delete attachments directly from the gallery. Enabling *Read Only* hides these actions. The document must be saved before files can be uploaded.

By default, the gallery displays all attachments belonging to the document. Use *Filters* to restrict the displayed **File** records. For example, to show only PDF files:

```json
[["File", "file_type", "=", "PDF"]]
```

To show only files uploaded through a particular gallery, filter by `attached_to_field` using the gallery’s field name:

```json
[["File", "attached_to_field", "=", "marketing_assets"]]
```

Enable *Make Attachment Public (by default)* if files uploaded through the gallery should be public by default.

#### Attach Image

Attach Image is a field wherein you will be allowed to attach Images of the format jpeg, png, etc. This becomes the Image representing that particular DocType. For e.g., you would want the image of an Item in its DocType, you can choose your field to be an Attach Image Field.

#### Text Editor

Text Editor is a text field and renders a **WYSIWYG** editor for input. It has various text-formatting options.

![Field Types](/files/text_editor_field.png)



#### Date

This field will enable you to enter the Date in this field.

![Field Types](/files/date_fieldtype.png)



#### Date and Time

This field will give you a date and time picker. The current date and time (as provided by your computer) are set by default.

#### Barcode

In this field, you can specify the field as Barcode which will allow you to enter a Barcode number. Once you do that, the Barcode would automatically get generated against the number.

![barcode](/files/barcode.png)



#### Button

This field lets you place a button in a document. This can be used to perform specific actions like publishing a blog post, triggering an action etc.

#### Code

This fieldtype can be used to take `code` as input. A code editor is rendered in the document form. Optionally, you can provide a langauge in the fieldtype options to enable syntax highlighting. For example, below is a `Code` type field with options set to `Python`:

You can enable basic syntax validations for following languages by setting "Option".

1. Python (for scripts)
2. PythonExpression (for simple one-line expressions that must evaluate to a value) E.g. Assignment Rule condition

Example of differences between `Python` and `PythonExpression`:

- `variable = 42` is a valid `Python` code but not a valid `PythonExpression` since the assignment doesn't evaluate to any value.
- `variable == 42` is both valid `Python` code and valid `PythonExpression` as the expresion can evaluate to some value.

![Field Types](/files/code_fieldtype.png)



#### Color

This will let the user input a color via a rendered color picker or directly input a hexadecimal color.

![Field Types](/files/color_fieldtype.png)



#### Column Break

This is a `'meta'` fieldtype that does not store any input data but can be used to indicate a column break in the document view or form.

For example,

![Field Types](/files/column_break_fieldtype_1.png)



will result into:

![Field Types](/files/column_break_fieldtype_2.png)



#### Currency

Currency field holds numeric value, like Item Price, Amount, etc. Currency field can have value up to six decimal places. Also, you can have a currency symbol being shown for the currency field.

#### Float

Float field carries numeric value, up to nine decimal places.

#### Geolocation

A Geolocation field will show a map view on which you can draw polygons, lines, and points. The data is stored as a GeoJSON [feature_collection](https://tools.ietf.org/html/rfc7946#section-3.3).

If you add a Geolocation field with the exact field name "location", you will get an additional map view (the equivalent of list view, but on a map). By the way, this also works if you create two separate fields named "latitude" and "longitude".

Note: Frappe uses the "Leaflet" library which stores coordinates as [latitude, longitude] which is the reverse of what GeoJSON usually does.

#### HTML

This will render the content entered in `Options` as HTML in the document form or view page. Here is an example:

![Field Types](/files/html_fieldtype_1.png)



will result into:

![Field Types](/files/html_fieldtype_2.png)



#### Image

Image field will render an image file selected in another attach field.

For the Image field, under Option (in Doctype), a field name should be provided where the image file is attached. By referring to the value in that field, the image will be a reference in the Image field.

![Field Types](/files/image_fieldtype_1.png)



will result into:

![Field Types](/files/image_fieldtype_2.png)



#### Int (Integer)

The integer field holds numeric value, without decimal place.

#### Small Text

Small Text field carries text content and has more character limit than the Data field.

#### Long Text

You can define your field to a Long Text Field when you would want to enter data with an unlimited character limit.

#### Text

This field type would allow you to add text in the field. The character limit in Small text, Long text and Text fields shall be determined based on the Relational Database Management System.

#### Markdown Editor

This field will allow you to add the text in markdown. This fieldtype also provides a `Preview` view of rendered HTML:

![Field Types](/files/md_fieldtype_1.png)



when preview is clicked:

![Field Types](/files/md_fieldtype_2.png)



#### Password

The password field will have decoded value in it. This type of field can be used to store sensitive data like passwords, pass phrases, secret keys etc.

#### Percent

You can define the field as a Percentage field which in the background will be calculated as a percentage.

#### Rating

This field can be used to display an interactive star rating input. The default star count shown is 5, however, this can easily be changed by entering a number ranging from 3 - 10 in the options field for that particular rating field.

![Check Field Edit](/files/rating-field.png)



You can also provide half ratings e.g 3.5 out of 5.

![Half Rating](/files/Screenshot 2021-12-20 at 4.52.09 PM.png)



#### Read Only

Read Only field will carry data fetched from another form which will be non-editable. You should set Read Only as field type if its source for value is predetermined.

#### Section Break

Section Break is used to divide the form into multiple sections. Any fields that follow (and before any other `Section Break`) a `Section Break` field will be part of this new section.

![Field Types](/files/section_break_fieldtype.png)



### Tab Break

Tab Break is used to divide the form into multiple tabs. Any field that follow till the next `Tab Break` will be the part of this new tab.

![Tabs](/files/form-tabs.png)



**Note:** If the `fields` table of a DocType is not started with a Tab Break, a default Tab Break named `Details` will be used. This happens only if a DocType has atleast one `Tab Break` in the `fields` table.

#### Signature

You can define the field to be a Signature field wherein you can add the Digital Signature in this field. Read documentation for [Signature Field](https://docs.erpnext.com/docs/v14/user/manual/en/customize-erpnext/articles/electronic-signature) to know more.

#### Table MultiSelect

This is a combination of 'Link' type and 'Table' type fields. Instead of a child table with 'Add Row' button, in one field multiple values can be selected.

#### Time

This is a Time field where you can define the Time in the field.

#### Duration

You can use the Duration field if you want to define a timespan.

If you don't want to track duration in terms of days or seconds, you can enable "Hide Days" and "Hide Seconds" options respectively in your Form. One day is equivalent to 24 hours.

#### JSON

This creates a JSON type column in your database. Also adds syntax highlighting for Desk controls.