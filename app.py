import os
import tempfile
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
TG_FILE = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}"


def send_message(chat_id, text):
    requests.post(
        f"{TG_API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )


@app.route("/", methods=["GET"])
def home():
    return "Voice Tasks Bot is running", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(silent=True) or {}
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")

    if not chat_id:
        return "ok", 200

    audio = message.get("voice") or message.get("audio") or message.get("document")

    if not audio:
        send_message(
            chat_id,
            "Пришли мне голосовое сообщение или аудиофайл."
        )
        return "ok", 200

    file_id = audio.get("file_id")

    try:
        file_info = requests.get(
            f"{TG_API}/getFile",
            params={"file_id": file_id},
            timeout=30
        ).json()

        file_path = file_info["result"]["file_path"]

        audio_data = requests.get(
            f"{TG_FILE}/{file_path}",
            timeout=60
        ).content

        suffix = os.path.splitext(file_path)[1] or ".ogg"

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False
        ) as temp_file:
            temp_file.write(audio_data)
            temp_path = temp_file.name

        with open(temp_path, "rb") as audio_file:
            response = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}"
                },
                files={
                    "file": (
                        "audio.ogg",
                        audio_file,
                        "audio/ogg"
                    )
                },
                data={
                    "model": "whisper-large-v3-turbo",
                    "language": "ru",
                    "response_format": "json"
                },
                timeout=120
            )

        os.remove(temp_path)
print("GROQ RESPONSE:", response.status_code, response.text, flush=True)
        response.raise_for_status()
        text = response.json().get("text", "").strip()

        if text:
            send_message(chat_id, text)
        else:
            send_message(chat_id, "Не удалось распознать запись.")

    except Exception as error:
        print(repr(error), flush=True)
        send_message(
            chat_id,
            "Не удалось распознать аудио."
        )

    return "ok", 200
