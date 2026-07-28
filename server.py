import os
import requests
from flask import Flask, jsonify, render_template

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_IDS = {
    x.strip() for x in os.environ.get("CHANNEL_IDS", "").split(",") if x.strip()
}

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/playlist")
def get_playlist():
    if not BOT_TOKEN or not CHANNEL_IDS:
        return jsonify([])

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

    try:
        res = requests.get(url).json()
        tracks = []

        if res.get("ok"):
            for update in res.get("result", []):
                msg = update.get("channel_post") or update.get("message") or {}
                chat_id = str(msg.get("chat", {}).get("id", ""))

                if chat_id not in CHANNEL_IDS:
                    continue

                if "audio" not in msg:
                    continue

                audio = msg["audio"]
                file_id = audio.get("file_id")

                if not file_id:
                    continue

                f_res = requests.get(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
                    params={"file_id": file_id}
                ).json()

                if not f_res.get("ok"):
                    continue

                file_path = f_res["result"]["file_path"]
                stream_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

                tracks.append({
                    "title": audio.get("title") or audio.get("file_name") or "Brano sconosciuto",
                    "artist": audio.get("performer") or "Canale Telegram",
                    "url": stream_url
                })

        return jsonify(tracks)

    except Exception:
        return jsonify([])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
