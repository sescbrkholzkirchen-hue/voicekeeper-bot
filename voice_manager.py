import asyncio
import logging
import math

import discord

from config import Config


logger = logging.getLogger("voicekeeper.voice")


class VoiceManager:
    def __init__(
        self,
        client: discord.Client,
        config: Config,
    ) -> None:
        self.client = client
        self.config = config

        # Verhindert, dass mehrere Funktionen gleichzeitig
        # eine neue Voice-Verbindung aufbauen.
        self._connect_lock = asyncio.Lock()

    async def get_target_channel(
        self,
    ) -> discord.VoiceChannel:
        """
        Sucht den Sprachkanal, dessen ID in Railway
        unter VOICE_CHANNEL_ID eingetragen ist.
        """

        channel = self.client.get_channel(
            self.config.voice_channel_id
        )

        if channel is None:
            try:
                channel = await self.client.fetch_channel(
                    self.config.voice_channel_id
                )

            except discord.NotFound as error:
                raise RuntimeError(
                    "Der eingestellte Sprachkanal wurde nicht gefunden."
                ) from error

            except discord.Forbidden as error:
                raise RuntimeError(
                    "Der Bot darf den eingestellten Kanal nicht sehen."
                ) from error

            except discord.HTTPException as error:
                raise RuntimeError(
                    "Der Sprachkanal konnte nicht von Discord geladen werden."
                ) from error

        if not isinstance(
            channel,
            discord.VoiceChannel,
        ):
            raise RuntimeError(
                "VOICE_CHANNEL_ID zeigt nicht auf "
                "einen normalen Sprachkanal."
            )

        return channel

    async def get_voice_client(
        self,
        channel: discord.VoiceChannel,
    ) -> discord.VoiceClient | None:
        """
        Sucht den vorhandenen Voice-Client
        für den Discord-Server.
        """

        return discord.utils.get(
            self.client.voice_clients,
            guild=channel.guild,
        )

    async def remove_broken_client(
        self,
        voice_client: discord.VoiceClient,
    ) -> None:
        """
        Beendet eine beschädigte oder nicht mehr
        verbundene Voice-Sitzung.

        cleanup() wird nicht zusätzlich manuell aufgerufen,
        da disconnect(force=True) die Verbindung und
        die interne Bereinigung übernehmen soll.
        """

        logger.warning(
            "Ungültige Voice-Sitzung wird sauber getrennt."
        )

        try:
            if (
                voice_client.is_playing()
                or voice_client.is_paused()
            ):
                voice_client.stop()

        except Exception:
            logger.exception(
                "Eine laufende Wiedergabe konnte "
                "nicht gestoppt werden."
            )

        try:
            await voice_client.disconnect(
                force=True
            )

        except Exception:
            logger.exception(
                "Voice-Client konnte nicht "
                "sauber getrennt werden."
            )

        # Discord und discord.py bekommen etwas Zeit,
        # um alte WebSocket-Aufgaben zu beenden.
        await asyncio.sleep(5)

    async def connect_new(
        self,
        channel: discord.VoiceChannel,
    ) -> discord.VoiceClient:
        """
        Baut eine vollständig neue Voice-Verbindung auf.
        """

        logger.warning(
            "Verbinde mit Sprachkanal %s.",
            channel.name,
        )

        voice_client = await channel.connect(
            timeout=45.0,

            # Wir verwenden unseren eigenen Monitor.
            # Dadurch soll discord.py nicht gleichzeitig
            # einen zweiten Reconnect durchführen.
            reconnect=False,

            # Der Bot empfängt kein Audio.
            self_deaf=True,

            # Der Bot darf den Begrüßungssound senden.
            self_mute=False,
        )

        logger.info(
            "Erfolgreich mit %s verbunden.",
            channel.name,
        )

        return voice_client

    async def ensure_connected(
        self,
    ) -> discord.VoiceClient:
        """
        Prüft die Verbindung und stellt sicher,
        dass genau eine gültige Voice-Sitzung besteht.
        """

        async with self._connect_lock:
            channel = await self.get_target_channel()

            voice_client = await self.get_voice_client(
                channel
            )

            # Eine gültige Verbindung ist vorhanden.
            if (
                voice_client is not None
                and voice_client.is_connected()
            ):
                # Der Bot befindet sich versehentlich
                # in einem anderen Sprachkanal.
                if (
                    voice_client.channel is not None
                    and voice_client.channel.id
                    != channel.id
                ):
                    logger.warning(
                        "Bot befindet sich im falschen Kanal. "
                        "Er wird nach %s verschoben.",
                        channel.name,
                    )

                    await voice_client.move_to(
                        channel
                    )

                    logger.info(
                        "Bot wurde erfolgreich nach %s verschoben.",
                        channel.name,
                    )

                return voice_client

            # Ein Voice-Client existiert noch,
            # ist aber nicht mehr richtig verbunden.
            if voice_client is not None:
                await self.remove_broken_client(
                    voice_client
                )

            # Eine neue Verbindung aufbauen.
            return await self.connect_new(
                channel
            )

    async def monitor(
        self,
    ) -> None:
        """
        Prüft regelmäßig, ob der Bot noch
        im gewünschten Sprachkanal verbunden ist.
        """

        await self.client.wait_until_ready()

        while not self.client.is_closed():
            try:
                voice_client = (
                    await self.ensure_connected()
                )

                channel_name = (
                    voice_client.channel.name
                    if voice_client.channel is not None
                    else "unbekannt"
                )

                latency_ms = (
                    voice_client.average_latency
                    * 1000
                )

                # Direkt nach dem Verbinden kann discord.py
                # noch keine Latenz berechnet haben.
                if math.isinf(latency_ms):
                    logger.info(
                        "Verbindung aktiv: %s | "
                        "Latenz wird noch gemessen.",
                        channel_name,
                    )
                else:
                    logger.info(
                        "Verbindung aktiv: %s | "
                        "Voice-Latenz: %.0f ms",
                        channel_name,
                        latency_ms,
                    )

                await asyncio.sleep(
                    self.config.connection_check_seconds
                )

            except asyncio.CancelledError:
                logger.info(
                    "Voice-Überwachung wurde beendet."
                )
                raise

            except discord.Forbidden:
                logger.exception(
                    "Dem Bot fehlen Discord-Rechte. "
                    "Benötigt werden: Kanal ansehen, "
                    "Verbinden und Sprechen."
                )

                await asyncio.sleep(30)

            except asyncio.TimeoutError:
                logger.exception(
                    "Der Aufbau der Voice-Verbindung "
                    "hat zu lange gedauert. "
                    "Neuer Versuch in 15 Sekunden."
                )

                await asyncio.sleep(15)

            except discord.ClientException:
                logger.exception(
                    "Discord meldet einen "
                    "Voice-Verbindungsfehler. "
                    "Neuer Versuch in 15 Sekunden."
                )

                await asyncio.sleep(15)

            except discord.HTTPException:
                logger.exception(
                    "Discord konnte die Voice-Anfrage "
                    "nicht verarbeiten. "
                    "Neuer Versuch in 15 Sekunden."
                )

                await asyncio.sleep(15)

            except Exception:
                logger.exception(
                    "Unerwarteter Fehler in der "
                    "Voice-Überwachung. "
                    "Neuer Versuch in 15 Sekunden."
                )

                await asyncio.sleep(15)
