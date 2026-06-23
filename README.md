# Agency Registration Automation

Playwright-based script that walks through the multi-step agency signup flow on the Authorized Partner app and creates a test account end to end.

**Target application:** [https://authorized-partner.vercel.app](https://authorized-partner.vercel.app)

---

## Prerequisites

- **Python** 3.10 or newer (tested with Python 3.13)
- **pip** for installing dependencies
- **Network access** to the target app and to receive email OTP codes
- A **Gmail inbox** you can access for the account used in the script (OTP is sent to the login email)
- *(Optional)* A real PDF or image file for business-document upload if the server rejects the built-in placeholder

---

## Environment & setup


| Item               | Version / detail                                                                                             |
| ------------------ | ------------------------------------------------------------------------------------------------------------ |
| Language           | Python 3                                                                                                     |
| Automation library | [Playwright for Python](https://playwright.dev/python) (`playwright>=1.44.0`; local venv may install 1.60.0) |
| Browser driver     | Chromium (bundled with Playwright; e.g. Chromium 148 with Playwright 1.60)                                   |
| API style          | `playwright.async_api` (async/await)                                                                         |
| Default mode       | Headless Chromium (`HEADED = False` in the script)                                                           |


### 1. Clone or download this repo

```bash
cd /path/to/vrit
```

### 2. Create and activate a virtual environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate   
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright browsers

Playwright ships its own browser binaries. Install Chromium once after the pip install:

```bash
playwright install chromium
```

To install all browsers (not required for this script):

```bash
playwright install
```

### 5. Optional configuration

Edit constants at the top of `signup_automation_script.py` before running:


| Constant         | Purpose                                                                                                   |
| ---------------- | --------------------------------------------------------------------------------------------------------- |
| `BASE_URL`       | App URL (default: `https://authorized-partner.vercel.app`)                                                |
| `HEADED`         | Set `True` to show the browser window while the script runs                                               |
| `SLOW_MO`        | Milliseconds to slow each Playwright action (useful for debugging)                                        |
| `GMAIL_BASE`     | Gmail local-part used for plus-addressed login emails                                                     |
| `LOGIN_PASSWORD` | Password used for signup and login                                                                        |
| `DOCUMENT_PATH`  | Path to a real file for the business-document upload step; leave empty to use a generated placeholder PNG |


---

## How to run

With the virtual environment activated and Chromium installed:

```bash
python signup_automation_script.py
```

### What happens during a run

1. Opens Chromium and accepts terms on `/register`.
2. Fills wizard steps: personal details → agency info → experience → business details (including document upload).
3. Pauses at **email verification** and prompts in the terminal for the 6-digit OTP sent to the login email.
4. Submits the final step and prints success credentials, or diagnostics if registration did not complete.

### Debugging

- Set `HEADED = True` to watch the browser.
- Set `SLOW_MO = 500` (or similar) to slow interactions.
- On failure, the script prints validation errors, toasts, and empty fields.

### After a successful signup

Log in at:

**[https://authorized-partner.vercel.app/admin](https://authorized-partner.vercel.app/admin)**

Use the **exact** email and password printed at the end of the run (the email includes a random suffix generated for that run).

---

## Test data & accounts

Each run generates a **unique 6-character suffix** so signups do not collide. Values below describe the pattern; actual emails/names change every run.


| Field             | Value / pattern                                                  |
| ----------------- | ---------------------------------------------------------------- |
| Login email       | `{GMAIL_BASE}+{suffix}@gmail.com` (default base: `kcsupreme945`) |
| Password          | `SecurePass@123` (configurable via `LOGIN_PASSWORD`)             |
| Agency name       | `Test Agency {suffix}`                                           |
| Agency email      | `agency_{suffix}@mailinator.com`                                 |
| Agency website    | `testagency-{suffix}.com`                                        |
| Agency address    | `123 Test Street, Kathmandu, Nepal`                              |
| Business reg. no. | `BRN-{SUFFIX}`                                                   |
| First / last name | `John` / `Doe {suffix}`                                          |
| Phone             | `98` + 8 random digits                                           |
| Certification     | `ICEF Certified Education Agent`                                 |
| Students annually | `50`                                                             |
| Focus area        | `Undergraduate admissions to Canada`                             |
| Success metrics   | `90`                                                             |


### Email OTP

- Verification codes are sent to the **Gmail plus-address** login email (`kcsupreme945+{suffix}@gmail.com` by default).
- You must have access to that Gmail inbox (or change `GMAIL_BASE` to an address you control).
- The script waits for you to type the OTP in the terminal when prompted.

### Document upload

- If `DOCUMENT_PATH` is unset or the file is missing, a minimal placeholder PNG is uploaded from the system temp directory.
- Some server validations may reject the placeholder; use a real PDF or image via `DOCUMENT_PATH` if upload or final submit fails.

### Notes

- Credentials and test identities are **for automation/testing only**.

