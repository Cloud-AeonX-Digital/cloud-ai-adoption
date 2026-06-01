import time
import threading
from .models import AlertPayload

# In-memory store: key -> expiry timestamp
# Key = trigger_id:host_name
# TTL = 30 minutes (Gap #8 fix)
_TTL_SECONDS = 30 * 60
_store: dict[str, float] = {}
_lock = threading.Lock()


def _key(incident: AlertPayload) -> str:
    return f"{incident.alert.trigger_id}:{incident.host.name}"


def is_duplicate(incident: AlertPayload) -> bool:
    k = _key(incident)
    with _lock:
        expiry = _store.get(k)
        if expiry and time.time() < expiry:
            return True
    return False


def mark_seen(incident: AlertPayload) -> None:
    k = _key(incident)
    with _lock:
        _store[k] = time.time() + _TTL_SECONDS
        _evict()


def _evict() -> None:
    """Remove expired entries to prevent unbounded memory growth."""
    now = time.time()
    expired = [k for k, exp in _store.items() if exp < now]
    for k in expired:
        del _store[k]
