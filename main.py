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
GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

WINDOW_MINUTES = 30

STATE_FILE = "state.json"
MOOD_FILE = "mood.json"

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
NIAT_JUMAT = "Ushalli fardhal Jumu'ati rak'ataini imaman/ma'muman lillaahi ta'aala."

IMAGE_PROMPTS = {
    "Fajr": "serene dawn sky over silhouette of a mosque, soft blue and pink gradient, misty morning, minimalist digital painting, peaceful atmosphere, birds flying, no people, no text",
    "Dhuhr": "bright midday sky over silhouette of a mosque, clear blue sky, warm sunlight, minimalist digital painting, peaceful atmosphere, no people, no text",
    "Asr": "golden afternoon light over silhouette of a mosque, warm orange glow, long shadows, minimalist digital painting, peaceful atmosphere, no people, no text",
    "Maghrib": "beautiful sunset over silhouette of a mosque, dramatic orange and purple sky, dusk atmosphere, minimalist digital painting, peaceful, no people, no text",
    "Isha": "peaceful night sky over silhouette of a mosque, stars and crescent moon, deep blue night, minimalist digital painting, serene atmosphere, no people, no text",
}

HARI_INDO = {0: "Senin", 1: "Selasa", 2: "Rabu", 3: "Kamis", 4: "Jumat", 5: "Sabtu", 6: "Minggu"}


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_state():
    today = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")
    data = load_json(STATE_FILE, {})
    if data.get("date") == today:
        return data
    fresh = {"date": today, "sent": []}
    save_json(STATE_FILE, fresh)
    return fresh


def get_latest_mood():
    data = load_json(MOOD_FILE, {"history": {}})
    history = data.get("history", {})
    if not history:
        return None
    latest_date = max(history.keys())
    return history[latest_date]


def get_prayer_times():
    today = datetime.now(ZoneInfo(TIMEZONE))
    url = "https://api.aladhan.com/v1/timings"
    params = {
        "latitude": LATITUDE, "longitude": LONGITUDE,
        "method": CALC_METHOD, "date": today.strftime("%d-%m-%Y"),
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


def call_groq(prompt, max_tokens=350):
    last_error = None
    for model in GROQ_MODELS:
        try:
            resp = requests.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0.9},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            last_error = e
            continue
    raise Exception(f"Semua model gagal: {last_error}")


def generate_motivation(prayer_key, is_jumat=False):
    nama_waktu = "Sholat Jumat" if is_jumat else PRAYER_NAMES[prayer_key]
    mood = get_latest_mood()

    mood_context = ""
    if mood:
        mood_map = {
            "senang": "Akmal lagi merasa semangat dan senang — boleh ikut bersyukur dan mendorong dia mempertahankan energi positif itu.",
            "biasa": "Akmal lagi merasa biasa aja / netral — kasih dorongan lembut biar makin semangat.",
            "lelah": "Akmal lagi merasa lelah — nada pesan lebih menenangkan, jangan menuntut, validasi kelelahannya dulu baru kasih semangat pelan.",
            "sedih": "Akmal lagi merasa sedih/berat — nada pesan penuh empati dan lembut, prioritaskan menenangkan hati sebelum motivasi, ingatkan Allah selalu bersama orang sabar.",
        }
        mood_context = f"\nKonteks tambahan: {mood_map.get(mood, '')}"

    prompt = f"""Buatkan pesan singkat pengingat waktu {nama_waktu} dalam Bahasa Indonesia untuk seorang pemuda muslim bernama Akmal yang sedang berjuang meraih beasiswa kuliah S1 Computer Science ke luar negeri dan membantu usaha keluarga.{mood_context}

Format pesan:
1. Motivasi related dengan waktu {nama_waktu} — tentang semangat sukses, rezeki, dan selalu mengingat Allah dalam usaha
2. Buat bervariasi, jangan template kaku, boleh sisipkan quote islami singkat
3. Nada hangat, sesuaikan dengan konteks mood di atas kalau ada
4. Maksimal 4-5 kalimat total
5. Jangan pakai emoji berlebihan (maksimal 1-2)

Jawab HANYA isi pesannya saja.
"""
    return call_groq(prompt)


def generate_tafsir_mingguan():
    prompt = """Buatkan 1 ayat Al-Qur'an pendek (sertakan nama surah dan nomor ayat) beserta tafsir/makna singkatnya dalam Bahasa Indonesia, temanya seputar semangat berusaha, kesabaran, atau menuntut ilmu — cocok untuk pemuda yang sedang berjuang kuliah dan bekerja.

Format:
- Tulis ayatnya (terjemahan saja, bukan Arab)
- Sebutkan surah dan ayat
- Beri tafsir singkat 2-3 kalimat, bahasa yang mudah dipahami
- Akhiri dengan catatan bahwa ini pemahaman ringkas, dianjurkan tabayyun ke ustadz/kajian untuk pendalaman

Jawab HANYA isi pesannya, tanpa pembuka.
"""
    return call_groq(prompt, max_tokens=400)


def get_image_url(prayer_key):
    prompt = IMAGE_PROMPTS[prayer_key]
    seed = random.randint(1, 999999)
    encoded_prompt = quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=576&seed={seed}&nologo=true"


def send_telegram_photo(image_url, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID, "photo": image_url,
            "caption": caption, "parse_mode": "Markdown",
        }, timeout=60)
        return resp.status_code == 200
    except Exception as e:
        print(f"Exception kirim foto: {e}")
        return False


def send_telegram_text(text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()


def send_prayer_message(prayer_key, motivation_text, is_jumat=False):
    now = datetime.now(ZoneInfo(TIMEZONE))
    now_str = now.strftime("%H:%M")
    today_str = now.strftime("%Y-%m-%d")
    hari = HARI_INDO[now.weekday()]

    if is_jumat:
        nama_waktu = "Sholat Jumat"
        niat = NIAT_JUMAT
        header = f"🕌 *Waktu {nama_waktu}* — {now_str} WIB ({hari})"
        extra_note = "\n\n📿 _Jangan lupa perbanyak sholawat dan baca Surah Al-Kahfi hari ini._"
    else:
        nama_waktu = PRAYER_NAMES[prayer_key]
        niat = NIAT[prayer_key]
        header = f"🕌 *Waktu Sholat {nama_waktu}* — {now_str} WIB ({hari})"
        extra_note = ""

    image_url = get_image_url(prayer_key)
    send_telegram_photo(image_url, header)

    message = f"*Niat:*\n_{niat}_\n\n*Pengingat:*\n{motivation_text}{extra_note}"

    reply_markup = {
        "inline_keyboard": [[
            {"text": "✅ Sudah Sholat", "callback_data": f"confirm|{prayer_key}|{today_str}"}
        ]]
    }
    send_telegram_text(message, reply_markup)
    print(f"Pesan {nama_waktu} terkirim!")


def send_tafsir_mingguan():
    tafsir = generate_tafsir_mingguan()
    text = f"📖 *Tafsir Singkat Jumat Ini*\n\n{tafsir}"
    send_telegram_text(text)
    print("Tafsir mingguan terkirim!")


def send_mood_checkin():
    today_str = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")
    text = "🌙 Sebelum istirahat, gimana perasaan Akmal hari ini?"
    reply_markup = {
        "inline_keyboard": [[
            {"text": "😊 Senang", "callback_data": f"mood|senang|{today_str}"},
            {"text": "😐 Biasa", "callback_data": f"mood|biasa|{today_str}"},
        ], [
            {"text": "😴 Lelah", "callback_data": f"mood|lelah|{today_str}"},
            {"text": "😔 Sedih", "callback_data": f"mood|sedih|{today_str}"},
        ]]
    }
    send_telegram_text(text, reply_markup)
    print("Mood check-in terkirim!")


def main():
    state = load_state()
    prayer_times = get_prayer_times()
    due = find_due_prayer(prayer_times, state)

    if due is None:
        print("Belum ada waktu sholat yang jatuh tempo saat ini.")
        return

    now = datetime.now(ZoneInfo(TIMEZONE))
    is_jumat_dzuhur = (due == "Dhuhr" and now.weekday() == 4)

    motivation = generate_motivation(due, is_jumat=is_jumat_dzuhur)
    send_prayer_message(due, motivation, is_jumat=is_jumat_dzuhur)

    if due == "Fajr" and now.weekday() == 4:
        send_tafsir_mingguan()

    if due == "Isha":
        send_mood_checkin()

    state["sent"].append(due)
    save_json(STATE_FILE, state)
    print(f"State diupdate: {state['sent']}")


if __name__ == "__main__":
    # ==== MODE TEST: paksa simulasi Jumat ====
    motivation = generate_motivation("Dhuhr", is_jumat=True)
    send_prayer_message("Dhuhr", motivation, is_jumat=True)
    send_tafsir_mingguan()
    send_mood_checkin()
    # main()
