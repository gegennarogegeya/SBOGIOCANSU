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

# Usa il file sbogia.session caricato su GitHub
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
client = TelegramClient('sbogia', API_ID, API_HASH, loop=loop)

def start_telethon():
    asyncio.set_event_loop(loop)
    loop.run_until_complete(client.start(bot_token=BOT_TOKEN))
    loop.run_forever()

telethon_thread = Thread(target=start_telethon, daemon=True)
telethon_thread.start()

def parse_channel_id(ch):
    try:
        return int(ch)
    except ValueError:
        return ch

async def get_all_tracks():
    tracks = []
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
    future = asyncio.run_coroutine_threadsafe(get_all_tracks(), loop)
    tracks = future.result(timeout=20)
    return jsonify(tracks)

@app.route("/api/stream/<channel>/<int:message_id>")
def stream_track(channel, message_id):
    future = asyncio.run_coroutine_threadsafe(get_audio_bytes(channel, message_id), loop)
    audio_bytes = future.result(timeout=40)
    
    if audio_bytes:
        return Response(audio_bytes, mimetype="audio/mpeg")
    return "Brano non trovato", 404

@app.route("/api/debug")
def debug():
    future = asyncio.run_coroutine_threadsafe(get_all_tracks(), loop)
    tracks = future.result(timeout=20)
    return jsonify({
        "status": "online",
        "session_file": "sbogia.session",
        "channels": CHANNEL_IDS,
        "total_tracks": len(tracks)
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
