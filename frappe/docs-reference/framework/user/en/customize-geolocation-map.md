---
title: "Customize the Geolocation / Map field"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/customize-geolocation-map"
updated: "2026-02-17"
---

If you want to show a map in your DocType Form, you can add a field of type "Geolocation". By default, it looks like this:

![orginal_map](/files/orginal_map.jpg)  


There are many ways to customize this field. We can change global values like the default location and zoom level. And we can customize how individual objects on a particular map are rendered.

Change the map defaults
-----------------------


> Note: these changes require a custom app and will apply to all maps in your system.
> 
> 

By default, it shows a street map centered on Mumbai. This is not configurable via the GUI yet. But, using a custom app, we can change the map type, start location, zoom level, etc.

Start by creating a file `$MY_APP/$MY_APP/public/js/map_defaults.js`. In your `$MY_APP/$MY_APP/hooks.py`, add the JS file into the `app_include_js` hook:


```
app_include_js = [
    "/assets/$MY_APP/js/map_defaults.js"
    # ...
]
```
Now, frappe will load this file for all desk views (i.e. for logged in system users).

In `map_defaults.js`, we add the following lines:


```
// Make sure we have a dictionary to add our custom settings
const map_settings = frappe.provide("frappe.utils.map_defaults");

// Center and zoomlevel can be copied from the URL of
// the map view at openstreetmap.org.

// New default location (middle of germany).
map_settings.center = [51.57, 9.866];
// new zoomlevel: see the whole country, not just a single city
map_settings.zoom = 6;

// Use a different map: satellite instead of streets
// Examples can be found at https://leaflet-extras.github.io/leaflet-providers/preview/
map_settings.tiles = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
map_settings.attribution = "Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community";
```
Restart your bench and reload your browser window. Now you should see the customized map:

![custom_map_defaults](/files/custom_map_defaults.jpeg)  


Change how a particular map is rendered
---------------------------------------

In order to change the look and feel of a particular map, you can overwrite the controller methods of the Geolocation field. This can be done with a **Client Script** or with the hook in a custom app.

By default, everything drawn on the map is blue. Let's overwrite the method `on_each_feature` to make all polygons red:


```
frappe.ui.form.on("My Doctype", {
    setup(frm) {
        frm.fields_dict.MY_MAP_FIELD.on_each_feature = function(feature, layer) {
            if (feature.geometry.type == "Polygon") {
                layer.setStyle({color: "red"});
            }
        };
    }
});
```
The result looks like this:

![red_polygon](/files/red_polygon.png)  


Other methods that can be overwritten include `point_to_layer` and `set_style`. Read more about these methods [in the Leaflet documentation](https://leafletjs.com/examples/geojson/).

