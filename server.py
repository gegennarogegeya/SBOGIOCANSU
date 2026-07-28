import os
import requests
from flask import Flask, jsonify, render_template

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8968645232:AAEo2FhkwZFrDWRSX1cfqz-SE9M35RBRVkM")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1002093868258")

app = Flask(__name__, template_folder=".")

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/playlist")
def get_playlist():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    res = requests.get(url).json()
    
    tracks = []
    if res.get("ok"):
        for update in res.get("result", []):
            msg = update.get("channel_post", {})
            if str(msg.get("chat", {}).get("id")) == CHANNEL_ID and "audio" in msg:
                audio = msg["audio"]
                file_id = audio["file_id"]
                f_res = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}").json()
                if f_res.get("ok"):
                    file_path = f_res["result"]["file_path"]
                    stream_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                    tracks.append({
                        "title": audio.get("title", audio.get("file_name", "Brano sconosciuto")),
                        "artist": audio.get("performer", "Canale Telegram"),
                        "url": stream_url
                    })
    return jsonify(tracks)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
