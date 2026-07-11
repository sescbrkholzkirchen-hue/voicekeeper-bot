import asyncio
import logging

import discord

from config import Config
from voice_manager import VoiceManager


logger = logging.getLogger("voicekeeper.audio")


class AudioManager:
    def __init__(
        self,
        client: discord.Client,
        config: Config,
        voice_manager: VoiceManager,
    ) -> None:
        self.client = client
        self.config = config
        self.voice_manager = voice_manager
        self.queue: asyncio.Queue[str] = asyncio.Queue()

    async def enqueue(self, member_name: str) -> None:
        await self.queue.put(member_name)
        logger.info(
            "Sound für %s wurde eingereiht. Warteschlange: %s",
            member_name,
            self.queue.qsize(),
        )

    async def play_once(
        self,
        voice_client: discord.VoiceClient,
        member_name: str,
    ) -> None:
        if not self.config.welcome_audio.is_file():
            raise FileNotFoundError(
                f"Audiodatei nicht gefunden: {self.config.welcome_audio}"
            )

        while voice_client.is_playing() or voice_client.is_paused():
            await asyncio.sleep(0.2)

        loop = asyncio.get_running_loop()
        finished = asyncio.Event()
        playback_error: Exception | None = None

        def after_playback(error: Exception | None) -> None:
            nonlocal playback_error
            playback_error = error
            loop.call_soon_threadsafe(finished.set)

        ffmpeg_source = discord.FFmpegPCMAudio(
            str(self.config.welcome_audio),
            options="-vn",
        )
        source = discord.PCMVolumeTransformer(
            ffmpeg_source,
            volume=self.config.welcome_volume,
        )

        logger.info("Begrüßungssound für %s wird abgespielt.", member_name)
        voice_client.play(source, after=after_playback)

        try:
            await asyncio.wait_for(finished.wait(), timeout=600)
        except asyncio.TimeoutError:
            voice_client.stop()
            raise RuntimeError(
                "Die Audiowiedergabe dauerte länger als zehn Minuten."
            )

        if playback_error:
            raise playback_error

        logger.info(
            "Begrüßungssound für %s wurde vollständig abgespielt.",
            member_name,
        )

    async def worker(self) -> None:
        await self.client.wait_until_ready()

        while not self.client.is_closed():
            member_name = await self.queue.get()

            try:
                voice_client = await self.voice_manager.ensure_connected()
                await self.play_once(voice_client, member_name)

            except asyncio.CancelledError:
                raise
            except FileNotFoundError:
                logger.exception(
                    "Sounddatei fehlt. Prüfe WELCOME_AUDIO und GitHub."
                )
                await asyncio.sleep(5)
            except Exception:
                logger.exception(
                    "Sound für %s konnte nicht abgespielt werden.",
                    member_name,
                )
                await asyncio.sleep(2)
            finally:
                self.queue.task_done()
