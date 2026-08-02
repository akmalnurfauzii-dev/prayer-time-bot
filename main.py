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
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

# Fallback chain — kalau model pertama 404/error, otomatis coba berikutnya
FREE_MODELS = [
    "meta-llama/llama-3.1-8b-instruct:free",
    "google/gemma-3-12b-it:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "deepseek/deepseek-r1:free",
    "google/gemma-3-27b-it:free",
    "moonshotai/kimi-k2:free",
    "qwen/qwen3-coder:free",
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
    for model in FREE_MODELS:
        try:
            print(f"Mencoba model: {model}")
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                },
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()["choices"][0]["message"]["content"].strip()
            print(f"Berhasil dengan model: {model}")
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


if __name__ == "__main__":
    main()
