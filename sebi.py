from playwright.sync_api import sync_playwright
import smtplib
from email.message import EmailMessage
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

EMAIL = os.getenv("EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TO_EMAILS = [email.strip() for email in os.getenv("TO_EMAIL", "").split(",") if email.strip()]
LAST_FILE = "last_seen_sebi.txt"

# === File Handling ===
def load_last():
    if not os.path.exists(LAST_FILE):
        return set()
    with open(LAST_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def save_last(items):
    with open(LAST_FILE, "a", encoding="utf-8") as f:
        for item in items:
            f.write(item + "\n")

# === Email Sending ===
def send_email(subject, items):
    if not TO_EMAILS:
        raise ValueError("No valid recipient email(s) found in TO_EMAIL.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL
    msg["To"] = ", ".join(TO_EMAILS)

    plain_body = "\n\n".join(f"{date} - {title}\n{link}" for date, title, link in items)
    msg.set_content(plain_body)

    html_body = "<h2>📢 New SEBI Circulars</h2><ul>"
    for date, title, link in items:
        html_body += f"<li><b>{date}</b>: <a href='{link}'>{title}</a></li>"
    html_body += "</ul>"
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL, EMAIL_PASSWORD)
        smtp.send_message(msg)

    print(f"[✅] Email sent to {len(TO_EMAILS)} recipient(s).")

# === Web Scraper ===
def fetch_sebi_circulars():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=7&smid=0", timeout=60000)
        page.wait_for_timeout(3000)

        rows = page.query_selector_all("table tr")[1:4]  # Top 3 circulars
        circulars = []

        for row in rows:
            cols = row.query_selector_all("td")
            if len(cols) >= 2:
                date = cols[0].inner_text().strip()
                link_elem = cols[1].query_selector("a")
                if link_elem:
                    title = link_elem.inner_text().strip()
                    href = link_elem.get_attribute("href")
                    full_link = "https://www.sebi.gov.in" + href if href.startswith("/") else href
                    circulars.append((date, title, full_link))

        browser.close()
        return circulars

# === Main Execution ===
if __name__ == "__main__":
    seen = load_last()
    current = fetch_sebi_circulars()

    new_items = []
    for date, title, link in current:
        id_str = f"{date}::{title}"
        if id_str not in seen:
            new_items.append((date, title, link))

    if new_items:
        send_email("📢 New SEBI Circulars", new_items)
        save_last([f"{d}::{t}" for d, t, _ in new_items])
    else:
        print("[ℹ️] No new circulars.")
