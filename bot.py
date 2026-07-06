import os
import asyncio
import discord

TOKEN = os.getenv("DISCORD_TOKEN")
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID"))

intents = discord.Intents.default()
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Eingeloggt als {client.user}")

    channel = client.get_channel(VOICE_CHANNEL_ID)

    if channel is None:
        print("Voice-Channel nicht gefunden.")
        return

    while True:
        try:
            if not client.voice_clients:
                await channel.connect()
                print(f"Verbunden mit: {channel.name}")

            await asyncio.sleep(60)

        except Exception as e:
            print(f"Fehler: {e}")
            await asyncio.sleep(10)

client.run(TOKEN)
