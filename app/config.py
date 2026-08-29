"""
Phase 3: App settings, loaded from environment variables (via .env locally).

The standard `pydantic-settings` pattern (see
[Pydantic's Settings Management docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)):
pull secrets out of source code entirely. `pydantic-settings` was already
sitting unused in requirements.txt since Phase 0 - this is where it actually
earns its place. `BaseSettings` behaves like a regular Pydantic model (same
validation, same type coercion) except its values come from the
environment/`.env` file instead of a request body.

Only JWT settings so far - DATABASE_URL stays hardcoded in database.py for
now rather than moving everything into this class at once.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
