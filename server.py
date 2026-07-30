import os
import asyncio
from flask import Flask, jsonify, render_template, Response
from telethon import TelegramClient
from telethon.sessions import MemorySession

API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

RAW_CHANNELS = os.environ.get("CHANNEL_IDS") or os.environ.get("CHANNEL_ID", "")
CHANNEL_IDS = [x.strip() for x in RAW_CHANNELS.split(",") if x.strip()]

app = Flask(__name__)

def parse_channel_id(ch):
    ch = ch.strip()
    try:
        return int(ch)
    except ValueError:
        return ch

async def fetch_telegram_tracks():
    tracks = []
    errors = []
    
    if not API_ID or not API_HASH or not BOT_TOKEN:
        return tracks, ["Credenziali API_ID, API_HASH o BOT_TOKEN mancanti!"]

    client = TelegramClient(MemorySession(), int(API_ID), API_HASH)
    
    try:
        await client.start(bot_token=BOT_TOKEN)
    except Exception as e:
        return tracks, [f"Errore connessione Telethon: {e}"]

    for raw_ch in CHANNEL_IDS:
        target = parse_channel_id(raw_ch)
        try:
            async for message in client.iter_messages(target, limit=300):
                audio = message.audio or message.document
                if audio and (message.audio or (message.document and message.document.mime_type and message.document.mime_type.startswith("audio/"))):
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
            errors.append(f"Errore canale {raw_ch}: {e}")

    await client.disconnect()
    return tracks, errors

async def download_track_bytes(channel, message_id):
    """Scarica il brano da Telegram in memoria per inviarlo al player"""
    client = TelegramClient(MemorySession(), int(API_ID), API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    
    try:
        target = parse_channel_id(channel)
        message = await client.get_messages(target, ids=int(message_id))
        if message and message.media:
            buffer = await client.download_media(message, file=bytes)
            return buffer
    except Exception as e:
        print(f"Errore download file audio: {e}")
    finally:
        await client.disconnect()
    
    return None

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/playlist")
def get_playlist():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tracks, errors = loop.run_until_complete(fetch_telegram_tracks())
    loop.close()
    return jsonify(tracks)

# --- LA ROTTA FANTASMA CHE MANCAVA ---
@app.route("/api/stream/<channel>/<int:message_id>")
def stream_track(channel, message_id):
    """Fornisce lo streaming del file audio richiesto dal player web"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    audio_bytes = loop.run_until_complete(download_track_bytes(channel, message_id))
    loop.close()

    if audio_bytes:
        return Response(audio_bytes, mimetype="audio/mpeg")
    return "File audio non trovato", 404

@app.route("/api/debug")
def debug():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tracks, errors = loop.run_until_complete(fetch_telegram_tracks())
    loop.close()
    return jsonify({
        "api_id_ok": bool(API_ID),
        "api_hash_ok": bool(API_HASH),
        "bot_token_ok": bool(BOT_TOKEN),
        "channels": CHANNEL_IDS,
        "total_tracks_found": len(tracks),
        "errors": errors
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
