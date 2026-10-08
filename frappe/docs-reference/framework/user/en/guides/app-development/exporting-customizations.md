---
title: "Exporting Customizations to your App"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/guides/app-development/exporting-customizations"
updated: "2026-02-17"
---

A common use case is to extend a DocType via Custom Fields and Property Setters for a particular app. To save these settings to an app, go to **Customize Form**

You will see a button for **Export Customizations**

![](/files/export-custom-1.png)  


Here you can select the module and whether you want these particular customizations to be synced after every update.

The customizations will be exported to a new folder `custom` in the module folder of your app. The customizations will be saved by the name of the DocType

![](/files/export-custom-2.png)  


When you do `bench update` or `bench migrate` these customizations will be synced to the app.


> Warning: Using this feature whenever a customization are synced all property setters and custom permissions are replaced on site with what's specified in the code. If this behaviour is not desired then you should not use this feature. 
> 
> 

