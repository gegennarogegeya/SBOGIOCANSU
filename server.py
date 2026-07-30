import os
import asyncio
from threading import Thread
from flask import Flask, jsonify
from telethon import TelegramClient

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")

RAW_CHANNELS = os.environ.get("CHANNEL_IDS") or os.environ.get("CHANNEL_ID", "")
CHANNEL_IDS = [x.strip() for x in RAW_CHANNELS.split(",") if x.strip()]

app = Flask(__name__)

loop = asyncio.new_event_loop()

def start_loop():
    asyncio.set_event_loop(loop)
    loop.run_forever()

Thread(target=start_loop, daemon=True).start()

# usa la tua sessione utente
client = TelegramClient("sbogia.session", API_ID, API_HASH, loop=loop)

def parse_channel_id(channel):
    try:
        return int(channel)
    except ValueError:
        return channel

async def test_channels():
    print("=== TEST CANALI CON SBOGIA.SESSION ===")
    if not client.is_connected():
        await client.connect()

    me = await client.get_entity("me")
    print("Loggato come:", me.id, getattr(me, "username", None), getattr(me, "first_name", None))

    result = []

    for raw_channel in CHANNEL_IDS:
        try:
            entity = await client.get_entity(parse_channel_id(raw_channel))
            print(f"Canale trovato: {raw_channel} -> {getattr(entity, 'title', None)}")

            titles = []
            async for message in client.iter_messages(entity, limit=5):
                if message.audio or (message.document and message.document.mime_type and message.document.mime_type.startswith("audio/")):
                    t = getattr(message, "message", "") or "audio"
                    titles.append(t)

            print(f"Brani audio nei primi 5 messaggi del canale {raw_channel}: {len(titles)}")

            result.append({
                "channel": raw_channel,
                "title": getattr(entity, "title", None),
                "audio_messages_found": len(titles)
            })

        except Exception as e:
            print(f"ERRORE CANALE {raw_channel}: {repr(e)}")
            result.append({
                "channel": raw_channel,
                "error": repr(e)
            })

    print("=== FINE TEST CANALI ===")
    return result

@app.route("/api/debug")
def debug():
    future = asyncio.run_coroutine_threadsafe(test_channels(), loop)
    try:
        data = future.result(timeout=60)
        return jsonify({
            "status": "online",
            "channels": data
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "details": repr(e)
        }), 500

@app.route("/")
def home():
    return jsonify({"msg": "Test SboGiA session attivo. Vai su /api/debug."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
