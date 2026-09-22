import os
import tempfile
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id, text):
    requests.post(
        f"{TG_API}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=30,
    )


@app.get("/")
def home():
    return "Voice Tasks Bot is running", 200


@app.post("/webhook")
def webhook():
    update = request.get_json(silent=True) or {}
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")

    if not chat_id:
        return "ok", 200

    if "voice" in message:
        file_id = message["voice"]["file_id"]
    elif "audio" in message:
        file_id = message["audio"]["file_id"]
    elif "document" in message:
        file_id = message["document"]["file_id"]
    else:
        send_message(
            chat_id,
            "Пришли мне голосовое сообщение или аудиофайл."
        )
        return "ok", 200

    try:
        info = requests.get(
            f"{TG_API}/getFile",
            params={"file_id": file_id},
            timeout=30,
        ).json()

        file_path = info["result"]["file_path"]
        audio = requests.get(
            f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}",
            timeout=60,
        ).content

        suffix = os.path.splitext(file_path)[1] or ".ogg"

        with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
            tmp.write(audio)
            tmp.flush()

            with open(tmp.name, "rb") as f:
                response = requests.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}"
                    },
                    files={"file": (os.path.basename(file_path), f)},
                    data={
                        "model": "whisper-large-v3-turbo",
                        "language": "ru",
                        "response_format": "json",
                    },
                    timeout=120,
                )

        response.raise_for_status()
        text = response.json()["text"].strip()

        send_message(chat_id, text or "Не удалось распознать речь.")

    except Exception as e:
        print(e, flush=True)
        send_message(
            chat_id,
            "Не получилось распознать запись. Попробуй ещё раз."
        )

    return "ok", 200
    @app.get("/setup")
def setup_webhook():
    webhook_url = "https://voice-tasks-bot.onrender.com/webhook"

    response = requests.post(
        f"{TG_API}/setWebhook",
        json={"url": webhook_url},
        timeout=30,
    )

    return response.json()
