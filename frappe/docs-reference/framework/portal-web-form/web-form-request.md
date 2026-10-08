---
title: "Web Form Request"
space: "Framework"
url: "https://docs.frappe.io/framework/portal-web-form/web-form-request"
updated: "2026-06-26"
---

## Web Form Request

A **Web Form Request** creates a private request link for a **Web Form**.

Use it when a form should not be fully public, but the respondent should still be able to submit it without having a user account. For example, you can send a customer satisfaction survey link to a customer, pre-fill customer-specific values, and keep internal fields hidden from the browser.

## When to Use

Use a **Web Form Request** when:

1. The respondent should open the form through a private link.
2. The respondent may not have a user account.
3. The form should include respondent-specific values.
4. The target document needs hidden values that should not be exposed in the web page.

## Creating a Request

Create a **Web Form Request** and select the *Web Form* it belongs to. A URL-safe key is generated automatically.

The request can define:

- *Expires On*: expiry date and time for the request key.
- *Web Form Values*: JSON values shown in the web form and editable by the respondent.
- *Doc Values*: JSON values applied to the target document on submission, but not sent to the browser.

The request key is used in the web form URL:

```text
/your-web-form-route/new?web_form_request_key=<key>
```

You can copy this URL from the **Web Form Request** form.

## Requiring a Key

Enable *Key required* on the **Web Form** to require a valid **Web Form Request** key.

If *Key required* is enabled and no valid key is provided, the web form cannot be opened or submitted.

If *Login required* is also enabled, both conditions apply: the user must be logged in and must provide a valid request key.

## Pre-filled and Hidden Values

Use *Web Form Values* for fields that should be visible to the respondent. These fields must be included in the **Web Form** fields table.

Use *Doc Values* for fields that should be set on the created document but should not be visible to the respondent. These fields must exist on the target DocType.

The JSON keys must use the underlying field names, for example `customer` or `survey_source`.

Example:

```json
{
 "customer": "CUST-0001",
 "survey_source": "Partner CSAT"
}
```

## Expiry and Usage

If *Expires On* is set, the request key cannot be used after that date and time.

For a single-response web form, the request is marked as used after successful submission and links to the created target document. This allows the same key to be used later for editing or deleting that response if the **Web Form** settings allow it.

For a **Web Form** with *Allow multiple responses* enabled, the request key can be reused for multiple submissions and does not link to a single target document.

## Related Web Form Settings

- *Allow Multiple Responses:*  
If enabled, the same request key can submit multiple responses. In this mode, the **Web Form Request** cannot have a *Reference Docname*, because one request may create many documents.
- *Allow Editing After Submit:*  
If enabled, a request key linked to a response can open and edit that response.
- *Allow Delete:*  
If enabled, a request key linked to a response can delete that response.

