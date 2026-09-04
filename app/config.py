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

Phase 6: `cors_origins` added - same class, extended, not replaced (the
whole payoff of building this as a proper `BaseSettings` from the start).
`list[str]` fields are parsed from an env var as a JSON-encoded string by
default (see the Pydantic Settings docs linked above,
"Parsing environment variable values") - not comma-separated - so
`.env`/`.env.example` write it as `CORS_ORIGINS=["http://localhost:5173"]`.
No custom comma-splitting validator is added for this: this project has no
demonstrated need for a friendlier local format yet, and the JSON syntax is
what the library gives you for free. Defaults to an empty list - no
frontend exists for this project yet, so there's nothing to trust by
default; an empty allowlist is a safe, honest starting point that has to
be deliberately opened up once a real frontend origin exists, rather than
guessing at one now.

Phase 6: `log_level` added the same way - see logging_config.py for where
it's actually used. `"INFO"` by default: normal request/business-event
lines, not the noisier `"DEBUG"` a real investigation might turn on
temporarily via `.env` without a code change.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    cors_origins: list[str] = []
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
