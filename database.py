
import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from datetime import datetime
import threading
import time
import logging

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATABASE CONFIG  (edit only this block on your server)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DB_CONFIG = {
    "host": "localhost",
    "database": "telegram_bot",
    "user": "postgres",
    "password": "jigu7878",   # password you set during installation
    "port": 5432
}
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONNECTION POOL
# One shared pool (5–50 conns) replaces per-call open/close.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_pool: psycopg2.pool.ThreadedConnectionPool = None
_pool_lock = threading.Lock()


def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            _pool = psycopg2.pool.ThreadedConnectionPool(5, 50, **DB_CONFIG)
            logging.info("[DB] Connection pool created (5-50 connections)")
    return _pool


def get_db_connection():
    """Get a connection from the pool."""
    return _get_pool().getconn()


def _release(conn):
    try:
        _get_pool().putconn(conn)
    except Exception as e:
        logging.warning(f"[DB] putconn error: {e}")


class PooledConn:
    """Context manager: borrow then return a pooled connection."""
    def __init__(self):
        self.conn = None

    def __enter__(self):
        self.conn = get_db_connection()
        return self.conn

    def __exit__(self, exc_type, *_):
        if self.conn:
            if exc_type:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            _release(self.conn)
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# IN-PROCESS TTL CACHES
# Cuts DB round-trips for hot read paths.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_gate_cache: dict = {}
_gate_cache_ttl = 30       # seconds — gate on/off rarely changes

_credits_cache: dict = {}
_credits_cache_ttl = 5     # short: credits change often

_premium_cache: dict = {}
_premium_cache_ttl = 60    # seconds — used by sub.py

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCHEMA INITIALIZATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def ensure_users_table():
    try:
        with PooledConn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    credits INTEGER DEFAULT 0,
                    cc_checked INTEGER DEFAULT 0,
                    cc_charged INTEGER DEFAULT 0,
                    joined_at TIMESTAMP
                )
            """)
            conn.commit()
        print("[DB] Users table checked.")
    except Exception as e:
        print(f"[DB] Error ensuring users table: {e}")


def ensure_stats_columns():
    try:
        with PooledConn() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS cc_checked INTEGER DEFAULT 0")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS cc_charged INTEGER DEFAULT 0")
            except Exception:
                pass
            conn.commit()
        print("[DB] Stats columns checked/created.")
    except Exception as e:
        print(f"[DB] Error checking stats columns: {e}")


def ensure_proxy_table():
    try:
        with PooledConn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS proxies (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    proxy TEXT NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        print("[DB] Proxies table checked/created.")
    except Exception as e:
        print(f"[DB] Error creating proxies table: {e}")


def ensure_gate_table():
    try:
        with PooledConn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gate_status (
                    gate TEXT PRIMARY KEY,
                    is_enabled BOOLEAN DEFAULT TRUE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        print("[DB] Gate status table checked.")
    except Exception as e:
        print(f"[DB] Error creating gate table: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# USER FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_user(user_id: int):
    with PooledConn() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        return cur.fetchone()


def create_user(user_id: int, username: str):
    with PooledConn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, username, credits, joined_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO NOTHING
        """, (user_id, username, 150, datetime.now()))
        conn.commit()


def get_user_credits(user_id: int) -> int:
    now = time.monotonic()
    cached = _credits_cache.get(user_id)
    if cached and now < cached[1]:
        return cached[0]
    with PooledConn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT credits FROM users WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        credits = result[0] if result else 0
    _credits_cache[user_id] = (credits, now + _credits_cache_ttl)
    return credits


def update_credits(user_id: int, new_credits: int):
    with PooledConn() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET credits = %s WHERE user_id = %s", (new_credits, user_id))
        conn.commit()
    _credits_cache[user_id] = (new_credits, time.monotonic() + _credits_cache_ttl)


def deduct_credits_atomic(user_id: int, amount: int) -> int:
    """
    Atomically deducts `amount` credits in one SQL round-trip (floor 0).
    Replaces the racy get_user_credits() + update_credits() pattern.
    Returns new balance.
    """
    with PooledConn() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE users
               SET credits = GREATEST(credits - %s, 0)
             WHERE user_id = %s
         RETURNING credits
        """, (amount, user_id))
        row = cur.fetchone()
        conn.commit()
        new_credits = row[0] if row else 0
    _credits_cache[user_id] = (new_credits, time.monotonic() + _credits_cache_ttl)
    return new_credits


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STATS FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def update_user_stats(user_id: int, is_charged: bool):
    """Single combined query instead of two separate ones."""
    with PooledConn() as conn:
        cur = conn.cursor()
        if is_charged:
            cur.execute("""
                UPDATE users
                   SET cc_checked = cc_checked + 1,
                       cc_charged = cc_charged + 1
                 WHERE user_id = %s
            """, (user_id,))
        else:
            cur.execute(
                "UPDATE users SET cc_checked = cc_checked + 1 WHERE user_id = %s",
                (user_id,)
            )
        conn.commit()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GATE FUNCTIONS  — cached
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def is_gate_enabled(gate: str) -> bool:
    now = time.monotonic()
    cached = _gate_cache.get(gate)
    if cached and now < cached[1]:
        return cached[0]

    with PooledConn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO gate_status (gate, is_enabled)
            VALUES (%s, TRUE)
            ON CONFLICT (gate) DO NOTHING
        """, (gate,))
        cur.execute("SELECT is_enabled FROM gate_status WHERE gate = %s", (gate,))
        row = cur.fetchone()
        conn.commit()
        status = bool(row[0]) if row else True

    _gate_cache[gate] = (status, now + _gate_cache_ttl)
    return status


def set_gate_status(gate: str, enabled: bool):
    with PooledConn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO gate_status (gate, is_enabled)
            VALUES (%s, %s)
            ON CONFLICT (gate)
            DO UPDATE SET
                is_enabled = EXCLUDED.is_enabled,
                updated_at = CURRENT_TIMESTAMP
        """, (gate, enabled))
        conn.commit()
    _gate_cache[gate] = (enabled, time.monotonic() + _gate_cache_ttl)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RUN INITIALIZATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ensure_users_table()
ensure_stats_columns()
ensure_proxy_table()
ensure_gate_table()
