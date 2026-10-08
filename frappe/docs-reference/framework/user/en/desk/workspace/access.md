---
title: "Access"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/desk/workspace/access"
updated: "2026-02-17"
---

Workspaces can be restricted based on Modules and Roles.

### Modules

Users can have access to different modules and standard workspaces are visible based on access to those modules.

In the below GIF you can see when Website Module access was removed for user John Doe, he was not able to see Website Workspace. ![Module Access](/files/ModuleAccess.gif)  


### Roles

Users can have access to modules but what if you still want those users to not see the standard workspace of that module. Then you can restrict access based on the roles given to that user.

Check below Example:

Jack Doe is a manager with Workspace Manager Role. He only wants user with Website Manager Role to see the Website Workspace.ence such a configuration is made as follows: ![Role Access 1](/files/RoleAccess1.gif)  


To test this, Jane Doe is given the Website Module access and not given the Website Manager role. Due to the configuration done above, she will not be able to see Website Workspace as shown below. Where as John Doe who has Website Module access and Website Manager role, will be able to see the Website Workspace. ![Role Access 2](/files/RoleAccess2.gif)  


### Default Workspace

The default workspace that will be shown when the user first logs in can be configured for each user. By default, the user will be shown the workspace they were last in. The default workspace can be selected using the "Default Workspace" field of the User settings form, that can be accessed through the "My Settings" option of your avatar menu.

