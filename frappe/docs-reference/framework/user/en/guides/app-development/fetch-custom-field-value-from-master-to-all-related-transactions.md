---
title: "Fetch a Field Value from a Document into a Transaction\n"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/guides/app-development/fetch-custom-field-value-from-master-to-all-related-transactions"
updated: "2026-02-17"
---


Let's say, there is a custom field "GSTIN" in Supplier, which should be fetched in Purchase Order.


### Scenario I: You want to keep this field updated

In this scenario, the custom field will be updated automatically based on the value in Supplier when you save the Purchase Order and will be re-updated everytime you save the Purchase Order. Since this field needs to be updated automatically, it overwrites user input. If you want to allow user input, refer to Scenario II.

#### Steps:

1. Create a Custom Field **GSTIN** for *Supplier* document with *Field Type* as **Data**.
 ![](/files/gstin-field-supplier.png)

1. Create another Custom Field **GSTIN** for *Purchase Order* document, but in this case with *Field Type* as **Read Only** or check **Read Only** checkbox. Set **Fetch From** as `supplier.gstin`.
 
![](/files/gstin-field-po-s1.png)

1. Go to the user menu and click "Reload".

1. Now, on selection of Supplier in a new Purchase Order, **GSTIN** will be fetched automatically from the selected Supplier.
 
![](/files/po-gstin-s1.png)

### Scenario II: You want to allow user input if value not found

In this scenario, the value is fetched from the Supplier the first time the Purchase Order is created. If the value is not found in Supplier, you can enter it manually. The value will only be fetched on saving Purchase Order if the field is empty.

#### Steps:

1. Create a Custom Field **GSTIN** for *Supplier* document with *Field Type* as **Data**.
 
![](/files/gstin-field-supplier.png)

1. Create another Custom Field **GSTIN** for *Purchase Order* document with *Field Type* as **Data**. Set **Fetch From** as `supplier.vat_number` and tick the checkbox titled **Fetch If Empty**.
 
![](/files/gstin-field-po-s2.png)

1. Go to the user menu and click "Reload".

1. Now, on selection of Supplier in a new Purchase Order, **GSTIN** will be fetched automatically from the selected Supplier. If GSTIN is not found in supplier, you can enter it manually.
 
![](/files/po-gstin-s2.png)
