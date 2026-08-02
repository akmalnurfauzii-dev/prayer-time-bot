# Jadwal Sholat Bot

Bot yang otomatis kirim notifikasi Telegram tiap waktu sholat (Subuh, Dzuhur, Ashar, Maghrib, Isya) berisi niat + pesan motivasi random yang di-generate AI (via OpenRouter).

## Cara Kerja

1. GitHub Actions jalan tiap 10 menit (cron).
2. Script ambil jadwal sholat hari ini dari [Aladhan API](https://aladhan.com/prayer-times-api) berdasarkan lokasi Purbalingga (metode Kemenag RI).
3. Kalau waktu sekarang cocok dengan salah satu waktu sholat DAN belum pernah dikirim hari ini, script:
   - Minta AI (OpenRouter) generate pesan motivasi singkat yang beda-beda tiap hari
   - Kirim pesan (niat + motivasi) ke Telegram
4. Status "sudah kirim" disimpan di `state.json` dan di-commit balik ke repo, reset otomatis tiap hari baru.

## Setup

### 1. Bikin Bot Telegram (kalau belum punya)

1. Chat [@BotFather](https://t.me/BotFather) di Telegram, kirim `/newbot`, ikuti instruksinya.
2. Simpan **token** yang dikasih (formatnya `123456:ABC-DEF...`).
3. Cari **chat_id** kamu: chat bot barusan sekali (`/start`), lalu buka di browser:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   Cari field `"chat":{"id": ...}` — itu chat_id kamu.

### 2. Bikin API Key OpenRouter

1. Daftar di [openrouter.ai](https://openrouter.ai)
2. Buat API key di halaman [Keys](https://openrouter.ai/keys)
3. Model default yang dipakai: `google/gemini-2.0-flash-exp:free` (gratis). Bisa diganti lewat secret `OPENROUTER_MODEL` kalau mau model lain.

### 3. Push Repo ke GitHub

```bash
cd jadwal-sholat-bot
git init
git add .
git commit -m "Initial commit: jadwal sholat bot"
git branch -M main
git remote add origin https://github.com/<username>/<repo-name>.git
git push -u origin main
```

### 4. Set GitHub Secrets

Di repo GitHub → Settings → Secrets and variables → Actions → New repository secret. Tambahkan 3 secret ini:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token dari BotFather |
| `TELEGRAM_CHAT_ID` | Chat ID kamu |
| `OPENROUTER_API_KEY` | API key dari OpenRouter |

### 5. Testing Manual

Ke tab **Actions** di repo → pilih workflow "Jadwal Sholat Bot" → **Run workflow** (tombol manual trigger). Ini bakal jalan sekali, tapi cuma kirim pesan kalau waktu saat itu PAS sama salah satu waktu sholat. Untuk testing beneran ngirim pesan, sementara ubah salah satu jadwal di respons API secara manual di kode, atau tunggu waktu sholat asli.

## Ubah Lokasi

Kalau lokasi berubah, edit `LATITUDE` dan `LONGITUDE` di `main.py`.

## Soal "Dering" / Alarm Asli

Telegram API cuma bisa kirim notifikasi biasa, bukan trigger dering/panggilan di HP. Untuk bikin notifikasi ini berbunyi seperti alarm:

- **Cara simpel:** di Telegram, set custom notification sound khusus buat chat bot ini (biasanya suara makin nyaring/panjang) via Chat Settings → Notifications.
- **Cara advanced (Android):** pakai app **MacroDroid** (gratis) — bikin automation yang "dengerin" notifikasi masuk dari bot Telegram ini, lalu trigger dia untuk memutar alarm/ringtone asli sampai di-dismiss manual.
