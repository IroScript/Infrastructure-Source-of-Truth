---
title: "Security FAQs"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/security-faqs"
updated: "2026-04-23"
---

This page contains some frequently asked questions related to security. Please review this before raising security issue with Frappe team.





### Frappe allows uploading malicious files like .EXE

Frappe is not an anti-virus, so it doesn't scan any kind of files that get uploaded. Frappe has inbuilt validation to block certain extensions and you can tweak this from "System Setting" > Files > Allowed File Extensions.

### Frappe shows complete traceback of error

Error traces help developers debug issues faster. In vast majority of the cases they do not reveal anything that isn't already available in our source code which is open source. If you still wish to disable tracebacks then go to "System Settings" and uncheck "Show Full Error and Allow Reporting of Issues to the Developer"

### Frappe doesn't encrypt the password when sending a request

Frappe recommends proper HTTPS (TLS) setup in production, if that is setup properly every request is encrypted at transport layer, so there is little security benefit from encrypted request content manually again on top of it.

If you're using a tool like Burp Suite to intercept an encrypted request by setting up a proxy/certificate that allows you to see unencrypted traffic then you're not really operating in real threat model. In real world, if TLS is compromised, you have much bigger problems.

In addition to this Frappe stores login password with PBKDF2 + SHA256 hash. Once stored, it's not possible to retrieve the passwords. Password fields that need value to be retrievable (e.g. API secrets) are stored with symmetric encryption using Fernet.

### Frappe enables "autocomplete" on password fields

Autocomplete + password managers are widely considered as better option for security and UX. Disabling autocomplete is outdated practice and major browsers don't even respect it if you disable it. Refer: <[https://developer.mozilla.org/en-US/docs/Web/Security/Securing_your_site/Turning_off_form_autocompletion#the_autocomplete_attribute_and_login_fields](https://developer.mozilla.org/en-US/docs/Web/Security/Securing_your_site/Turning_off_form_autocompletion#the_autocomplete_attribute_and_login_fields)>

### Frappe doesn't expire passwords every 30/90 days

Password rotation isn't necessarily secure and can even cause harmful side effects: <[https://www.sans.org/blog/time-for-password-expiration-to-die/](https://www.sans.org/blog/time-for-password-expiration-to-die/)>

If you still want this behaviour you can enable it from "System Settings" > "Force User to Reset Password"

### Frappe doesn't allow configuring password requirements to include upper, lowercase and special characters

Hard-coded requirements for passwords are generally bad UX. Password strength is largely based on entropy, see this comic for a good illustration of this: <[https://xkcd.com/936/](https://xkcd.com/936/)>

Frappe instead runs heuristics to compute password strength. By default we require a reasonably strong password, but if you want to increase this strength then you can configure it in "System Settings" > "Password" > " Minimum Password Score"

### Frappe sets cookie path to `/` which can allow other applications on same origin to use the cookie

Frappe doesn't allow configuring different applications on different paths. So this can't happen. By default, all pages on your configured domain/subdomain are served by Frappe.

### Frappe doesn't add "Secure" flag to cookies

Frappe adds a "Secure" flag to cookies only when it's accessed from the HTTPS scheme.

We recommend enabling HSTS on your domain so unencrypted traffic is blocked. <[https://en.wikipedia.org/wiki/HTTP_Strict_Transport_Security](https://en.wikipedia.org/wiki/HTTP_Strict_Transport_Security)>

We allow non-HTTPS connections to support deployments in internal networks where users might not want to setup TLS.

### The site reveals that it's running on Frappe

It is trivial to figure out which application a site is running if you know application characteristics. E.g. preload headers, asset file names, and API paths. It's impossible to mask all of this information.

Even if we hide branding from UI, it won't take much time to figure out that a particular site is running on Frappe.

### Frappe allows adding links to external websites in comments

In a collaborative environment like Frappe, linking to external tools and resources is often a necessary part of the workflow, so disabling them completely isn't practical. To address the potential phishing risks, it is possible to display a warning modal before a user leaves the Desk. This feature can be enabled from "System Settings" > "Show External Link Warning".



### XSS in Print Formats or Developer Fields

Fields such as Print Formats, Custom Scripts, and other developer-focused HTML fields are intentionally designed to allow raw HTML/JavaScript for customization. These are only accessible to trusted users (e.g. System Managers/Developers), so rendering scripts in these contexts is expected behavior and not considered an XSS vulnerability. Reports of script execution in such fields are therefore invalid unless untrusted or low-privilege users can exploit them.

