---
title: "Installation"
space: "Framework"
url: "https://docs.frappe.io/framework/user/en/installation"
updated: "2026-08-24"
---

## System Requirements

This guide assumes you are using a personal computer, VPS or a bare-metal server. You also need to be on a \*nix system, so any Linux Distribution and macOS is supported. If you're a Windows user, you could use Ubuntu in WSL. We officially support only the following distributions.

1. macOS
2. Debian / Ubuntu

> Learn more about the architecture here. 

## Pre-requisites


| Dependency     | Frappe v14/v15 | Frappe v16/develop |
| -------------- | -------------- | ------------------ |
| MariaDB        | 10.6.6+        | 11.8               |
| Python         | 3.10+          | 3.14               |
| NodeJS         | 18+            | 24                 |
| Redis / valkey | 6              | 6+                 |
| Yarn           | 1.12+          | 1.22+              |
| pip            | 20+            | 25.3+              |


- wkhtmltopdf: version 0.12.6 with patched qt - for pdf generation
- cron: bench's scheduled jobs - automated certificate renewal, scheduled backups

### macOS

Install command line version of Xcode tools.

```
xcode-select --install
```

Install Homebrew. It makes it easy to install packages on macOS.

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

(It may prompt you to run some additional commands at the end, which will ensure `brew` is available in your PATH)

Install wkhtmltopdf

```
curl -L https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-2/wkhtmltox-0.12.6-2.macos-cocoa.pkg -O

installer -pkg wkhtmltox-0.12.6-2.macos-cocoa.pkg -target ~
```

Now, you can easily install the required packages by running the following command

```
brew install git redis mariadb@11.8 pkg-config mariadb-connector-c
```

If you plan to use PostgreSQL instead of MariaDB, then you can include `postgresql`

During this installation you'll be prompted to set the MySQL root password. If you are not prompted, you'll have to initialize the MySQL server setup yourself. You can do that by running the command:

```
sudo mariadb-secure-installation
```

> Remember: only run it if you're not prompted the password during setup.
>
>

Then, move on to the common steps

### Debian / Ubuntu

You should be running Debian 13+ or Ubuntu 24.04+, otherwise you may have issues with some of the packages.

Update your system's package index

```
sudo apt update
```

Install `git`, `redis`, and `mariadb`

```
sudo apt install git redis-server libmariadb-dev mariadb-server mariadb-client pkg-config
```

During this installation you'll be prompted to set the MySQL root password. If you are not prompted, you'll have to initialize the MySQL server setup yourself. You can do that by running the command:

```
sudo mariadb-secure-installation
```

> Remember: only run it if you're not prompted the password during setup.
>
>

It is really important that you remember this password, since it'll be useful later on.

**Install wkhtmltopdf**

```
sudo apt install xvfb libfontconfig
```

Download and install wkhtmltopdf package from [https://wkhtmltopdf.org/downloads.html](https://wkhtmltopdf.org/downloads.html), then run this command to install the package.

```
sudo dpkg -i wkhtmltox_file.deb
```

### Common dependencies

**Install nvm, node, and yarn**

We recommend installing node using nvm

```
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
```

After nvm is installed, you may have to close your terminal and open another tab/window, or `source` your shell's rc file (example: `~/.bashrc` or `~/.zshrc`. Then run the following command to install node.

```
nvm install 24
```

Verify the installed version, by running:

```
$ node -v
v24.12.0
```

Finally, install `yarn` using `npm`

```
npm install -g yarn
```

\*\* Install uv and python \*\*

We recommend using python using uv

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After uv is installed, you may have to close your terminal and open another tab/window, or `source` your shell's rc file (example: `~/.bashrc` or `~/.zshrc`. Then run the following command to install python.

```
uv python install 3.14 --default
```

Alternatively, you can choose between 3.10-3.13 for version 15.

## Install Bench CLI

Install bench via pip

```
uv tool install frappe-bench
```

Confirm the bench installation by checking the version

```
bench --version
```

Create your first bench.

```
mkdir ~/frappe
cd ~/frappe
bench init my-bench
```

Congratulations, you have installed bench onto your system.