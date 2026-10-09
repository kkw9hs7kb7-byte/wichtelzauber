"""Simple Argon2id credentials and opaque server-side sessions."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError, VerificationError

hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1, hash_len=32, salt_len=16, type=Type.ID)
SESSION_SECONDS = 14 * 24 * 3600


def now():
    return datetime.now(timezone.utc).isoformat()


def after(seconds):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def new_id():
    return secrets.token_hex(16)


def hash_password(pw):
    return hasher.hash(pw)


def check_password(stored, pw):
    try:
        return hasher.verify(stored, pw)
    except (VerifyMismatchError, VerificationError, ValueError, TypeError):
        return False


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(conn, kind, subject_id):
    raw = secrets.token_urlsafe(40)
    csrf = secrets.token_urlsafe(32)
    conn.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?)',
                 (digest(raw), kind, subject_id, csrf, after(SESSION_SECONDS), now()))
    return raw, csrf


def read_session(conn, raw):
    if not raw:
        return None
    s = conn.execute('SELECT * FROM sessions WHERE token_hash=? AND expires_at > ?',
                     (digest(raw), now())).fetchone()
    return dict(s) if s else None


def revoke_all(conn, kind, subject_id):
    conn.execute('DELETE FROM sessions WHERE kind=? AND subject_id=?', (kind, subject_id))
