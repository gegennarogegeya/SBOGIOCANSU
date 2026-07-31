import os
import asyncio
from threading import Thread, Lock
from flask import Flask, jsonify, render_template, Response
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
TG_STRING_SESSION = os.environ.get("TG_STRING_SESSION", "")

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

client = TelegramClient(
    StringSession(TG_STRING_SESSION),
    API_ID,
    API_HASH,
    loop=loop
)

def parse_channel_id(channel):
    try:
        return int(channel)
    except ValueError:
        return channel

async def ensure_connected():
    if not client.is_connected():
        await client.connect()

async def load_tracks():
    await ensure_connected()
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
                        title = attr.tit
