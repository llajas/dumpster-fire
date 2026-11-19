"""Environment configuration, validated before acquiring device access."""

from pathlib import Path
from typing import Annotated, ClassVar

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """AUSTIN_FIRE_* environment variables; API key is the ESPHome Noise PSK."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="AUSTIN_FIRE_", frozen=True, hide_input_in_errors=True
    )
    host: Annotated[str, Field(min_length=1)]
    api_key: Annotated[SecretStr, Field(min_length=1)]
    state_path: Path = Path("/data/austin_dumpster_fire_state.json")
    timeout_minutes: Annotated[int, Field(ge=1, le=240)] = 15
    enabled: bool = True
    io_timeout_seconds: Annotated[float, Field(gt=0, le=120)] = 20.0
    flame_object_id: str | None = None
    trigger_object_id: str | None = None
    feed_url: str = "https://data.austintexas.gov/resource/wpu4-x69d.json"
