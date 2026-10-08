---
title: "Adding Pages\n"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/guides/portal-development/adding-pages"
updated: "2026-02-17"
---


To add pages, just add `.html` or `.md` files in the `www` folder. The pages must only have the content, not the `` and `` tags.

You can also write markdown pages

### Index

The first file in a folder must be called `index.md` or `index.html`

Either file must be present for the system to make this a valid folder to build pages.

### Markdown

 # This is a title

 This is some page content
 a [link](/link/to/page)

### Adding Links

Links urls to pages can be given without the `.html` extension for example `/home/link`

### Title

The first `` block if present will be the page title if not specified in a special tag. If no `
====================================================================================

` or title is specified, the file name will be the title.

### Adding CSS

You can also add a `.css` file with the same filename (e.g. `index.css` for `index.md`) that will be rendered with the page.

### Special Tags

1. `` will make the page render in Jinja
2. `` will add a custom title
3. `` will not add breadcrumbs in the page
4. `` will enable caching (if you have used Jinja templating)
==========================================================================================================================================================================================================================================================================================================================================================================================================

