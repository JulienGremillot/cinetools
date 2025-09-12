import requests
import os
from dotenv import load_dotenv

load_dotenv()
APP_ID = os.getenv("META_APP_ID")
APP_SECRET = os.getenv("META_APP_SECRET")
USER_TOKEN = os.getenv("META_USER_ACCESS_TOKEN")

url = "https://graph.facebook.com/v17.0/oauth/access_token"

params = {
    "grant_type": "fb_exchange_token",
    "client_id": APP_ID,
    "client_secret": APP_SECRET,
    "fb_exchange_token": USER_TOKEN
}

response = requests.get(url, params=params)

if response.ok:
    data = response.json()
    print("✅ Long-lived token :", data["access_token"])
    print("⏳ Expire dans :", data["expires_in"], "secondes (~60 jours)")
else:
    print("❌ Erreur :", response.text)
