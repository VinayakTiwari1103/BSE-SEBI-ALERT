import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import smtplib
from email.message import EmailMessage

# === Load and Validate Environment ===
load_dotenv()

REQUIRED_VARS = ["BSE_USERNAME", "BSE_PASSWORD", "EMAIL", "EMAIL_PASSWORD", "TO_EMAIL"]
for var in REQUIRED_VARS:
    if not os.getenv(var):
        raise ValueError(f"Missing required environment variable: {var}")

USERNAME = os.getenv("BSE_USERNAME")
PASSWORD = os.getenv("BSE_PASSWORD")
EMAIL = os.getenv("EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Handle multiple recipients
TO_EMAILS = [email.strip() for email in os.getenv("TO_EMAIL", "").split(",") if email.strip()]
if not TO_EMAILS:
    raise ValueError("No valid recipient email(s) found in TO_EMAIL.")

WATCHLIST = {
    "Angel One Ltd": "https://www.bseindia.com/stock-share-price/angel-one-ltd/angelone/543235/corp-announcements/",
    "ICICI Securities Ltd": "https://www.bseindia.com/stock-share-price/icici-securities-ltd/icicisec/541179/corp-announcements/"
}

LAST_SENT_FILE = "last_sent_announcements.txt"

# === File Utilities ===
def load_last_sent():
    if not os.path.exists(LAST_SENT_FILE):
        return set()
    with open(LAST_SENT_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_last_sent(new_announcements):
    with open(LAST_SENT_FILE, "a", encoding="utf-8") as f:
        for item in new_announcements:
            f.write(item + "\n")

# === Email Sender ===
def send_email(subject, plain_body, html_body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL
    msg["To"] = ", ".join(TO_EMAILS)
    msg.set_content(plain_body)
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL, EMAIL_PASSWORD)
        smtp.send_message(msg)
    print(f"[✅] Email sent to {len(TO_EMAILS)} recipient(s).")


# === Announcement Scraper ===
def fetch_announcements():
    announcements = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            print("[🔄] Logging in...")
            page.goto("https://www.bsealerts.in/login.php", timeout=60000)
            page.wait_for_selector('input[name="email"]', timeout=10000)
            page.fill('input[name="email"]', USERNAME)
            page.fill('input[name="password"]', PASSWORD)
            page.click('input[name="submit"]')
            page.wait_for_timeout(5000)

            if "login.php" in page.url:
                print("[❌] Login failed!")
                return []

            page.goto("https://www.bsealerts.in/index.php", timeout=60000)
            page.wait_for_timeout(3000)

            for company_name, bse_link in WATCHLIST.items():
                print(f"[🔁] Checking: {company_name}")
                company_link = page.query_selector(f"text={company_name}")
                if not company_link:
                    continue
                company_link.click()
                page.wait_for_timeout(3000)

                links = page.query_selector_all("div:has-text('Announcements') + div a")
                for link in links[:3]:
                    text = link.inner_text().strip()
                    announcements.append({
                        "company": company_name,
                        "text": text,
                        "link": bse_link
                    })

        except Exception as e:
            print(f"[❌] Error: {e}")
            page.screenshot(path="error_screenshot.png")
        finally:
            context.close()
            browser.close()

    return announcements

# === Main ===
if __name__ == "__main__":
    results = fetch_announcements()
    last_sent = load_last_sent()

    new_items = []
    sent_ids = []

    for ann in results:
        unique_id = f"{ann['company']}::{ann['text']}"
        if unique_id not in last_sent:
            new_items.append(ann)
            sent_ids.append(unique_id)

    if new_items:
        plain_body = ""
        html_body = ""
        for ann in new_items:
            plain_body += f"{ann['company']}\n{ann['text']}\n{ann['link']}\n\n"
            html_body += f"<p><b>{ann['company']}</b><br>{ann['text']}<br><a href='{ann['link']}'>🔗 Read on BSE</a></p>"

        send_email("📢 New BSE Alerts", plain_body, html_body)
        save_last_sent(sent_ids)
    else:
        print("[ℹ️] No new announcements since last check.")
