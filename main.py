# main.py — Bot Telegram + Alertes CMC (Top 200, +4%/1m pump, -5%/5m dump, /status)
import os
import time
import requests
from datetime import datetime, timezone

# Secrets lus depuis Railway (Variables)
CMC_API_KEY = os.getenv("CMC_API_KEY")
BOT_TOKEN   = os.getenv("BOT_TOKEN")
CHAT_ID     = os.getenv("CHAT_ID")

if not CMC_API_KEY or not BOT_TOKEN or not CHAT_ID:
    raise SystemExit("❌ Variables manquantes. Défini CMC_API_KEY, BOT_TOKEN, CHAT_ID dans Railway → Variables.")

VS_CURRENCY = "USD"
TOP_N       = 200
POLL_SECS   = 10
HISTORY_MIN = 20
COOLDOWN_MIN = 10

THRESH = {
    60:  {"up": 4.0, "down": None},   # +4% en 1m = PUMP
    300: {"up": None, "down": -5.0},  # -5% en 5m = DUMP
    900: {"up": None, "down": None},  # off
}

CMC_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"

def send_telegram(text: str, chat_id: str = None):
    chat_id = chat_id or CHAT_ID
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": chat_id, "text": text},
            timeout=10
        )
        if r.status_code != 200:
            print("Telegram err:", r.status_code, r.text[:200])
    except Exception as e:
        print("Telegram exception:", e)

_updates_offset = None
def poll_commands_and_reply():
    """Répond à /status (non bloquant)."""
    global _updates_offset
    try:
        params = {"timeout": 0}
        if _updates_offset is not None:
            params["offset"] = _updates_offset
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", params=params, timeout=10)
        if r.status_code != 200:
            return
        data = r.json()
        for upd in data.get("result", []):
            _updates_offset = upd["update_id"] + 1
            msg = upd.get("message")
            if not msg:
                continue
            text = (msg.get("text") or "").strip().lower()
            chat_id = str(msg["chat"]["id"])
            if text in ("/status", "status"):
                send_telegram("Bot actif ✅ (Top 200, +4%/1m, −5%/5m)", chat_id)
    except Exception:
        pass

def fetch_top_prices():
    headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY, "Accept": "application/json"}
    params = {"start": 1, "limit": TOP_N, "convert": VS_CURRENCY,
              "sort": "market_cap", "sort_dir": "desc"}
    r = requests.get(CMC_URL, headers=headers, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()["data"]
    out = {}
    for d in data:
        sym = d["symbol"].upper()
        price = d["quote"][VS_CURRENCY]["price"]
        out[sym] = float(price)
    return out

def pct_change(p_now, p_then):
    if p_then <= 0:
        return None
    return (p_now / p_then - 1.0) * 100.0

def main():
    history = {}
    last_alert = {}

    send_telegram("✅ Bot CMC démarré · Top 200 · Règles: +4%/1m (pump) · −5%/5m (dump)")

    while True:
        try:
            now_ts = time.time()

            # Répond aux commandes
            poll_commands_and_reply()

            # Prix CMC
            prices = fetch_top_prices()

            # Historique (conserver ~20 min)
            cutoff = now_ts - HISTORY_MIN * 60
            for sym, price in prices.items():
                arr = history.get(sym, [])
                arr.append((now_ts, price))
                while arr and arr[0][0] < cutoff:
                    arr.pop(0)
                history[sym] = arr

            # Détection
            hits = []
            for sym, arr in history.items():
                if len(arr) < 2:
                    continue
                p_now = arr[-1][1]

                # PUMP 1m
                t_cut = now_ts - 60
                p_then = next((p for (ts, p) in arr if ts >= t_cut), None)
                if p_then is not None:
                    pct = pct_change(p_now, p_then)
                    if pct is not None and pct >= 4.0:
                        hits.append((sym, 60, pct, p_now, "PUMP"))

                # DUMP 5m
                t_cut = now_ts - 300
                p_then = next((p for (ts, p) in arr if ts >= t_cut), None)
                if p_then is not None:
                    pct = pct_change(p_now, p_then)
                    if pct is not None and pct <= -5.0:
                        hits.append((sym, 300, pct, p_now, "DUMP"))

            # Envoi (cooldown)
            hits.sort(key=lambda x: abs(x[2]), reverse=True)
            for sym, w, pct, price, side in hits:
                key = (sym, w, side)
                if now_ts - last_alert.get(key, 0) < COOLDOWN_MIN * 60:
                    continue
                emoji = "📈" if side == "PUMP" else "📉"
                label = f"{w//60}m"
                msg = f"{emoji} {side} {sym} {pct:+.2f}% / {label}\nPrix: {price:.6g} {VS_CURRENCY}"
                send_telegram(msg)
                last_alert[key] = now_ts

            print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC] Scan OK")
            time.sleep(POLL_SECS)

        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", "?")
            txt  = getattr(e.response, "text", "")[:200]
            print("HTTP error:", code, txt, "...")
            time.sleep(5)
        except Exception as e:
            print("Error:", e)
            time.sleep(3)

if __name__ == "__main__":
    main()
