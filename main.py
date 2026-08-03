import os
import json
import random
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote

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
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

WINDOW_MINUTES = 30

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

# Prompt ilustrasi per waktu sholat — suasana khas tiap waktu
IMAGE_PROMPTS = {
    "Fajr": "serene dawn sky over silhouette of a mosque, soft blue and pink gradient, misty morning, minimalist digital painting, peaceful atmosphere, birds flying, no people, no text",
    "Dhuhr": "bright midday sky over silhouette of a mosque, clear blue sky, warm sunlight, minimalist digital painting, peaceful atmosphere, no people, no text",
    "Asr": "golden afternoon light over silhouette of a mosque, warm orange glow, long shadows, minimalist digital painting, peaceful atmosphere, no people, no text",
    "Maghrib": "beautiful sunset over silhouette of a mosque, dramatic orange and purple sky, dusk atmosphere, minimalist digital painting, peaceful, no people, no text",
    "Isha": "peaceful night sky over silhouette of a mosque, stars and crescent moon, deep blue night, minimalist digital painting, serene atmosphere, no people, no text",
}


def load_state():
    today = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
            if data.get("date") == today:
                return data
        except Exception:
            pass
    fresh = {"date": today, "sent": []}
    save_state(fresh)
    return fresh


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


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
    now_minutes = now.hour * 60 + now.minute
    for key, waktu in prayer_times.items():
        if key in state["sent"]:
            continue
        h, m = map(int, waktu.split(":"))
        diff = now_minutes - (h * 60 + m)
        if 0 <= diff <= WINDOW_MINUTES:
            return key
    return None


def generate_motivation(prayer_key):
    nama_waktu = PRAYER_NAMES[prayer_key]
    prompt = f"""Buatkan pesan singkat pengingat waktu sholat {nama_waktu} dalam Bahasa Indonesia untuk seorang pemuda muslim bernama Akmal yang sedang berjuang meraih beasiswa kuliah S1 Computer Science ke luar negeri dan membantu usaha keluarga.

Format pesan:
1. Motivasi related dengan waktu {nama_waktu} — tentang semangat sukses, rezeki, dan selalu mengingat Allah dalam usaha
2. Buat bervariasi, jangan template kaku, boleh sisipkan quote islami singkat
3. Nada hangat, membangun semangat, bukan menggurui
4. Maksimal 4-5 kalimat total
5. Jangan pakai emoji berlebihan (maksimal 1-2)

Jawab HANYA isi pesannya saja.
"""
    last_error = None
    for model in GROQ_MODELS:
        try:
            resp = requests.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 300, "temperature": 0.9},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            last_error = e
            continue
    raise Exception(f"Semua model gagal: {last_error}")


def get_image_url(prayer_key):
    prompt = IMAGE_PROMPTS[prayer_key]
    seed = random.randint(1, 999999)
    encoded_prompt = quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=576&seed={seed}&nologo=true"


def send_telegram_photo(image_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "Markdown",
    }, timeout=30)
    if resp.status_code != 200:
        print(f"Gagal kirim foto: {resp.text[:300]}")
        return False
    return True


def send_telegram(prayer_key, motivation_text):
    nama_waktu = PRAYER_NAMES[prayer_key]
    niat = NIAT[prayer_key]
    now = datetime.now(ZoneInfo(TIMEZONE))
    now_str = now.strftime("%H:%M")
    today_str = now.strftime("%Y-%m-%d")

    caption = f"🕌 *Waktu Sholat {nama_waktu}* — {now_str} WIB"

    # Kirim ilustrasi dulu
    image_url = get_image_url(prayer_key)
    print(f"Generate ilustrasi: {image_url}")
    photo_sent = send_telegram_photo(image_url, caption)
    if not photo_sent:
        print("Ilustrasi gagal dikirim, lanjut kirim teks aja.")

    # Kirim pesan lengkap + tombol konfirmasi
    message = (
        f"*Niat:*\n_{niat}_\n\n"
        f"*Pengingat:*\n{motivation_text}"
    )

    reply_markup = {
        "inline_keyboard": [[
            {"text": "✅ Sudah Sholat", "callback_data": f"confirm|{prayer_key}|{today_str}"}
        ]]
    }

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "reply_markup": reply_markup,
    }, timeout=15)
    resp.raise_for_status()
    print("Pesan + tombol konfirmasi terkirim!")


def main():
    state = load_state()
    prayer_times = get_prayer_times()
    due = find_due_prayer(prayer_times, state)

    if due is None:
        print("Belum ada waktu sholat yang jatuh tempo saat ini.")
        return

    motivation = generate_motivation(due)
    send_telegram(due, motivation)

    state["sent"].append(due)
    save_state(state)
    print(f"Terkirim untuk {PRAYER_NAMES[due]}.")


if __name__ == "__main__":
    # main()
    motivation = generate_motivation("Dhuhr")
    send_telegram("Dhuhr", motivation)
