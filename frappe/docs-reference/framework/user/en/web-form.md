---
title: "Web Form"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/web-form"
updated: "2026-06-26"
---

Frappe provides an easy way to generate forms for your website with very little configuration. These forms may be public (anyone can fill them up), can be configured to require login, or can be made available through private request links.

![Web Form](/files/v-14-webform-conference-register.png)

## Creating a Web Form

To create a Web Form, type "new web form" in awesomebar and hit enter.

1. Enter Title
2. Select DocType for which the record should be created.
3. Add some introduction (Optional).
4. Click on "Get Fields" button to get all fields from selected doctype OR select fields for your web form.
5. Publish it and you are good to go.

![Create Web Form](/files/v-14-webform.png)

![Web Form Fields](/files/v-14-webform-fields.png)

[Customize Web Form →](/framework/v14/user/en/web-form/customization)

[Private Web Form Requests →](/framework/user/en/web-form/web-form-request)

## Standard Web Forms

If you check the "Is Standard" checkbox, a new folder will be created in the  
`module` of the Web Form. In this folder, you will see a `.py` and `.js` file  
that you can use to configure the web form. These files need to be checked into  
version control with your custom app. You can install this app on any site and  
it will have this web form installed.

> `Is Standard` field will only be visible when you are in developer mode.

