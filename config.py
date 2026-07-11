from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Config:
    token: str
    voice_channel_id: int
    welcome_audio: Path
    welcome_volume: float
    join_cooldown_seconds: int
    connection_check_seconds: int

    @classmethod
    def from_environment(cls) -> "Config":
        token = os.getenv("DISCORD_TOKEN", "").strip()
        channel_id_text = os.getenv("VOICE_CHANNEL_ID", "").strip()

        if not token:
            raise RuntimeError("DISCORD_TOKEN fehlt in Railway.")

        if not channel_id_text:
            raise RuntimeError("VOICE_CHANNEL_ID fehlt in Railway.")

        try:
            channel_id = int(channel_id_text)
        except ValueError as error:
            raise RuntimeError(
                "VOICE_CHANNEL_ID darf nur aus Zahlen bestehen."
            ) from error

        try:
            volume = float(os.getenv("WELCOME_VOLUME", "0.5"))
        except ValueError:
            volume = 0.5
        volume = max(0.0, min(volume, 2.0))

        try:
            cooldown = int(os.getenv("JOIN_COOLDOWN_SECONDS", "10"))
        except ValueError:
            cooldown = 10
        cooldown = max(0, cooldown)

        try:
            check_seconds = int(os.getenv("CONNECTION_CHECK_SECONDS", "30"))
        except ValueError:
            check_seconds = 30
        check_seconds = max(10, check_seconds)

        return cls(
            token=token,
            voice_channel_id=channel_id,
            welcome_audio=Path(
                os.getenv("WELCOME_AUDIO", "welcome.mp3").strip()
                or "welcome.mp3"
            ),
            welcome_volume=volume,
            join_cooldown_seconds=cooldown,
            connection_check_seconds=check_seconds,
        )
