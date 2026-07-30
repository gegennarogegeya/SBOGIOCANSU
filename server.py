import os
import asyncio
from flask import Flask, jsonify, render_template
from telethon import TelegramClient

# Credenziali dalle variabili d'ambiente di Render
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Gestisce sia CHANNEL_IDS che CHANNEL_ID (separati da virgola se sono più di uno)
RAW_CHANNELS = os.environ.get("CHANNEL_IDS") or os.environ.get("CHANNEL_ID", "")
CHANNEL_IDS = [x.strip() for x in RAW_CHANNELS.split(",") if x.strip()]

app = Flask(__name__)

async def fetch_telegram_tracks():
    """Scansiona i canali Telegram usando Telethon e recupera tutti i brani audio."""
    tracks = []
    
    # Inizializza il client Telethon in modalità Bot
    client = TelegramClient('bot_session', API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)

    try:
        for channel in CHANNEL_IDS:
            # Converti in intero se è un ID numerico (es. -100123456789) oppure mantieni la stringa se è l'username (es. @mio_canale)
            try:
                target_channel = int(channel)
            except ValueError:
                target_channel = channel

            # Scorri tutti i messaggi del canale
            async for message in client.iter_messages(target_channel):
                if message.audio or (message.document and message.document.mime_type and message.document.mime_type.startswith("audio/")):
                    audio = message.audio or message.document
                    
                    # Estrai i metadati dall'attributo audio se presente
                    title = "Brano sconosciuto"
                    artist = "Canale Telegram"

                    if message.audio:
                        for attr in message.audio.attributes:
                            if hasattr(attr, 'title') and attr.title:
                                title = attr.title
                            if hasattr(attr, 'performer') and attr.performer:
                                artist = attr.performer
                    
                    # Se il titolo non è trovato, usa il nome del file
                    if title == "Brano sconosciuto" and hasattr(audio, 'attributes'):
                        for attr in audio.attributes:
                            if hasattr(attr, 'file_name') and attr.file_name:
                                title = attr.file_name

                    # Genera l'URL di streaming diretto al messaggio o al file
                    # Telegram Bot API standard per fare streaming richiede la rotto getFile
                    # Qui costruiamo un endpoint interno/link al file
                    tracks.append({
                        "id": message.id,
                        "title": title,
                        "artist": artist,
                        "channel_id": str(channel),
                        # Endpoint per lo streaming diretto del file
                        "url": f"/api/stream/{channel}/{message.id}"
                    })
    except Exception as e:
        print(f"Errore durante la scansione dei canali: {e}")
    finally:
        await client.disconnect()

    return tracks

async def download_track_bytes(channel, message_id):
    """Scarica il file di un brano specifico in memoria per inviarlo al browser."""
    client = TelegramClient('bot_session', API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    
    try:
        try:
            target_channel = int(channel)
        except ValueError:
            target_channel = channel

        message = await client.get_messages(target_channel, ids=int(message_id))
        if message and message.media:
            # Scarica il file in memoria
            buffer = await client.download_media(message, file=bytes)
            return buffer
    except Exception as e:
        print(f"Errore download file: {e}")
    finally:
        await client.disconnect()
    
    return None

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/playlist")
def get_playlist():
    if not API_ID or not API_HASH or not BOT_TOKEN or not CHANNEL_IDS:
        return jsonify([])

    # Esegui la funzione asincrona di Telethon dentro la rotta Flask
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tracks = loop.run_until_complete(fetch_telegram_tracks())
    loop.close()

    return jsonify(tracks)

@app.route("/api/stream/<channel>/<int:message_id>")
def stream_track(channel, message_id):
    """Route per lo streaming audio del singolo brano."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    audio_bytes = loop.run_until_complete(download_track_bytes(channel, message_id))
    loop.close()

    if audio_bytes:
        from flask import Response
        return Response(audio_bytes, mimetype="audio/mpeg")
    return "File non trovato", 440

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
