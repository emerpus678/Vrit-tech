import asyncio
import base64
import os
import random
import string
import tempfile
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright

_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

#confriguration
BASE_URL   = "https://authorized-partner.vercel.app"
HEADED     = False   
SLOW_MO    = 0       

suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
#email and password
GMAIL_BASE     = "kcsupreme945"
LOGIN_EMAIL    = f"{GMAIL_BASE}+{suffix}@gmail.com"
LOGIN_PASSWORD = "SecurePass@123"


DOCUMENT_PATH  = ""

DATA = {
    "agency_name":      f"Test Agency {suffix}",
    "role_in_agency":   "Director",
    "agency_email":     f"agency_{suffix}@mailinator.com",
    "agency_website":   f"testagency-{suffix}.com",
    "agency_address":   "123 Test Street, Kathmandu, Nepal",
    "business_reg_no":  f"BRN-{suffix.upper()}",
    "certification":    "ICEF Certified Education Agent",
    "students_annually":"50",
    "focus_area":       "Undergraduate admissions to Canada",
    "success_metrics":  "90",
    "first_name":       "John",
    "last_name":        f"Doe {suffix}",
    "email":            LOGIN_EMAIL,
    "phone":            "98" + "".join(random.choices(string.digits, k=8)),
    "password":         LOGIN_PASSWORD,
}

#helpers
async def fill_placeholder(page, placeholder, value, timeout=8000):
    """Fill an input matched by placeholder text.

    Waits for the field to be visible and verifies the value stuck, re-filling
    once if an async form reset (e.g. server data load) clears it.
    """
    loc = page.get_by_placeholder(placeholder, exact=False).first
    try:
        await loc.wait_for(state="visible", timeout=timeout)
    except Exception:
        return False
    # Number inputs reject non-numeric text; keep only digits for them.
    input_type = (await loc.get_attribute("type")) or "text"
    if input_type == "number":
        digits = "".join(ch for ch in value if ch.isdigit())
        value = digits or "0"
    await loc.fill(value)
    if (await loc.input_value()) != value:
        await page.wait_for_timeout(600)
        await loc.fill(value)
    return True

async def wait_for_field(page, placeholder, timeout=10000):
    """Wait for a form field to mount, then let async resets settle."""
    try:
        await page.get_by_placeholder(placeholder, exact=False).first.wait_for(
            state="visible", timeout=timeout
        )
        await page.wait_for_timeout(800)
        return True
    except Exception:
        return False

async def choose_from_dropdown(page, placeholder, search=None):
    """Select an option from either a Radix Select or the custom MultiSelect.
    """
    triggers = page.get_by_role("combobox")
    trigger = None
    for i in range(await triggers.count()):
        cand = triggers.nth(i)
        if not await cand.is_visible():
            continue
        text = (await cand.inner_text()) or ""
        if placeholder.lower() in text.lower():
            trigger = cand
            break
    if trigger is None:
        return False

    placeholder_text = (await trigger.inner_text() or "").strip()

    await trigger.scroll_into_view_if_needed()
    await trigger.click()
    await page.wait_for_timeout(500)

    # Radix Select: options carry role="option".
    options = page.get_by_role("option")
    if await options.count():
        target = None
        if search:
            filtered = options.filter(has_text=search)
            if await filtered.count():
                target = filtered.first
        target = target or options.first
        await target.click()
        return True


#selection made
    async def selection_made():
        #selection made
        current = (await trigger.inner_text() or "").strip()
        return current and current != placeholder_text

    for attempt in range(2):
        searchbox = page.get_by_placeholder("Search...")
        if not await searchbox.count():
            # Popover didn't open; click the trigger again.
            await trigger.click()
            await page.wait_for_timeout(500)
            searchbox = page.get_by_placeholder("Search...")
        if search and await searchbox.count():
            await searchbox.first.fill(search)
            await page.wait_for_timeout(300)

        popover = page.locator("[class*='popover']").last
        opt = popover.locator("div.cursor-pointer")
        try:
            await opt.first.wait_for(state="visible", timeout=3000)
            await opt.first.click()
        except Exception:
            # Fallback: click the first option row via JS (fires React onClick).
            await page.evaluate(
                """() => {
                    const pops = [...document.querySelectorAll("[class*='popover']")];
                    const pop = pops[pops.length - 1];
                    if (!pop) return false;
                    const rows = [...pop.querySelectorAll('div')].filter(
                        d => /cursor-pointer/.test(d.className) && d.querySelector('span')
                    );
                    if (!rows.length) return false;
                    rows[0].click();
                    return true;
                }"""
            )
        await page.wait_for_timeout(300)
        if await selection_made():
            await page.keyboard.press("Escape")
            return True
        # Reopen for a second try.
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)
        await trigger.click()
        await page.wait_for_timeout(500)

    await page.keyboard.press("Escape")
    return await selection_made()

async def check_first_in_group(page, group_label):
    """Tick the first checkbox that appears after the given group label.

    Options render as `role="checkbox"` buttons in a sibling container, so we
    anchor on the label and walk the DOM forward to the first checkbox.
    """
    label = page.get_by_text(group_label, exact=True).first
    if await label.count():
        following = label.locator(
            'xpath=following::*[@role="checkbox" or '
            '(self::input and @type="checkbox")][1]'
        )
        if await following.count():
            try:
                await following.first.click()
                return True
            except Exception:
                pass
        
    # Fallback: first checkbox anywhere on the current step.
    cb = page.locator("[role='checkbox'], input[type='checkbox']").first
    if await cb.count():
        try:
            await cb.click()
            return True
        except Exception:
            return False
    return False

async def upload_document(page):
    """Upload a file into the first dropzone (business step requires >=1 document).

    Uses DOCUMENT_PATH if it points to a real file; otherwise falls back to a
    generated placeholder PNG. A real PDF/image is recommended, since the server
    may reject a trivial placeholder during the final submit.
    """
    file_input = page.locator("input[type='file']").first
    if not await file_input.count():
        return False
    if DOCUMENT_PATH and os.path.exists(DOCUMENT_PATH):
        doc_path = DOCUMENT_PATH
    else:
        doc_path = os.path.join(tempfile.gettempdir(), "vrit_business_document.png")
        if not os.path.exists(doc_path):
            with open(doc_path, "wb") as fh:
                fh.write(_PNG_1X1)
    await file_input.set_input_files(doc_path)
    await page.wait_for_timeout(1000)
    return True

async def click_next(page):
    """Click the primary Next/Continue/Submit button on the current form."""
    for label in ("Next", "Continue", "Submit", "Create Account", "Register"):
        btn = page.get_by_role("button", name=label, exact=False)
        for i in range(await btn.count()):
            candidate = btn.nth(i)
            if await candidate.is_visible() and await candidate.is_enabled():
                await candidate.click()
                return
    submit = page.locator("button[type='submit']").first
    if await submit.count():
        await submit.click()

async def visible_heading(page, name):
    heading = page.get_by_role("heading", name=name, exact=False)
    return await heading.count() > 0 and await heading.first.is_visible()

async def detect_step(page):
    """Detect wizard step from page content (URL stays /register throughout)."""
    if await visible_heading(page, "Register Your Agency"):
        if await page.get_by_role("checkbox").count():
            return "terms"

    # Email OTP screen (shown inline during the personal-details/setup step).
    otp = page.get_by_text("verification code", exact=False)
    if await otp.count() and await otp.first.is_visible():
        return "email_otp"

    if await visible_heading(page, "Provide Business Details and Set Preferences"):
        return "business"
    if await visible_heading(page, "About your Agency"):
        return "agency"
    if await visible_heading(page, "Experience and Performance Metrics"):
        return "experience"
    if await visible_heading(page, "Provide your personal details"):
        return "profile"


    # NOT the email OTP step.
    step_param = parse_qs(urlparse(page.url).query).get("step", [""])[0]
    return {
        "setup":                     "profile",
        "details":                   "agency",
        "professional-experience":   "experience",
        "verification":              "business",
    }.get(step_param, "unknown")

async def all_toasts(page):
    """Return all visible toast/notification messages (success or error)."""
    texts = await page.locator("ol li, [role='status']").all_text_contents()
    return [t.strip() for t in texts if t.strip()]

async def dump_diagnostics(page):
    """Print validation errors, toasts, and empty fields to explain a stuck step."""
    errors = [
        e.strip()
        for e in await page.locator("[class*='destructive']").all_text_contents()
        if e.strip() and e.strip().lower() != "validating..."
    ]
    print("  Validation errors:", errors or "none")
    print("  Toasts/messages:", await all_toasts(page) or "none")
    print("  Current URL:", page.url)
    empty = await page.locator("input").evaluate_all(
        "els => els.filter(e => e.offsetParent && !e.value)"
        ".map(e => e.placeholder || e.name || e.type)"
    )
    print("  Empty visible inputs:", empty or "none")

async def wait_for_step_change(page, previous, timeout_ms=12000):
    """Poll until the detected step differs from `previous` (async submits)."""
    elapsed = 0
    interval = 500
    while elapsed < timeout_ms:
        current = await detect_step(page)
        if current != previous:
            return current
        await page.wait_for_timeout(interval)
        elapsed += interval
    return await detect_step(page)

#steps
async def step_terms(page):
    print("Step: Terms & Conditions")
    await page.goto(f"{BASE_URL}/register", wait_until="domcontentloaded")
    await page.get_by_role("heading", name="Register Your Agency").wait_for()
    await page.get_by_role("checkbox").check()
    # Wizard uses ?step= query param; explicit navigation is more reliable than continue
    await page.goto(f"{BASE_URL}/register?step=setup", wait_until="domcontentloaded")
    await page.wait_for_load_state("networkidle")

async def step_business(page):
    print("Step:  Business Details")
    await wait_for_field(page, "Enter your registration number")
    await fill_placeholder(page, "Enter your registration number", DATA["business_reg_no"])
    await choose_from_dropdown(page, "Select Your Preferred Countries")
    await check_first_in_group(page, "Preferred Institution Types")
    await fill_placeholder(page, "ICEF Certified", DATA["certification"])
    await upload_document(page)  # required: "At least one document must be uploaded"
    await click_next(page)
    await page.wait_for_load_state("networkidle")

async def step_agency(page):
    print("Step: About Your Agency")
    await wait_for_field(page, "Enter Agency Name")
    await fill_placeholder(page, "Enter Agency Name", DATA["agency_name"])
    await fill_placeholder(page, "Enter Your Role in Agency", DATA["role_in_agency"])
    await fill_placeholder(page, "Enter Your Agency Email Address", DATA["agency_email"])
    await fill_placeholder(page, "Enter Your Agency Website", DATA["agency_website"])
    await fill_placeholder(page, "Enter Your Agency Address", DATA["agency_address"])
    await choose_from_dropdown(page, "Select Your Region of Operation")
    await click_next(page)
    await page.wait_for_load_state("networkidle")

async def step_experience(page):
    print("Step: Professional Experience")
    await wait_for_field(page, "Enter an approximate number")
    await choose_from_dropdown(page, "Select Your Experience Level")
    await fill_placeholder(page, "Enter an approximate number", DATA["students_annually"])
    await fill_placeholder(page, "Undergraduate admissions", DATA["focus_area"])
    await fill_placeholder(page, "90%", DATA["success_metrics"])
    await check_first_in_group(page, "Services Provided")
    await click_next(page)
    await page.wait_for_load_state("networkidle")

async def step_profile(page):
    print("Step: Personal Details & Password")
    await fill_placeholder(page, "Enter Your First Name", DATA["first_name"])
    await fill_placeholder(page, "Enter Your Last Name", DATA["last_name"])
    await fill_placeholder(page, "Enter Your Email Address", DATA["email"])
    await fill_placeholder(page, "00-00000000", DATA["phone"])
    pw_fields = page.locator("input[type='password']")
    count = await pw_fields.count()
    if count >= 1:
        await pw_fields.nth(0).fill(DATA["password"])
    if count >= 2:
        await pw_fields.nth(1).fill(DATA["password"])
    await click_next(page)
    await page.wait_for_load_state("networkidle")

async def step_verification(page):
    print("Step: Email Verification")
    print(f"  A 6-digit code was emailed to: {DATA['email']}")
    code = (await asyncio.to_thread(input, "  Enter the OTP code: ")).strip()

    otp = page.locator("input").first
    await otp.click()
    try:
        await otp.fill(code)
    except Exception:
        pass
    if (await otp.input_value()) != code:
        await page.keyboard.type(code)

    verify = page.get_by_role("button", name="Verify Code", exact=False)
    if await verify.count():
        await verify.first.click()
    else:
        await page.keyboard.press("Enter")
    await page.wait_for_load_state("networkidle")

STEP_HANDLERS = {
    "terms":        step_terms,
    "business":     step_business,
    "agency":       step_agency,
    "experience":   step_experience,
    "profile":      step_profile,
    "email_otp":    step_verification,
}

async def registration_succeeded(page):
    """True only on a genuine completion signal.

    The app redirects to /admin?redirected=true when registration is NOT
    finished, so a bare /admin URL must NOT be treated as success.
    """
    url = page.url.replace(BASE_URL, "").lower()
    if "redirected=true" in url:
        return False
    toast = page.get_by_text("Registration completed", exact=False)
    if await toast.count():
        return True
    return any(k in url for k in ("success", "thank-you", "thankyou"))

async def wait_for_registration_result(page, timeout_ms=15000):
    """After submitting Business Details, wait for success or an error toast."""
    elapsed, interval = 0, 500
    while elapsed < timeout_ms:
        if await registration_succeeded(page):
            return "success"
        if "redirected=true" in page.url:
            return "incomplete"
        errs = [
            e.strip()
            for e in await page.locator("[class*='destructive']").all_text_contents()
            if e.strip() and e.strip().lower() not in ("validating...", "")
        ]
        if errs:
            return "error"
        await page.wait_for_timeout(interval)
        elapsed += interval
    return "timeout"

def print_success(page_url):
    print(f"Signup complete! → {page_url}")
    print("  Log in at: " + f"{BASE_URL}/admin")
    print(f"  Email:    {DATA['email']}")
    print(f"  Password: {DATA['password']}")
    print("  NOTE: Log in with the exact email above.")


#main function
async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not HEADED, slow_mo=SLOW_MO)
        page    = await browser.new_page(viewport={"width": 1280, "height": 900})

        await step_terms(page)

        seen = set()
        for _ in range(15):
            url  = page.url.replace(BASE_URL, "").lower()
            step = await detect_step(page)

            if await registration_succeeded(page):
                print_success(page.url)
                break

            if step == "terms":
                await step_terms(page)
                continue

            if step == "unknown":
                print(f"Unknown step (url={url}) – trying to advance…")
                await click_next(page)
                await page.wait_for_load_state("networkidle")
                continue

            if step in seen:
                print(f"Stuck on '{step}' – no progress, stopping.")
                await dump_diagnostics(page)
                break
            seen.add(step)

            handler = STEP_HANDLERS.get(step)
            if handler:
                await handler(page)

                # The business step is the final submit and verify it truly worked.
                if step == "business":
                    result = await wait_for_registration_result(page)
                    if result == "success":
                        print_success(page.url)
                    else:
                        print(f"Registration did NOT complete (result: {result}).")
                        print("  The account will be inactive until registration finishes.")
                        await dump_diagnostics(page)
                    break

                # Other steps submit asynchronously; wait for the wizard to advance.
                await wait_for_step_change(page, step)
                if await registration_succeeded(page):
                    print_success(page.url)
                    break

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
