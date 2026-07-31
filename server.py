import os
import asyncio
from flask import Flask, jsonify, render_template, Response, stream_with_context
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
TG_STRING_SESSION = os.environ.get("TG_STRING_SESSION", "")

RAW_CHANNELS = os.environ.get("CHANNEL_IDS") or os.environ.get("CHANNEL_ID", "")
CHANNEL_IDS = [x.strip() for x in RAW_CHANNELS.split(",") if x.strip()]

app = Flask(__name__)

loop = asyncio.new_event_loop()
client = TelegramClient(StringSession(TG_STRING_SESSION), API_ID, API_HASH, loop=loop)

tracks_cache = []

def parse_channel_id(channel):
    try:
        return int(channel)
    except ValueError:
        return channel

async def load_tracks():
    await client.connect()
    tracks = []

    for raw_channel in CHANNEL_IDS:
        target = parse_channel_id(raw_channel)
        try:
            entity = await client.get_entity(target)
            print(f"Canale OK: {raw_channel} -> {getattr(entity, 'title', None)}")

            async for message in client.iter_messages(entity, limit=500):
                if not message.media:
                    continue

                audio = message.audio or message.document
                if not audio:
                    continue

                mime_type = getattr(audio, "mime_type", "") or ""
                if not message.audio and not mime_type.startswith("audio/"):
                    continue

                title = "Brano sconosciuto"
                artist = "Canale Telegram"

                for attr in getattr(audio, "attributes", []):
                    if getattr(attr, "title", None):
                        title = attr.title
                    if getattr(attr, "performer", None):
                        artist = attr.performer
                    if title == "Brano sconosciuto" and getattr(attr, "file_name", None):
                        title = attr.file_name

                tracks.append({
                    "id": message.id,
                    "title": title,
                    "artist": artist,
                    "channel_id": str(raw_channel),
                    "url": f"/api/stream/{raw_channel}/{message.id}"
                })

        except Exception as error:
            print(f"ERRORE CANALE {raw_channel}: {repr(error)}")

    print(f"Playlist aggiornata: {len(tracks)} brani totali")
    return tracks

async def download_audio(channel, message_id):
    try:
        target = parse_channel_id(channel)
        entity = await client.get_entity(target)
        message = await client.get_messages(entity, ids=int(message_id))

        if message and message.media:
            return await client.download_media(message, file=bytes)

    except Exception as error:
        print(f"ERRORE DOWNLOAD AUDIO: {repr(error)}")

    return None

def load_tracks_sync():
    global tracks_cache
    try:
        tracks_cache = loop.run_until_complete(load_tracks())
    except Exception as error:
        print(f"ERRORE: {repr(error)}")

load_tracks_sync()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/playlist")
def get_playlist():
    return jsonify(tracks_cache)

@app.route("/api/stream/<channel>/<int:message_id>")
def stream_track(channel, message_id):
    try:
        audio_bytes = loop.run_until_complete(download_audio(channel, message_id))

        if audio_bytes:
            return Response(
                audio_bytes,
                mimetype="audio/mpeg",
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(len(audio_bytes))
                }
            )

    except Exception as error:
        print(f"ERRORE STREAM: {repr(error)}")

    return "Brano non trovato", 404

@app.route("/api/debug")
def debug():
    return jsonify({
        "status": "online",
        "channels": CHANNEL_IDS,
        "total_tracks": len(tracks_cache)
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
