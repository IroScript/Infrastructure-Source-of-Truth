---
title: "Assignments and Todos"
space: "Framework"
url: "https://docs.frappe.io/framework/assignments-and-todos"
updated: "2026-02-17"
---

## Overview

The **ToDo** doctype in Frappe Framework helps users track and manage tasks assigned to themselves or to others. ToDos can be created independently or linked to other documents in the system, providing a centralized task management system.

## ToDo Fields

- *Status*: Can be "Open", "Closed", or "Cancelled"
- *Priority*: Set as "High", "Medium", or "Low" (default is "Medium")
- *Color*: Optional color tagging for visual identification
- *Due Date*: When the task should be completed
- *Description*: The main content of the task (required)
- *Reference Type* & *Name*: Optional link to a related document (e.g., a specific Issue, Lead, etc.)
- *Role*: Optional role assignment
- *Assigned* By: User who created or assigned the task
- *Allocated To*: User responsible for completing the task

## Creating ToDos

ToDos can be created in several ways:

1. **Direct Creation**:

   - Navigate to the ToDo list
   - Click on "Add ToDo" button
   - Fill in the required details and save

2. **Via Assignment**:

   - From any document (e.g., Issue, Task), use the "Assign To" function
   - The system creates a ToDo and links it to that document

3. **Via Email**:

   - Send emails to the system with appropriate settings
   - Email content is converted to ToDos automatically (ToDo is in the `email_append_to` settings)

4. **Via Assignment Rules**:

   - Set up automatic assignments based on conditions
   - The system creates ToDos when conditions are met (note: Assignment Rules cannot be set on the ToDo doctype itself)

## Managing ToDos

### Marking as Completed

To mark a **ToDo** as completed:

- Open the ToDo
- Change the status to "Closed"
- Save the document

Only the assignee (the user in the "Allocated To" field) can close their assigned ToDos. When done through the UI, the system will show an error if someone else tries to complete another person's ToDo.

### Cancelling ToDos

To cancel a **ToDo**:

- Open the ToDo
- Change the status to "Cancelled"
- Save the document

Cancelling differs from completion as it indicates the task won't be done rather than has been done.

### Impact of Due Date

The due date field:

- Helps in prioritizing tasks
- Provides a target completion date
- Is used in listing views to sort and filter ToDos
- Is used by Assignment Rules for automated due date management

However, the system does not automatically send reminders when due dates are approaching or have passed. If you need this, consider creating a custom **Notification**.

## Notifications

The system sends notifications in the following scenarios:

1. **When a document is assigned or the assignment is cancelled**:

   - The assignee receives a notification
   - The notification includes the task description and who assigned it, or cancelled the assignment

3. **Global Notification Counter**:

   - Open ToDos contribute to the notification counter in the Frappe interface
   - The counter helps users see at a glance how many open tasks they have

## Permissions

- Users can see ToDos assigned to them or created by them
- System Managers have access to all ToDos
- The "All" role has permission to create, read, write, and delete ToDos

## Integration with Other Documents

When a **ToDo** is linked to another document:

- A comment is added to the referenced document when the ToDo is assigned
- A comment is added when the ToDo is completed or cancelled
- The list of assigned users is updated in the referenced document's `_assign` field
- When viewing the referenced document, users can see who the document is assigned to

## Working with Assignment Rules

While Assignment Rules cannot be created for the **ToDo** doctype itself, they can create ToDos for other doctypes:

- Create rules based on document conditions
- Assign tasks using round-robin, load balancing, or field-based assignment
- Automatically set due dates based on document fields
- Close or reassign ToDos when document conditions change

Assignment Rules provide powerful automation for task management across the system.
