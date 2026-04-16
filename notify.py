import os
from twilio.rest import Client

def send_alert(text):
    client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    from_number = os.environ["TWILIO_FROM"]
    recipients = [r.strip() for r in os.environ["RECIPIENTS"].split(",")]

    for number in recipients:
        client.messages.create(body=text, from_=from_number, to=number)
        print(f"Sent to {number}")
