import json
import os
import socket
import urllib.parse

import psycopg2
import psycopg2.extras

from config import Config


class Database:
    """Simple JSON-backed PostgreSQL persistence for app state."""

    def __init__(self):
        raw_url = os.getenv("DATABASE_URL") or Config.DATABASE_URL
        if isinstance(raw_url, str):
            raw_url = raw_url.strip()
            if raw_url.startswith("DATABASE_URL="):
                raw_url = raw_url.split("=", 1)[1].strip()
            if raw_url.startswith("postgresql://"):
                raw_url = f"postgres://{raw_url[len('postgresql://'):]}"
        self.url = raw_url
        self.enabled = bool(self.url)
        self.conn = None

        if self.enabled:
            self.conn = self._connect(self.url)
            self.conn.autocommit = True
            self._ensure_tables()

    def _connect(self, url):
        try:
            return psycopg2.connect(url, sslmode="require")
        except psycopg2.OperationalError as exc:
            message = str(exc)
            if "Network is unreachable" not in message:
                raise

            parsed = urllib.parse.urlparse(url)
            host = parsed.hostname
            port = parsed.port or 5432
            dbname = parsed.path.lstrip("/") or "postgres"
            user = urllib.parse.unquote(parsed.username) if parsed.username else None
            password = urllib.parse.unquote(parsed.password) if parsed.password else None

            if not host:
                raise

            addrs = socket.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_STREAM)
            if not addrs:
                raise

            hostaddr = addrs[0][4][0]
            return psycopg2.connect(
                host=host,
                hostaddr=hostaddr,
                port=port,
                dbname=dbname,
                user=user,
                password=password,
                sslmode="require",
            )

    def _ensure_tables(self):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS app_data (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL
                );
                """
            )

    def load_json(self, key, default=None):
        if default is None:
            default = {}
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute("SELECT value FROM app_data WHERE key = %s", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def save_json(self, key, value):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO app_data (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, psycopg2.extras.Json(value)),
            )
