import asyncio
import logging
import os
import sys

import discord


# --------------------------------------------------
# Logging für Railway
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

logger = logging.getLogger("voicekeeper")


# --------------------------------------------------
# Railway-Variablen prüfen
# --------------------------------------------------

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
        "VOICE_CHANNEL_ID darf nur aus Zahlen bestehen."
    ) from error


# --------------------------------------------------
# Discord-Client
# --------------------------------------------------

intents = discord.Intents.default()
client = discord.Client(intents=intents)

connection_task: asyncio.Task | None = None


async def get_voice_channel() -> discord.VoiceChannel:
    """
    Sucht den gewünschten Sprachkanal.
    Falls er nicht im Cache ist, wird er direkt von Discord geladen.
    """

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

        except discord.HTTPException as error:
            raise RuntimeError(
                "Der Sprachkanal konnte nicht von Discord geladen werden."
            ) from error

    if not isinstance(channel, discord.VoiceChannel):
        raise RuntimeError(
            f"Der Kanal mit der ID {VOICE_CHANNEL_ID} ist kein Sprachkanal."
        )

    return channel


async def remove_broken_voice_client(
    voice_client: discord.VoiceClient,
) -> None:
    """
    Entfernt eine alte oder ungültige Voice-Sitzung vollständig.
    Das hilft insbesondere nach Discord-Fehlern wie WebSocket 4006.
    """

    logger.warning(
        "Alte oder ungültige Voice-Sitzung wird entfernt."
    )

    try:
        await voice_client.disconnect(force=True)
    except Exception:
        logger.exception(
            "Die alte Voice-Verbindung konnte nicht sauber getrennt werden."
        )

    try:
        voice_client.cleanup()
    except Exception:
        logger.exception(
            "Die alte Voice-Verbindung konnte nicht vollständig bereinigt werden."
        )

    # Discord kurz Zeit geben, die alte Sitzung zu verwerfen
    await asyncio.sleep(3)


async def maintain_voice_connection() -> None:
    """
    Überwacht dauerhaft, ob der Bot im richtigen Sprachkanal verbunden ist.
    """

    await client.wait_until_ready()

    while not client.is_closed():
        try:
            channel = await get_voice_channel()

            voice_client = discord.utils.get(
                client.voice_clients,
                guild=channel.guild,
            )

            # Bot ist verbunden
            if voice_client is not None and voice_client.is_connected():
                if voice_client.channel is None:
                    logger.warning(
                        "Voice-Client ist verbunden, hat aber keinen Kanal."
                    )
                    await remove_broken_voice_client(voice_client)

                elif voice_client.channel.id != channel.id:
                    logger.warning(
                        "Bot befindet sich im falschen Sprachkanal. "
                        "Er wird nach %s verschoben.",
                        channel.name,
                    )

                    await voice_client.move_to(channel)

                    logger.info(
                        "Bot wurde erfolgreich nach %s verschoben.",
                        channel.name,
                    )

                else:
                    logger.info(
                        "Verbindung aktiv: %s | Voice-Latenz: %.0f ms",
                        channel.name,
                        voice_client.average_latency * 1000,
                    )

            # Voice-Client vorhanden, aber nicht verbunden
            elif voice_client is not None:
                await remove_broken_voice_client(voice_client)

                logger.warning(
                    "Defekte Voice-Sitzung wurde entfernt. "
                    "Neue Verbindung zu %s wird aufgebaut.",
                    channel.name,
                )

                await channel.connect(
                    timeout=30.0,
                    reconnect=True,
                    self_deaf=True,
                    self_mute=True,
                )

                logger.info(
                    "Erfolgreich neu mit %s verbunden.",
                    channel.name,
                )

            # Noch gar kein Voice-Client vorhanden
            else:
                logger.warning(
                    "Keine Voice-Verbindung vorhanden. "
                    "Verbinde mit %s.",
                    channel.name,
                )

                await channel.connect(
                    timeout=30.0,
                    reconnect=True,
                    self_deaf=True,
                    self_mute=True,
                )

                logger.info(
                    "Erfolgreich mit %s verbunden.",
                    channel.name,
                )

            # Verbindung alle 60 Sekunden kontrollieren
            await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("Voice-Überwachung wurde beendet.")
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
                "Neuer Versuch in 15 Sekunden."
            )
            await asyncio.sleep(15)

        except asyncio.TimeoutError:
            logger.exception(
                "Der Aufbau der Voice-Verbindung hat zu lange gedauert. "
                "Neuer Versuch in 15 Sekunden."
            )
            await asyncio.sleep(15)

        except Exception:
            logger.exception(
                "Unerwarteter Fehler in der Voice-Überwachung. "
                "Neuer Versuch in 15 Sekunden."
            )
            await asyncio.sleep(15)


@client.event
async def on_ready() -> None:
    global connection_task

    logger.info(
        "Eingeloggt als %s | Bot-ID: %s",
        client.user,
        client.user.id if client.user else "unbekannt",
    )

    # on_ready kann nach einem Reconnect mehrfach ausgelöst werden.
    # Deshalb darf die Überwachung nur einmal laufen.
    if connection_task is None or connection_task.done():
        connection_task = asyncio.create_task(
            maintain_voice_connection(),
            name="voice-connection-monitor",
        )

        logger.info(
            "Voice-Verbindungsüberwachung gestartet."
        )
    else:
        logger.info(
            "Voice-Verbindungsüberwachung läuft bereits."
        )


@client.event
async def on_disconnect() -> None:
    logger.warning(
        "Discord-Gateway-Verbindung wurde unterbrochen."
    )


@client.event
async def on_resumed() -> None:
    logger.info(
        "Discord-Gateway-Sitzung wurde erfolgreich fortgesetzt."
    )


# --------------------------------------------------
# Bot starten
# --------------------------------------------------

try:
    client.run(
        TOKEN,
        reconnect=True,
        log_handler=None,
    )

except discord.LoginFailure:
    logger.critical(
        "Der Discord-Token ist ungültig. "
        "Bitte DISCORD_TOKEN in Railway überprüfen."
    )
    raise
