"""depot — a thin, transparent launcher over `docker compose` for the shared support services.

It wraps compose profiles for an easy menu, but never hides them: every command it runs is echoed, and
raw `docker compose --profile … up/ps/logs` works identically. See `depot.cli`.
"""
