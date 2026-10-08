---
title: "Using Vue in a Desk Page"
space: "Framework"
url: "https://docs.frappe.io/framework/using-vue-inside-a-desk-page"
updated: "2026-09-29"
---

Using Vue to add pages to your Desk based app gives you a best-of-both-worlds type of convenience:

1. You get to use Vue with its reactivity and composability
2. You get to use [Frappe JS APIs](/framework/user/en/api/server-calls)

This is possible without having to manually configure a Vue app. You can follow
the steps below to set it up.

### Create a Page

Navigate to the Page DocType (at `/app/page`) and create a new Page entry.
New files will be created for your page in the module you select.

![Page DocType!](/files/page.png)

### Check created files

Under the module folder in your app's directory, you'll find a new folder with three
files in it:

```
└── app
    └── app
        └── module
            └── page
                └── test_vue
                    ├── __init__.py
                    ├── test_vue.json
                    └── test_vue.js
```

Among these, in the newly created JavaScript file you'll see `make_app_page` being called:

```javascript
frappe.pages['test-vue'].on_page_load = function (wrapper) {
  var page = frappe.ui.make_app_page({
    parent: wrapper,
    title: 'None',
    single_column: true,
  });
};
```

This is used to create a new page. See the [Page API](/framework/user/en/api/page) for more info.

This file will be loaded when you visit to `/app/test-vue`, you can visit the
path and an empty page with the title "None" will be shown.


### Creating Vue files

To use Vue, your `.vue` source files need to be transpiled and bundled. Frappe
Framework does this out of the box.

We'll now create two files, a `.vue` file, and a `.js` file that loads your Vue
code. You can add these files under your app's `public/js` folder:

```
└── app
    └── app
        └── public
            └── test_vue
                ├── TestVue.vue
                └── test_vue.bundle.js
```

First, we'll create the `.vue` file `TestVue.vue`. Some simple Vue code to test the setup:

```vue
<script setup>
import { ref } from 'vue';

const message = ref('Hello, World');
</script>
<template>
  <h1>{{ message }}</h1>
</template>
```

Second, the `.js` file that loads the Vue code:

```javascript
import { createApp } from 'vue';
import TestVue from './TestVue.vue';

// A simple function to mount your Vue app
function setup_vue(wrapper) {
  const app = createApp(TestVue);
  app.mount(wrapper.get(0));
  return app;
}

// We'll call this function from the generated test_vue.js file
frappe.ui.setup_vue = setup_vue;
export default setup_vue;
```

### Require the bundle

In the generated `test_vue.js` file, add the following code to load the Vue app:

```javascript
frappe.pages['test-vue'].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: 'Test Vue',
    single_column: true,
  });

  // hot reload when in developer mode
  if (frappe.boot.developer_mode) {
    frappe.hot_update ??= frappe.hot_update;
    frappe.hot_update.push(() => load_vue(wrapper));
  }
};
frappe.pages['test-vue'].on_page_show = (wrapper) => load_vue(wrapper);

// Simple callback function to load Vue in the page
async function load_vue(wrapper) {
  const $parent = $(wrapper).find('.layout-main-section');
  $parent.empty();

  // Require the bundle and mount the Vue app
  await frappe.require('test_vue.bundle.js');
  frappe.test_vue_app = frappe.ui.setup_vue($parent);
}
```

This will call the `load_vue` function that `requires` the bundle and mounts the
Vue app when the page is loaded or shown.


### Build or run the dev server

To build your code you can call:

```bash
bench build
```

Note: this will build the frontend code for all the apps on your bench.

To run the dev server you can navigate the frappe app's (i.e `bench/apps/frappe`) folder and run:

```bash
npm run build -- --apps app --watch
```

This will watch for any changes in your app and rebuild the code, which should
trigger a hot reload in your browser.

If you've done everything right you should see your page show the Vue app's message:

![Vue Works](/files/It-works.png)