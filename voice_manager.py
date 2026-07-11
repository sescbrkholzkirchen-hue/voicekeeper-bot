import asyncio
import logging

import discord

from config import Config


logger = logging.getLogger("voicekeeper.voice")


class VoiceManager:
    def __init__(self, client: discord.Client, config: Config) -> None:
        self.client = client
        self.config = config
        self._connect_lock = asyncio.Lock()

    async def get_target_channel(self) -> discord.VoiceChannel:
        channel = self.client.get_channel(self.config.voice_channel_id)

        if channel is None:
            channel = await self.client.fetch_channel(
                self.config.voice_channel_id
            )

        if not isinstance(channel, discord.VoiceChannel):
            raise RuntimeError(
                "VOICE_CHANNEL_ID zeigt nicht auf einen normalen Sprachkanal."
            )

        return channel

    async def get_voice_client(
        self,
        channel: discord.VoiceChannel,
    ) -> discord.VoiceClient | None:
        return discord.utils.get(
            self.client.voice_clients,
            guild=channel.guild,
        )

    async def remove_broken_client(
        self,
        voice_client: discord.VoiceClient,
    ) -> None:
        logger.warning("Ungültige Voice-Sitzung wird entfernt.")

        try:
            if voice_client.is_playing() or voice_client.is_paused():
                voice_client.stop()
        except Exception:
            logger.exception("Wiedergabe konnte nicht gestoppt werden.")

        try:
            await voice_client.disconnect(force=True)
        except Exception:
            logger.exception("Voice-Client konnte nicht getrennt werden.")

        try:
            voice_client.cleanup()
        except Exception:
            logger.exception("Voice-Client konnte nicht bereinigt werden.")

        await asyncio.sleep(2)

    async def ensure_connected(self) -> discord.VoiceClient:
        async with self._connect_lock:
            channel = await self.get_target_channel()
            voice_client = await self.get_voice_client(channel)

            if voice_client and voice_client.is_connected():
                if voice_client.channel and voice_client.channel.id != channel.id:
                    logger.warning(
                        "Bot ist im falschen Kanal und wird nach %s verschoben.",
                        channel.name,
                    )
                    await voice_client.move_to(channel)
                return voice_client

            if voice_client is not None:
                await self.remove_broken_client(voice_client)

            logger.warning("Verbinde mit Sprachkanal %s.", channel.name)

            voice_client = await channel.connect(
                timeout=45.0,
                reconnect=False,
                self_deaf=True,
                self_mute=False,
            )

            logger.info("Erfolgreich mit %s verbunden.", channel.name)
            return voice_client

    async def monitor(self) -> None:
        await self.client.wait_until_ready()

        while not self.client.is_closed():
            try:
                voice_client = await self.ensure_connected()
                channel_name = (
                    voice_client.channel.name
                    if voice_client.channel is not None
                    else "unbekannt"
                )
                logger.info(
                    "Verbindung aktiv: %s | Voice-Latenz: %.0f ms",
                    channel_name,
                    voice_client.average_latency * 1000,
                )
                await asyncio.sleep(self.config.connection_check_seconds)

            except asyncio.CancelledError:
                raise
            except discord.Forbidden:
                logger.exception(
                    "Dem Bot fehlen Rechte: Kanal ansehen, Verbinden oder Sprechen."
                )
                await asyncio.sleep(30)
            except (discord.ClientException, asyncio.TimeoutError):
                logger.exception(
                    "Voice-Verbindung fehlgeschlagen. Neuer Versuch in 15 Sekunden."
                )
                await asyncio.sleep(15)
            except Exception:
                logger.exception(
                    "Unerwarteter Voice-Fehler. Neuer Versuch in 15 Sekunden."
                )
                await asyncio.sleep(15)
