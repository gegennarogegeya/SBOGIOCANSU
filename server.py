import os
import asyncio
from threading import Thread
from flask import Flask, jsonify, render_template, Response
from telethon import TelegramClient

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

RAW_CHANNELS = os.environ.get("CHANNEL_IDS") or os.environ.get("CHANNEL_ID", "")
CHANNEL_IDS = [x.strip() for x in RAW_CHANNELS.split(",") if x.strip()]

app = Flask(__name__)

loop = asyncio.new_event_loop()

def start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

telethon_thread = Thread(target=start_loop, args=(loop,), daemon=True)
telethon_thread.start()

# Inizializza il bot senza file di sessione locali
client = TelegramClient(None, API_ID, API_HASH, loop=loop)

async def connect_client():
    if not client.is_connected():
        await client.start(bot_token=BOT_TOKEN)

asyncio.run_coroutine_threadsafe(connect_client(), loop)

def parse_channel_id(ch):
    try:
        return int(ch)
    except ValueError:
        return ch

async def get_all_tracks():
    tracks = []
    if not client.is_connected():
        await client.start(bot_token=BOT_TOKEN)

    for raw_ch in CHANNEL_IDS:
        target = parse_channel_id(raw_ch)
        try:
            entity = await client.get_entity(target)
            async for message in client.iter_messages(entity, limit=300):
                if message.audio or (message.document and message.document.mime_type and message.document.mime_type.startswith("audio/")):
                    audio = message.audio or message.document
                    title = "Brano sconosciuto"
                    artist = "Canale Telegram"

                    if message.audio:
                        for attr in message.audio.attributes:
                            if hasattr(attr, 'title') and attr.title:
                                title = attr.title
                            if hasattr(attr, 'performer') and attr.performer:
                                artist = attr.performer

                    if title == "Brano sconosciuto" and hasattr(audio, 'attributes'):
                        for attr in audio.attributes:
                            if hasattr(attr, 'file_name') and attr.file_name:
                                title = attr.file_name

                    tracks.append({
                        "id": message.id,
                        "title": title,
                        "artist": artist,
                        "channel_id": str(raw_ch),
                        "url": f"/api/stream/{raw_ch}/{message.id}"
                    })
        except Exception as e:
            print(f"Errore canale {raw_ch}: {e}")

    return tracks

async def get_audio_bytes(channel, message_id):
    try:
        if not client.is_connected():
            await client.start(bot_token=BOT_TOKEN)
        target = parse_channel_id(channel)
        entity = await client.get_entity(target)
        message = await client.get_messages(entity, ids=int(message_id))
        if message and message.media:
            return await client.download_media(message, file=bytes)
    except Exception as e:
        print(f"Errore download audio: {e}")
    return None

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/playlist")
def get_playlist():
    try:
        future = asyncio.run_coroutine_threadsafe(get_all_tracks(), loop)
        tracks = future.result(timeout=60)
        return jsonify(tracks)
    except Exception as e:
        print(f"Errore playlist: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/stream/<channel>/<int:message_id>")
def stream_track(channel, message_id):
    try:
        future = asyncio.run_coroutine_threadsafe(get_audio_bytes(channel, message_id), loop)
        audio_bytes = future.result(timeout=60)
        if audio_bytes:
            return Response(audio_bytes, mimetype="audio/mpeg")
    except Exception as e:
        print(f"Errore stream: {e}")
    return "Brano non trovato", 404

@app.route("/api/debug")
def debug():
    try:
        future = asyncio.run_coroutine_threadsafe(get_all_tracks(), loop)
        tracks = future.result(timeout=60)
        return jsonify({
            "status": "online",
            "bot_mode": True,
            "channels": CHANNEL_IDS,
            "total_tracks": len(tracks)
        })
    except Exception as e:
        return jsonify({"status": "error", "details": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
