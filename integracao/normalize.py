import base64
import binascii
import hmac
from enum import Enum


def authenticated(header, user, password):
    if not user or len(password) < 16:
        return False
    try:
        scheme, encoded = header.split(" ", 1)
        if scheme.lower() != "basic":
            return False
        supplied_user, supplied_password = base64.b64decode(encoded, validate=True).decode().split(":", 1)
        return hmac.compare_digest(supplied_user.encode(), user.encode()) & hmac.compare_digest(supplied_password.encode(), password.encode())
    except (ValueError, UnicodeError, binascii.Error):
        return False


def scalar(value):
    if isinstance(value, Enum):
        return str(value.value)
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return str(value)[:200]
    return None


def normalize_printer(printer):
    identifier = scalar(getattr(printer, "id", None))
    if not identifier:
        raise ValueError("Printer without stable id")
    return {
        "id": identifier,
        "name": scalar(getattr(printer, "name", None)) or "Impressora " + identifier,
        "status": scalar(getattr(printer, "current_status", None)),
        "progress_percent": None,
        "filename": None,
        "elapsed_minutes": None,
        "remaining_minutes": None,
        "nozzle_celsius": None,
        "bed_celsius": None,
    }
