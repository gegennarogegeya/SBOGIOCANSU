import os
import asyncio
from threading import Thread, Lock
from flask import Flask, jsonify, render_template, Response
from telethon import TelegramClient

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")

RAW_CHANNELS = os.environ.get("CHANNEL_IDS") or os.environ.get("CHANNEL_ID", "")
CHANNEL_IDS = [x.strip() for x in RAW_CHANNELS.split(",") if x.strip()]

app = Flask(__name__)

loop = asyncio.new_event_loop()
tracks_cache = []
cache_lock = Lock()

def start_loop():
    asyncio.set_event_loop(loop)
    loop.run_forever()

Thread(target=start_loop, daemon=True).start()

# usa la sessione utente salvata (file sbogia.session)
client = TelegramClient("sbogia.session", API_ID, API_HASH, loop=loop)

def parse_channel_id(channel):
    try:
        return int(channel)
    except ValueError:
        return channel

async def ensure_connected():
    if not client.is_connected():
        await client.connect()
    # nessun bot_token: sessione utente già autorizzata

async def load_tracks():
    await ensure_connected()
    tracks = []

    for raw_channel in CHANNEL_IDS:
        try:
            entity = await client.get_entity(parse_channel_id(raw_channel))

            async for message in client.iter_messages(entity, limit=300):
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

            print(f"Canale OK: {raw_channel}")

        except Exception as error:
            print(f"ERRORE CANALE {raw_channel}: {repr(error)}")

    return tracks

async def refresh_tracks():
    global tracks_cache

    while True:
        try:
            new_tracks = await asyncio.wait_for(load_tracks(), timeout=25)

            with cache_lock:
                tracks_cache = new_tracks

            print(f"Playlist aggiornata: {len(new_tracks)} brani")

        except Exception as error:
            print(f"ERRORE AGGIORNAMENTO PLAYLIST: {repr(error)}")

        await asyncio.sleep(120)

async def download_audio(channel, message_id):
    try:
        await ensure_connected()
        entity = await client.get_entity(parse_channel_id(channel))
        message = await client.get_messages(entity, ids=int(message_id))

        if message and message.media:
            return await client.download_media(message, file=bytes)

    except Exception as error:
        print(f"ERRORE DOWNLOAD AUDIO: {repr(error)}")

    return None

asyncio.run_coroutine_threadsafe(refresh_tracks(), loop)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/playlist")
def get_playlist():
    with cache_lock:
        return jsonify(tracks_cache)

@app.route("/api/stream/<channel>/<int:message_id>")
def stream_track(channel, message_id):
    try:
        future = asyncio.run_coroutine_threadsafe(
            download_audio(channel, message_id),
            loop
        )
        audio_bytes = future.result(timeout=25)

        if audio_bytes:
            return Response(
                audio_bytes,
                mimetype="audio/mpeg",
                headers={"Accept-Ranges": "bytes"}
            )

    except Exception as error:
        print(f"ERRORE STREAM: {repr(error)}")

    return "Brano non trovato", 404

@app.route("/api/debug")
def debug():
    with cache_lock:
        total_tracks = len(tracks_cache)
