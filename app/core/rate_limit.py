"""Limitador de intentos fallidos de login, en memoria.

Cuenta intentos FALLIDOS por clave dentro de una ventana de tiempo.
Limitación conocida: vive en la memoria de un solo proceso. Si despliegas con
varios workers o réplicas, cada uno llevará su propia cuenta; en ese caso hay
que usar un almacén compartido (p. ej. Redis).
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, status


class FailedAttemptLimiter:
    def __init__(self, window_seconds: int):
        self.window = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._attempts[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if not q:
            self._attempts.pop(key, None)
        return q

    def retry_after(self, key: str, limit: int) -> int:
        """Segundos hasta poder reintentar; 0 si no está bloqueado."""
        now = time.monotonic()
        with self._lock:
            q = self._prune(key, now)
            if len(q) >= limit:
                return max(1, int(self.window - (now - q[0])) + 1)
            return 0

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            self._attempts[key].append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._attempts.clear()


def raise_too_many_attempts(retry_after: int) -> None:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Demasiados intentos fallidos. Inténtalo de nuevo más tarde.",
        headers={"Retry-After": str(retry_after)},
    )
