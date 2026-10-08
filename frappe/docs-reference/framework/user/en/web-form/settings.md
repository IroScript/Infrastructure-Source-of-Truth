---
title: "Settings"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/web-form/settings"
updated: "2026-06-26"
---

## Webform Settings

There are multiple checkboxs in the `Settings` tab that can be used to enable and disable different functionalities.

### Login Required

If you want responses from guest user, just disable the `login_required` checkbox. Logged In users can also use it. It is disabled by default.

If you only want responses from logged in user just enable the `login_required` checkbox.

> Enabling it will make **Allow Multiple Responses, Allow Editing After Submit, Allow Delete, Allow Comments, Show Attachments** and **Show List** checkboxes visible.

### Key Required

Enable *Key required* when the Web Form should only be opened with a private key from a [Web Form Request](/framework/user/en/web-form/web-form-request).

This is useful for surveys or invitation flows where the respondent does not have a user account, but the form should not be public. The request key can carry visible pre-filled form values and hidden document values.

If *Login required* is also enabled, the user must be logged in and must have a valid request key.

### Allow Multiple Responses

It is used to enable users to give multiple responses which they can see in Webform List View.

> Enabling it will also enable [show_list](/framework/user/en/web-form/settings#show-list) checkbox in List Setting section

### Allow Editing After Submit

It will allow user to edit there submitted responses.

### Allow Delete

It will allow user to delete there submitted responses from Webform List View.

### Anonymous

By setting this the response received will be anonymous.

### Apply Document Permission

By default if user has read access to the documents submitted by different users it will be visible in the Webform List View. But he/she can only open the record from list view if **Apply Document Permission** checkbox is checked.

### Allow Print

It will add a print button to print the document. It will only be visible on View Mode.

### Allow Comments

It will add comment section below the webform where users can communicate. All the comments will be linked to the document.

### Show Attachments

It will show all the attachments attached in the document in Attachment Section.

### Max Attachment Size (in MB)

It will restrict users to attach large files.

### Allow Incomplete Forms

It will allow submission of forms even if mandatory fields are not populated.

## List Settings

![Web Form](/files/v-14-web-form-list-settings.png)



### Show List

It will enable `List View` where you can see all the submitted forms. You can only open the form that you own. 

![Web Form](/files/v-14-web-form-list-view.png)





> If `apply_document_permissions` is enabled you can open other forms.

### Title & List Columns

You can change the title of the list and also can add/remove/arrange list view columns 

![Web Form](/files/v-14-web-form-update-title-list-columns.png)



![Web Form](/files/v-14-web-form-updated-list-view.png)



## Sidebar Settings

![Web Form](/files/v-14-web-form-show-sidebar.png)



### Show Sidebar

Show webform with sidebar. Select or create a website sidebar where you can add link to current webform and other related webforms or webpages. 

![Web Form](/files/v-14-web-form-with-sidebar.png)

