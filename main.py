import os
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# ==== KONFIGURASI ====
LATITUDE = -7.3886
LONGITUDE = 109.3608
TIMEZONE = "Asia/Jakarta"
CALC_METHOD = 20

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS = [
    "llama-3.3-70b-versatile",   # kualitas terbaik, 1000 req/hari
    "llama-3.1-8b-instant",      # fallback, 14400 req/hari
]

STATE_FILE = "state.json"
PRAYER_NAMES = {
    "Fajr": "Subuh",
    "Dhuhr": "Dzuhur",
    "Asr": "Ashar",
    "Maghrib": "Maghrib",
    "Isha": "Isya",
}
NIAT = {
    "Fajr": "Ushalli fardhal Shubhi rak'ataini mustaqbilal qiblati adaa'an lillaahi ta'aala.",
    "Dhuhr": "Ushalli fardhazh Zhuhri arba'a raka'atin mustaqbilal qiblati adaa'an lillaahi ta'aala.",
    "Asr": "Ushalli fardhal 'Ashri arba'a raka'atin mustaqbilal qiblati adaa'an lillaahi ta'aala.",
    "Maghrib": "Ushalli fardhal Maghribi tsalaatsa raka'atin mustaqbilal qiblati adaa'an lillaahi ta'aala.",
    "Isha": "Ushalli fardhal 'Isyaa-i arba'a raka'atin mustaqbilal qiblati adaa'an lillaahi ta'aala.",
}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        today = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")
        if data.get("date") == today:
            return data
    return {"date": datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d"), "sent": []}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def get_prayer_times():
    today = datetime.now(ZoneInfo(TIMEZONE))
    url = "https://api.aladhan.com/v1/timings"
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "method": CALC_METHOD,
        "date": today.strftime("%d-%m-%Y"),
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    timings = resp.json()["data"]["timings"]
    return {k: timings[k] for k in PRAYER_NAMES}


def find_due_prayer(prayer_times, state):
    now = datetime.now(ZoneInfo(TIMEZONE))
    now_str = now.strftime("%H:%M")
    for key, waktu in prayer_times.items():
        if waktu == now_str and key not in state["sent"]:
            return key
    return None


def generate_motivation(prayer_key):
    nama_waktu = PRAYER_NAMES[prayer_key]
    prompt = f"""Buatkan pesan singkat pengingat waktu sholat {nama_waktu} dalam Bahasa Indonesia untuk seorang pemuda muslim bernama Akmal yang sedang berjuang meraih beasiswa kuliah S1 Computer Science ke luar negeri dan membantu usaha keluarga.

Format pesan:
1. Satu kalimat motivasi yang related dengan waktu {nama_waktu} — tentang semangat sukses, rezeki, dan selalu mengingat Allah dalam usaha (beasiswa, bisnis, belajar)
2. Buat bervariasi tiap kali, jangan template kaku, boleh sisipkan quote islami singkat atau ayat/hadits (tanpa perlu sertakan sanad panjang, cukup makna/terjemahan singkat)
3. Nada hangat, membangun semangat, bukan menggurui
4. Maksimal 4-5 kalimat total
5. Jangan pakai emoji berlebihan (maksimal 1-2 kalau perlu)

Jawab HANYA isi pesannya saja, tanpa embel-embel pembuka seperti "Berikut pesannya:".
"""
    last_error = None
    for model in GROQ_MODELS:
        try:
            print(f"Mencoba model: {model}")
            resp = requests.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                },
                timeout=30,
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Error: {resp.text[:300]}")
            resp.raise_for_status()
            result = resp.json()["choices"][0]["message"]["content"].strip()
            print(f"Berhasil dengan: {model}")
            return result
        except Exception as e:
            print(f"Model {model} gagal: {e}")
            last_error = e
            continue

    raise Exception(f"Semua model gagal. Error terakhir: {last_error}")


def send_telegram(prayer_key, motivation_text):
    nama_waktu = PRAYER_NAMES[prayer_key]
    niat = NIAT[prayer_key]
    now = datetime.now(ZoneInfo(TIMEZONE)).strftime("%H:%M")

    message = (
        f"🕌 *Waktu Sholat {nama_waktu}* — {now} WIB\n\n"
        f"*Niat:*\n_{niat}_\n\n"
        f"*Pengingat:*\n{motivation_text}"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }, timeout=15)
    resp.raise_for_status()


def main():
    state = load_state()
    prayer_times = get_prayer_times()
    due = find_due_prayer(prayer_times, state)

    if due is None:
        print("Belum ada waktu sholat yang jatuh tempo saat ini.")
        return

    print(f"Waktu {PRAYER_NAMES[due]} jatuh tempo, generate & kirim pesan...")
    motivation = generate_motivation(due)
    send_telegram(due, motivation)

    state["sent"].append(due)
    save_state(state)
    print("Terkirim.")


def test_full_flow():
    print("=== TEST FULL FLOW ===")

    print("\n[1] Fetch jadwal sholat Purbalingga hari ini...")
    prayer_times = get_prayer_times()
    for key, waktu in prayer_times.items():
        print(f"  {PRAYER_NAMES[key]}: {waktu} WIB")

    print("\n[2] Generate motivasi via Groq AI...")
    first_prayer = list(prayer_times.keys())[0]
    motivation = generate_motivation(first_prayer)
    print(f"\n  Hasil motivasi:\n  {motivation}")

    print("\n[3] Kirim pesan lengkap ke Telegram...")
    send_telegram(first_prayer, motivation)
    print("  Terkirim!")

    print("\n=== SELESAI — cek Telegram lo ===")


if __name__ == "__main__":
    test_full_flow()  # ← TEST dulu
    # main()          # ← PRODUCTION (aktifin kalau test udah oke)
