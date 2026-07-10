import asyncio
import logging
import os
import sys

import discord


# Railway-Logs übersichtlich ausgeben
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

logger = logging.getLogger("voicekeeper")


# Umgebungsvariablen prüfen
TOKEN = os.getenv("DISCORD_TOKEN")
VOICE_CHANNEL_ID_RAW = os.getenv("VOICE_CHANNEL_ID")

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN fehlt. Bitte die Variable in Railway eintragen."
    )

if not VOICE_CHANNEL_ID_RAW:
    raise RuntimeError(
        "VOICE_CHANNEL_ID fehlt. Bitte die Variable in Railway eintragen."
    )

try:
    VOICE_CHANNEL_ID = int(VOICE_CHANNEL_ID_RAW)
except ValueError as error:
    raise RuntimeError(
        "VOICE_CHANNEL_ID muss ausschließlich aus Zahlen bestehen."
    ) from error


intents = discord.Intents.default()
client = discord.Client(intents=intents)

connection_task: asyncio.Task | None = None


async def get_voice_channel() -> discord.VoiceChannel:
    """Lädt den gewünschten Sprachkanal aus Discord."""

    channel = client.get_channel(VOICE_CHANNEL_ID)

    if channel is None:
        try:
            channel = await client.fetch_channel(VOICE_CHANNEL_ID)
        except discord.NotFound as error:
            raise RuntimeError(
                f"Der Kanal mit der ID {VOICE_CHANNEL_ID} wurde nicht gefunden."
            ) from error
        except discord.Forbidden as error:
            raise RuntimeError(
                "Der Bot darf den Sprachkanal nicht sehen."
            ) from error

    if not isinstance(channel, discord.VoiceChannel):
        raise RuntimeError(
            f"Der Kanal mit der ID {VOICE_CHANNEL_ID} ist kein Sprachkanal."
        )

    return channel


async def disconnect_broken_clients() -> None:
    """Entfernt alte oder nicht mehr verbundene Voice-Clients."""

    for voice_client in list(client.voice_clients):
        if not voice_client.is_connected():
            try:
                await voice_client.disconnect(force=True)
            except Exception:
                logger.exception(
                    "Ein alter Voice-Client konnte nicht bereinigt werden."
                )


async def maintain_voice_connection() -> None:
    """Prüft dauerhaft, ob der Bot im richtigen Sprachkanal verbunden ist."""

    await client.wait_until_ready()

    while not client.is_closed():
        try:
            channel = await get_voice_channel()
            await disconnect_broken_clients()

            voice_client = discord.utils.get(
                client.voice_clients,
                guild=channel.guild,
            )

            if voice_client and voice_client.is_connected():
                if voice_client.channel.id != channel.id:
                    logger.warning(
                        "Bot befindet sich im falschen Sprachkanal. "
                        "Er wird verschoben."
                    )
                    await voice_client.move_to(channel)
                else:
                    logger.info(
                        "Verbindung aktiv: %s | Latenz: %.0f ms",
                        channel.name,
                        voice_client.average_latency * 1000,
                    )
            else:
                logger.warning(
                    "Keine Voice-Verbindung vorhanden. Verbinde neu mit %s.",
                    channel.name,
                )

                await channel.connect(
                    reconnect=True,
                    timeout=30.0,
                    self_deaf=True,
                    self_mute=True,
                )

                logger.info(
                    "Erfolgreich mit %s verbunden.",
                    channel.name,
                )

            # Alle zwei Minuten prüfen
            await asyncio.sleep(120)

        except asyncio.CancelledError:
            raise

        except discord.Forbidden:
            logger.exception(
                "Dem Bot fehlen Rechte. Benötigt werden mindestens "
                "'Kanal ansehen' und 'Verbinden'."
            )
            await asyncio.sleep(60)

        except discord.ClientException:
            logger.exception(
                "Discord meldet einen Voice-Verbindungsfehler. "
                "Neuer Versuch in 30 Sekunden."
            )
            await asyncio.sleep(30)

        except Exception:
            logger.exception(
                "Unerwarteter Fehler. Neuer Versuch in 30 Sekunden."
            )
            await asyncio.sleep(30)


@client.event
async def on_ready() -> None:
    global connection_task

    logger.info(
        "Eingeloggt als %s | Bot-ID: %s",
        client.user,
        client.user.id if client.user else "unbekannt",
    )

    # on_ready kann nach einem Gateway-Reconnect erneut ausgelöst werden.
    # Deshalb darf die Überwachungsaufgabe nur einmal gestartet werden.
    if connection_task is None or connection_task.done():
        connection_task = asyncio.create_task(
            maintain_voice_connection(),
            name="voice-connection-monitor",
        )
        logger.info("Voice-Verbindungsüberwachung gestartet.")


@client.event
async def on_disconnect() -> None:
    logger.warning("Discord-Gateway-Verbindung wurde unterbrochen.")


@client.event
async def on_resumed() -> None:
    logger.info("Discord-Gateway-Sitzung wurde erfolgreich fortgesetzt.")


try:
    client.run(
        TOKEN,
        reconnect=True,
        log_handler=None,
    )
except discord.LoginFailure:
    logger.critical(
        "Der Discord-Token ist ungültig. Bitte DISCORD_TOKEN in Railway prüfen."
    )
    raise
