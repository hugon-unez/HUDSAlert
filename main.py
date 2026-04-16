import os
import re
import ssl
import smtplib
import traceback
import requests
from bs4 import BeautifulSoup
from google import genai
from datetime import datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

LOCATION_NUM = 30
MENU_URL = "https://www.foodpro.huds.harvard.edu/foodpro/shtmenu.aspx"

def build_url():
    now_et = datetime.now(ZoneInfo("America/New_York"))
    dtdate = f"{now_et.month}/{now_et.day}/{now_et.year}"
    params = (
        f"sName=HARVARD+UNIVERSITY+DINING+SERVICES"
        f"&locationNum={LOCATION_NUM}"
        f"&locationName=Dining+Hall"
        f"&naFlag=1"
        f"&dtdate={requests.utils.quote(dtdate)}"
    )
    return f"{MENU_URL}?{params}"

def fetch_menu():
    url = build_url()
    print(f"Fetching: {url}")
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.text

def parse_menu(html):
    soup = BeautifulSoup(html, "html.parser")
    body_text = soup.get_text(separator="\n")

    menu_data = {"date": None, "lunch_entrees": [], "dinner_entrees": []}

    # Search for a weekday date pattern directly — more reliable than parsing after "for"
    date_match = re.search(
        r"((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), \w+ \d+, \d{4})",
        body_text
    )
    if date_match:
        menu_data["date"] = date_match.group(1).strip()
        print(f"Menu date: {menu_data['date']}")

        now_et = datetime.now(ZoneInfo("America/New_York"))
        today_et = f"{now_et.strftime('%A, %B')} {now_et.day}, {now_et.year}"
        if menu_data["date"] != today_et:
            print(f"WARNING: page date '{menu_data['date']}' does not match today ({today_et} ET)")

    lines = body_text.split("\n")
    current_meal = None
    current_section = None
    entree_count = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("--") and line.endswith("--"):
            section = line.strip("- ").lower()
            # Count non-breakfast, non-grill entree sections.
            # First occurrence = lunch (or brunch), second = dinner.
            if section in ("entrees", "brunch"):
                entree_count += 1
                current_meal = "lunch" if entree_count == 1 else "dinner"
            current_section = section
            continue

        if current_meal in ("lunch", "dinner") and current_section in ("entrees", "brunch"):
            if len(line) > 2:
                entrees = menu_data["lunch_entrees"] if current_meal == "lunch" else menu_data["dinner_entrees"]
                if line not in entrees:
                    entrees.append(line)

    print(f"Found {len(menu_data['lunch_entrees'])} lunch entrees")
    print(f"Found {len(menu_data['dinner_entrees'])} dinner entrees")
    return menu_data

def format_menu(menu_data):
    now_et = datetime.now(ZoneInfo("America/New_York"))
    is_before_noon = now_et.hour < 12

    meal = "Lunch" if is_before_noon else "Dinner"
    entrees = menu_data["lunch_entrees"] if is_before_noon else menu_data["dinner_entrees"]
    date_str = menu_data.get("date") or "Unknown date"
    entree_list = ", ".join(entrees) if entrees else "No entrees found"

    return meal, date_str, entree_list

def make_funny(meal, date_str, entree_list):
    prompt = (
        f"You're a Harvard student texting your friends about {meal} on {date_str}. "
        f"Entrees: {entree_list}\n\n"
        f"Rules:\n"
        f"- Max 1-2 sentences, super casual\n"
        f"- Use Gen Z slang/Twitter language (#expand for good meals, #shrink for mid ones)\n"
        f"- Students hate: daily catch/fish (roast it), basic grilled chicken (boring)\n"
        f"- Students generally do not like: things that feel random and excessive (why give me jerk chicken, or rosemary chicken)\n"
        f"- Students love: quesadillas, anything fried, chicken that's not plain\n"
        f"- Be sarcastic about bad options, hype good ones\n"
        f"- Examples of vibe: 'daily catch today lmaooo just put the fries in the bag' "
        f"or 'shrimp quesadilla #expand we eating good tonight'\n\n"
        f"Write the text:"
    )

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=genai.types.GenerateContentConfig(max_output_tokens=1000, temperature=1.2),
    )
    return response.text.strip()

def send_alert(text):
    sender = os.environ["GMAIL_USER"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]
    recipients = [r.strip() for r in os.environ["RECIPIENTS"].split(",")]

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = ""
    msg.set_content(text)

    context = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls(context=context)
        smtp.login(sender, app_password)
        smtp.send_message(msg)

    print(f"Alert sent to: {', '.join(recipients)}")

def main():
    try:
        html = fetch_menu()
        menu_data = parse_menu(html)
        meal, date_str, entree_list = format_menu(menu_data)
        text = make_funny(meal, date_str, entree_list)
        print("\n" + text)
        send_alert(text)

    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
