"""
accounts/encryption.py

Central utility for encrypting and hashing sensitive PII fields (Aadhar, PAN).

Design:
  - ENCRYPT  : Fernet symmetric encryption using FIELD_ENCRYPTION_KEY from settings.
                Stored ciphertext can be decrypted to show the real value to admins.
  - HASH     : HMAC-SHA256 of the raw value using FIELD_HASH_KEY from settings.
                Hash is stored separately and used for fast, secure uniqueness checks.
  - MASK     : A safe display string returned in API responses (never the raw value).
"""

import hmac
import hashlib
from cryptography.fernet import Fernet
from django.conf import settings


def _get_fernet():
    key = settings.FIELD_ENCRYPTION_KEY
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt(value: str) -> str:
    """Encrypt a plain-text string. Returns a URL-safe base64 ciphertext string."""
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a ciphertext string back to plain text."""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


def make_hash(value: str) -> str:
    """
    Create a stable HMAC-SHA256 hex digest of a value.
    Used for uniqueness checks — same input always produces same hash.
    """
    key = settings.FIELD_HASH_KEY
    if isinstance(key, str):
        key = key.encode()
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()


def mask_aadhar(value: str) -> str:
    """Return a masked display string, e.g. 'XXXX-XXXX-9012'."""
    return f"XXXX-XXXX-{value[-4:]}"


def mask_pan(value: str) -> str:
    """Return a masked display string, e.g. 'XXXXX9999X'."""
    return f"XXXXX{value[5:9]}X"
