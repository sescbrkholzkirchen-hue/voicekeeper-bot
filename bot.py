import os
import asyncio
import discord

TOKEN = os.getenv("DISCORD_TOKEN")
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID"))

intents = discord.Intents.default()
client = discord.Client(intents=intents)

voice_client = None

@client.event
async def on_ready():
    global voice_client
    print(f"Eingeloggt als {client.user}")

    while True:
        try:
            channel = client.get_channel(VOICE_CHANNEL_ID)

            if channel is None:
                print("Voice-Channel nicht gefunden.")
            elif voice_client is None or not voice_client.is_connected():
                voice_client = await channel.connect()
                print(f"Verbunden mit: {channel.name}")
            else:
                print("Bot ist weiterhin verbunden.")

            await asyncio.sleep(300)

        except Exception as e:
            print(f"Fehler: {e}")
            await asyncio.sleep(30)

client.run(TOKEN)
