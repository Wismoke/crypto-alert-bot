import requests

# FAUSSES VALEURS — tu remplaceras par les vraies plus tard
BOT_TOKEN = "8487710475:AAHuWXy8Y2f94juk9Z0Gh-TtE91DnyjVfC4"
CHAT_ID   = "1011365025"

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=15)
    print(r.status_code, r.text)

if __name__ == "__main__":
    send_telegram("Hello Selim 👋 — déploiement Railway via GitHub OK ✅")
