---
title: "Notifications"
space: "Framework"
url: "https://docs.frappe.io/framework/notifications"
updated: "2026-02-17"
---

The **Notification** doctype in Frappe Framework provides a powerful way to automate notifications across different channels when specific events occur in your system. This guide explains how to configure and use notifications effectively.

## General Settings

- **Enabled**: Toggle to activate or deactivate a notification.
- **Channel**: Select the delivery method for your notification:
  - **Email**: Send notifications via email
  - **Slack**: Send notifications to a Slack channel
  - **System Notification**: Display notifications within the Frappe interface
  - **SMS**: Send notifications via SMS (requires SMS Settings configuration)
- **Is Standard**: For developer mode; marks the notification as part of a standard module

## Event Triggers

Notifications can be triggered based on various events:

### Document Events

- **New**: Triggered when a new document is created
- **Save**: Triggered when a document is saved
- **Submit**: Triggered when a document is submitted
- **Cancel**: Triggered when a document is cancelled

### Date-Based Events

- **Days Before**: Triggered a specific number of days before a date field value
- **Days After**: Triggered a specific number of days after a date field value
- When using these events:
  - **Reference Date**: Select the date field to monitor
  - **Days Before or After**: Specify number of days before/after the date to trigger

### Value-Based Events

- **Value Change**: Triggered when a specific field's value changes
  - **Value Changed**: Select the field to monitor for changes

### Method-Based Events

- **Method**: Triggered when a specific document method is called
  - **Trigger Method**: Specify the method name (e.g., "before_insert", "after_update")

### Custom Events

- **Custom**: For programmatically triggered notifications

## Conditional Triggers

You can make notifications more targeted by adding conditions:

- **Condition**: A Python expression that must evaluate to `True` for the notification to be sent
- The condition has access to:
  - `doc`: The document that triggered the notification
  - `nowdate()`: Current date function
  - `frappe.utils`: Utility functions

### Examples

- The _Status_ of the document is "Open"

    ```python
    doc.status=="Open"
    ```

- The document's _Due Date_ matches the current date

    ```python
    doc.due_date==nowdate()
    ```

- The total is bigger than 40,000

    ```python
    doc.total > 40000
    ```

## Recipients Configuration

### Email, System Notification, and SMS Channels

Configure recipients using the Recipients table:

1. **Receiver Type**:

   - **By Document Field**: Select a field containing email addresses/phone numbers
   - **By Role**: Select a role whose users will receive the notification
   - **Custom**: Specify custom recipients

2. **Additional Options**:

   - **CC/BCC**: For email notifications
   - **Condition**: Python expression to conditionally include recipients
   - **Send to All Assignees**: Include all users assigned to the document

### For Slack Channel

- Select a predefined Slack Webhook URL from the dropdown

## Message Configuration

### Subject (for Email, Slack, and System Notifications)

- Enter the subject line text
- Support for Jinja templates: `{{ doc.name }} Delivered`

### Message Body

- **Message Type**: Select between HTML, Markdown, or Plain Text (available in developer mode only)
- **Message**: Enter the notification content
- Uses Jinja templating for dynamic content

### Templating Variables

- `{{ doc }}`: Access any field from the triggering document (e.g., `{{ doc.customer }}`)
- `{{ comments }}`: Access document comments (e.g., `{{ comments[-1].comment }}`)
- `{% if %}...{% endif %}`: Conditional logic
- `{{ nowdate() }}`: Current date

### Template Example

```html
<h3>Order Overdue</h3>

<p>Transaction {{ doc.name }} has exceeded Due Date. Please take necessary action.</p>

<!-- show last comment -->
{% if comments %}
Last comment: {{ comments[-1].comment }} by {{ comments[-1].by }}
{% endif %}

<h4>Details</h4>

<ul>
<li>Customer: {{ doc.customer }}
</li><li>Amount: {{ doc.grand_total }}
</li></ul>
```

## Advanced Options

### Attachment Settings

- **Attach Print**: Attach a PDF printout of the document
    - **Print Format**: Select a specific print format for the attached PDF
- **Attach Files**:
    - "All": sends all files that are attached to the record that triggered the notification
    - "From Field": sends a file from a specific attachment field
        - **From Attach Field**: Select the field that holds the attachment you want to send

### Post-Notification Actions

- **Set Property After Alert**: Update a field after sending the notification
- **Value To Be Set**: The value to set in the specified field

## Best Practices

1. **Test your notifications**: Use the "Get Alerts for Today" button to test date-based notifications.
2. **Keep conditions specific**: Make sure your conditions are targeted to avoid notification fatigue.
3. **Use templating wisely**: Make messages clear and include only relevant information.
4. **Verify recipient fields**: Ensure fields contain valid email addresses or phone numbers.
5. **Consider permission levels**: Recipients must have permission to access documents referenced in notifications.

## Troubleshooting

- If notifications aren't sending, check that the document meets all conditions.
- For email notifications, verify email settings are properly configured.
- For SMS notifications, ensure SMS settings are configured.
- For Slack notifications, verify webhook URL is valid and active.
- Check server logs for any errors related to notification delivery.

## Technical Notes

- Notifications are processed asynchronously to avoid impact on system performance.
- Date-based events are checked daily via a scheduled job.
- Document-event notifications are triggered in real-time when the associated action occurs.
- Conditions and templates are evaluated in a restricted environment for security.

By effectively configuring the Notification doctype, you can keep users informed about important events and automate communication across your Frappe application.
