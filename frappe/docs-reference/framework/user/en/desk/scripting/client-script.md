---
title: "Client Script"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/desk/scripting/client-script"
updated: "2026-02-17"
---

A Client Script lets you dynamically define a custom Form Script that is executed on a user's browser. If you choose to utilize non standard tools or libraries, make sure to test them on different browsers to ensure compatibility across your userbase.


> In Version 13, **Custom Script** was renamed to **Client Script**
> 
> 

1. How to create a Client Script
--------------------------------

To create a Client Script

1. To add/edit Client Script, ensure your role is System Manager.
2. Type "New Client Script" in the awesomebar and hit enter to create a new Client Script document.
3. Select the DocType whose form you wish to customize.
4. Update the script using the preset template and save.
5. Head over to the DocType you've customized and see the changes.

2. Features
-----------

As compared to the restrictive nature of Server Scripts, everything is fair game in Client Scripts. This is because the frontend APIs are secure by design. You can utilize all of JavaScript APIs, along with Frappe's and any other JS or CSS library you might've customized Desk with.


> The validations you add through Client Script will only be applied while using the standard form view accessible through the browser. In case you wish for those to be applied through API or [System Console](/framework/v14/user/en/desk/scripting/system-console) access too, use [Server Scripts](/framework/v14/user/en/desk/scripting/server-script).
> 
> 

3. Examples
-----------

### 3.1 Custom validation

Add additional form validations while creating or updating a document from Frappe's standard form view.


```
// additional validation on Task dates
frappe.ui.form.on('Task', 'validate', function(frm) {
    if (frm.doc.from_date < get_today()) {
        msgprint('You can not select past date in From Date');
    }
});
  

```
### 3.2 Fetching values on field updates

Fetch `local_tax_no` on changing value of the `customer` field.


```
cur_frm.add_fetch('customer', 'local_tax_no', 'local_tax_no');
  

```
### 3.3 Customize field properties

Make a field `ibsn` read only after creating the document.


```
// make a field read-only after saving
frappe.ui.form.on('Task',  {
    refresh: function(frm) {
        frm.set_df_property('ibsn', 'read_only', !frm.is_new());
    }
});
  

```
### 3.4 Customize field properties

Calculate incentives on a Sales Invoice form on save.


```
// calculate sales incentive
frappe.ui.form.on('Sales Invoice',  {
    validate: function(frm) {
        // calculate incentives for each person on the deal
        total_incentive = 0
        $.each(frm.doc.sales_team,  function(i,  d) {
            // calculate incentive
            let incentive_percent = 2;
            if(frm.doc.base_grand_total > 400) incentive_percent = 4;
            // actual incentive
            d.incentives = flt(frm.doc.base_grand_total) * incentive_percent / 100;
            total_incentive += flt(d.incentives)
        });
        frm.doc.total_incentive = total_incentive;
    }
});
```
### 3.5 Filter email recipients

You can restrict the available emails via a **Client Script**. Every form can specify what email addresses should be selectable. This reduces the cognitive load for the user and avoids sending emails to wrong recipients.

`CommunicationComposer` (the email dialog) will check if there is a **Client Script** supplying filters for the "recipients", "cc" and "bcc" fields. For example, if a **Quotation** should only show email addresses linked to the recipient of the **Quotation**, we can add the following script:


```
frappe.ui.form.on("Quotation", {
    get_email_recipient_filters: function (frm, field) {
        // field can be "recipients", "cc" or "bcc"
        if (field === "recipients") {
            return [
                [
                    "Dynamic Link",
                    "link_doctype",
                    "=",
                    frm.doc.quotation_to
                ],
                [
                    "Dynamic Link",
                    "link_name",
                    "=",
                    frm.doc.party_name
                ],
            ];
        }
    },
    // ...
};
```
The filters are referring to the **Contact** DocType and it's *Links* child table.

Even with filters, it remains possible to paste arbitrary recipients.

### 3.6 Set default email recipients

In standard processes like **Sales Order** -> **Delivery Note** -> **Sales Invoice**, the email recipients are often pre-defined. For example, this could be done in advance by the account manager.

You can set default email recipients via a **Client Script**. Every form can programmatically supply it's own default recipients.

`CommunicationComposer` (the email dialog) will check if there is a **Client Script** supplying default recipients. For example, if your **Quotation** DocType contains a field named *BCC* (`"custom_bcc"`), you can add the following **Client Script** to use it as default BCC in the email dialog:


```
frappe.ui.form.on("Quotation", {
    get_email_recipients: function (frm, field) {
        // field can be "recipients", "cc" or "bcc"
        if (field === "bcc") {
            return [frm.doc.custom_bcc]
        }
    },
    // ...
};
```
  


