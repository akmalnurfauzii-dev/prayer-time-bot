import os
import json
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TIMEZONE = "Asia/Jakarta"

OFFSET_FILE = "offset.json"
STREAK_FILE = "streak.json"

PRAYER_NAMES = {
    "Fajr": "Subuh",
    "Dhuhr": "Dzuhur",
    "Asr": "Ashar",
    "Maghrib": "Maghrib",
    "Isha": "Isya",
}
ALL_PRAYER_KEYS = list(PRAYER_NAMES.keys())


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


def get_updates(offset):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"offset": offset, "timeout": 5}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("result", [])


def answer_callback(callback_query_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    requests.post(url, json={
        "callback_query_id": callback_query_id,
        "text": text,
        "show_alert": False,
    }, timeout=15)


def edit_message_mark_done(chat_id, message_id, original_text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    requests.post(url, json={
        "chat_id": chat_id,
        "message_id": message_id,
        "text": original_text + "\n\n✅ *Sudah dikonfirmasi*",
        "parse_mode": "Markdown",
    }, timeout=15)


def compute_streak(history):
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    streak = 0
    check_date = today

    today_str = today.strftime("%Y-%m-%d")
    today_confirmed = set(history.get(today_str, []))
    if len(today_confirmed) < 5:
        check_date = today - timedelta(days=1)

    while True:
        date_str = check_date.strftime("%Y-%m-%d")
        confirmed = set(history.get(date_str, []))
        if len(confirmed) >= 5:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    return streak


def send_streak_update(chat_id, prayer_key, today_confirmed_count, streak):
    nama = PRAYER_NAMES[prayer_key]
    progress_bar = "🟩" * today_confirmed_count + "⬜" * (5 - today_confirmed_count)

    text = (
        f"✅ *{nama}* tercatat!\n\n"
        f"Progress hari ini: {progress_bar} ({today_confirmed_count}/5)\n"
        f"🔥 Streak: *{streak} hari beruntun*"
    )
    if today_confirmed_count == 5:
        text += "\n\n🎉 MasyaAllah, lengkap 5 waktu hari ini!"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }, timeout=15)


def main():
    offset_data = load_json(OFFSET_FILE, {"offset": 0})
    streak_data = load_json(STREAK_FILE, {"history": {}, "current_streak": 0})
    history = streak_data.get("history", {})

    updates = get_updates(offset_data["offset"])
    print(f"Ditemukan {len(updates)} update baru.")

    latest_offset = offset_data["offset"]
    any_confirmation = False

    for update in updates:
        latest_offset = update["update_id"] + 1

        callback = update.get("callback_query")
        if not callback:
            continue

        data = callback.get("data", "")
        if not data.startswith("confirm|"):
            continue

        try:
            _, prayer_key, date_str = data.split("|")
        except ValueError:
            continue

        if prayer_key not in ALL_PRAYER_KEYS:
            continue

        chat_id = callback["message"]["chat"]["id"]
        message_id = callback["message"]["message_id"]
        original_text = callback["message"].get("text", "")
        callback_id = callback["id"]

        day_list = history.get(date_str, [])
        if prayer_key in day_list:
            answer_callback(callback_id, "Udah dicatat sebelumnya kok ✅")
            continue

        day_list.append(prayer_key)
        history[date_str] = day_list

        answer_callback(callback_id, "Tercatat! Barakallah 🤲")
        edit_message_mark_done(chat_id, message_id, original_text)

        streak = compute_streak(history)
        send_streak_update(chat_id, prayer_key, len(day_list), streak)

        any_confirmation = True
        print(f"Konfirmasi: {prayer_key} pada {date_str} — total hari ini: {len(day_list)}/5")

    offset_data["offset"] = latest_offset
    save_json(OFFSET_FILE, offset_data)

    streak_data["history"] = history
    streak_data["current_streak"] = compute_streak(history)
    save_json(STREAK_FILE, streak_data)

    if any_confirmation:
        print(f"Streak saat ini: {streak_data['current_streak']} hari")
    else:
        print("Tidak ada konfirmasi baru.")


if __name__ == "__main__":
    main()
