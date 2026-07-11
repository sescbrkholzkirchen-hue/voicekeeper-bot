import asyncio
import logging
import sys

import discord

from audio_manager import AudioManager
from config import Config
from voice_manager import VoiceManager


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

logger = logging.getLogger("voicekeeper")
config = Config.from_environment()

intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True

client = discord.Client(intents=intents)
voice_manager = VoiceManager(client, config)
audio_manager = AudioManager(client, config, voice_manager)

voice_monitor_task: asyncio.Task | None = None
audio_worker_task: asyncio.Task | None = None
last_join_times: dict[int, float] = {}


@client.event
async def on_ready() -> None:
    global voice_monitor_task, audio_worker_task

    logger.info(
        "Eingeloggt als %s | Bot-ID: %s",
        client.user,
        client.user.id if client.user else "unbekannt",
    )

    if voice_monitor_task is None or voice_monitor_task.done():
        voice_monitor_task = asyncio.create_task(
            voice_manager.monitor(),
            name="voice-monitor",
        )
        logger.info("Voice-Überwachung gestartet.")

    if audio_worker_task is None or audio_worker_task.done():
        audio_worker_task = asyncio.create_task(
            audio_manager.worker(),
            name="audio-worker",
        )
        logger.info("Sound-Warteschlange gestartet.")


@client.event
async def on_voice_state_update(
    member: discord.Member,
    before: discord.VoiceState,
    after: discord.VoiceState,
) -> None:
    if member.bot:
        return

    joined_target = (
        after.channel is not None
        and after.channel.id == config.voice_channel_id
        and (
            before.channel is None
            or before.channel.id != config.voice_channel_id
        )
    )

    if not joined_target:
        return

    now = asyncio.get_running_loop().time()
    last_join = last_join_times.get(member.id, 0.0)

    if now - last_join < config.join_cooldown_seconds:
        logger.info(
            "Sound für %s wegen Cooldown übersprungen.",
            member.display_name,
        )
        return

    last_join_times[member.id] = now

    logger.info(
        "%s ist dem Sprachkanal %s beigetreten.",
        member.display_name,
        after.channel.name,
    )
    await audio_manager.enqueue(member.display_name)


@client.event
async def on_disconnect() -> None:
    logger.warning("Discord-Gateway-Verbindung wurde unterbrochen.")


@client.event
async def on_resumed() -> None:
    logger.info("Discord-Gateway-Sitzung wurde fortgesetzt.")


try:
    client.run(
        config.token,
        reconnect=True,
        log_handler=None,
    )
except discord.LoginFailure:
    logger.critical(
        "DISCORD_TOKEN ist ungültig. Prüfe die Variable in Railway."
    )
    raise
