---
title: "Workspace"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/desk/workspace"
updated: "2026-02-17"
---

Workspace is the first page you land on when you log in.
It also has a dedicated sidebar where you can rearrange the workspace position according to your convenience.

The workspace itself is a tool to build user-specific pages. 
It comes with some standard workspaces which are listed in the `PUBLIC` section in the sidebar and are visible to all users.
You can also create private workspaces which will only be visible to the logged-in user(owner) in the `MY WORKSPACES` section. 

Let's build one and check out some cool features.

###Create New Workspace
1. Click on **Create Workspace** button.
2. Enter Title and click on Create.

![Create Workspace](/files/CreateWorkspace.gif)

###Create Child Workspace
1. Click on **Create Workspace** button.
2. Enter Title.
3. Select Home in the Parent field and click on Create.

![Create Child Workspace](/files/ChildPage.gif)

###Workspace Blocks
The workspace block is a building block for the workspace page.
These blocks can be placed in different variations to build an ideal workspace for a specific use case.

[Learn More →](/framework/v14/user/en/desk/workspace/blocks)

![Workspace Blocks](/files/WorkspaceBlocks.gif)
###Sidebar


![Workspace Sidebar](/files/WorkspaceSidebar.png)


There are two sections in the sidebar `MY WORKSPACES` & `PUBLIC`.


You can create as many private workspaces as you want.
It will only be visible to the currently logged-in user(owner) under the `MY WORKSPACES` section


All the standard workspaces comes under `PUBLIC` section. 
You can also create more public workspaces. These workspaces will be visible to all users.
 


[More →](/framework/v14/user/en/desk/workspace/customization#customizing-workspaces) 



>Only users with **Workspace Manager Role** can create, edit or delete public workspaces

###Customization
Workspace has two modes **Read Only Mode** and **Edit Mode**. You can start customizing your workspace by clicking on the **Edit** button.
[Customizing Workspaces](/framework/v14/user/en/desk/workspace/customization#customizing-workspaces) and [Customizing Workspace Page](/framework/v14/user/en/desk/workspace/customization#customizing-workspace-page) are two different things.

>Adding new blocks from the workspace document will not work as the new workspace doesn't know exactly where to add that block (at which position). You can update the existing blocks from the workspace document but it is not recommended either. The best practice would be to use the new workspace builder UI to do all kinds of customization.