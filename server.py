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

# sessione utente (col tuo numero, sbogia.session)
client = TelegramClient("sbogia.session", API_ID, API_HASH, loop=loop)

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
        try:
