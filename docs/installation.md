# Installation

Installation means preparing your computer so the application can run.

## Step 1: Open a Terminal

A terminal is a text window where you type commands.

On macOS:

1. Open Spotlight.
2. Type `Terminal`.
3. Press Enter.

On Windows:

1. Open the Start menu.
2. Type `PowerShell`.
3. Open Windows PowerShell.

## Step 2: Go to the Project Folder

Use `cd`, which means "change directory".

```bash
cd /Users/blainetelahun/Critical_Infrastructure
```

What this does: moves your terminal into the project folder.

Expected output: no output is normal.

Check you are in the right place:

```bash
pwd
```

Expected output:

```text
/Users/blainetelahun/Critical_Infrastructure
```

On Windows, `pwd` may print a Windows-style path instead.

## Step 3: Create a Virtual Environment

```bash
python -m venv venv
```

What this does: creates a private Python library folder named `venv`.

Why it matters: it keeps this project's libraries separate from other projects.

Expected output: usually nothing.

Common error:

```text
python: command not found
```

Fix: install Python 3.10 or newer, then try again.

## Step 4: Activate the Virtual Environment

On macOS or Linux:

```bash
source venv/bin/activate
```

On Windows PowerShell:

```powershell
venv\Scripts\Activate.ps1
```

Expected output: your prompt may begin with `(venv)`.

Common Windows error:

```text
running scripts is disabled on this system
```

Fix: ask your administrator to allow local PowerShell scripts, or use Command Prompt with:

```cmd
venv\Scripts\activate.bat
```

## Step 5: Install Libraries

```bash
pip install -r requirements.txt
```

What this does: reads `requirements.txt` and downloads the libraries the app imports.

Expected output: many download lines and a success message.

Common error:

```text
Could not find a version that satisfies the requirement
```

Possible causes:

- Python is too old.
- Internet access is blocked.
- The package service is temporarily unavailable.

Verification:

```bash
python -c "import streamlit, openai, pinecone; print('Libraries installed')"
```

Expected output:

```text
Libraries installed
```

## Step 6: Continue to Configuration

After installation, follow [Configuration](configuration.md).
