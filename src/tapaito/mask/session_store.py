"""Almacén de sesión exclusivamente en memoria RAM con TTL y coherencia de entidades."""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field

from tapaito.schemas import EntityType

NUMERIC_ENTITY_TYPES: frozenset[EntityType] = frozenset(
    {
        EntityType.CEDULA,
        EntityType.NIT,
        EntityType.CELULAR,
        EntityType.RADICADO,
    }
)

_DIGITS_RE = re.compile(r"\d+")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def normalize_entity_value(entity_type: EntityType, raw_value: str) -> str:
    """Normaliza el valor de una entidad para garantizar coherencia dentro de una sesión."""
    cleaned = _WHITESPACE_RE.sub(" ", raw_value.strip())
    if entity_type in NUMERIC_ENTITY_TYPES:
        digits = "".join(_DIGITS_RE.findall(cleaned))
        if entity_type == EntityType.CELULAR and len(digits) == 12 and digits.startswith("57"):
            digits = digits[2:]
        if digits:
            return digits

    return _strip_accents(cleaned).casefold()


@dataclass
class _SessionState:
    last_access: float
    counters: dict[EntityType, int] = field(default_factory=dict)
    key_to_token: dict[tuple[EntityType, str], str] = field(default_factory=dict)
    token_to_value: dict[str, str] = field(default_factory=dict)
    known_values: list[tuple[EntityType, str, str]] = field(default_factory=list)


class SessionStore:
    """Almacén en memoria RAM para coherencia de tokens por sesión (R9: cero persistencia en disco)."""

    def __init__(self, ttl_seconds: int = 1800) -> None:
        self.ttl_seconds = ttl_seconds
        self._sessions: dict[str, _SessionState] = {}

    def _purge_expired(self, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        expired_ids = [
            sid
            for sid, state in self._sessions.items()
            if (current - state.last_access) >= self.ttl_seconds
            and (self.ttl_seconds <= 0 or (current - state.last_access) > self.ttl_seconds)
        ]
        for sid in expired_ids:
            del self._sessions[sid]

    def _get_or_create_state(self, session_id: str) -> _SessionState:
        now = time.monotonic()
        self._purge_expired(now)
        state = self._sessions.get(session_id)
        if state is None:
            state = _SessionState(last_access=now)
            self._sessions[session_id] = state
        else:
            state.last_access = now
        return state

    def get_or_create_token(
        self,
        session_id: str,
        entity_type: EntityType,
        raw_value: str,
    ) -> str:
        """Obtiene el token existente o crea uno nuevo con formato ⟦TIPO_N⟧."""
        state = self._get_or_create_state(session_id)
        norm_key = normalize_entity_value(entity_type, raw_value)
        map_key = (entity_type, norm_key)

        surface = raw_value.strip()
        token = state.key_to_token.get(map_key)
        if token is None:
            next_idx = state.counters.get(entity_type, 0) + 1
            state.counters[entity_type] = next_idx
            token = f"⟦{entity_type.value}_{next_idx}⟧"
            state.key_to_token[map_key] = token
            state.token_to_value[token] = surface

        # Registrar superficie vista para barrido de sesión si no está ya presente
        if surface:
            entry = (entity_type, surface, token)
            if entry not in state.known_values:
                state.known_values.append(entry)
            if entity_type in NUMERIC_ENTITY_TYPES and norm_key != surface:
                norm_entry = (entity_type, norm_key, token)
                if norm_entry not in state.known_values:
                    state.known_values.append(norm_entry)

        return token

    def get_token_to_value_map(self, session_id: str) -> dict[str, str]:
        """Devuelve una copia del mapa token -> valor original representativo de la sesión."""
        now = time.monotonic()
        self._purge_expired(now)
        state = self._sessions.get(session_id)
        if state is None:
            return {}
        state.last_access = now
        return dict(state.token_to_value)

    def get_known_values(self, session_id: str) -> list[tuple[EntityType, str, str]]:
        """Devuelve la lista de (entity_type, raw_surface, token) conocidos en la sesión."""
        now = time.monotonic()
        self._purge_expired(now)
        state = self._sessions.get(session_id)
        if state is None:
            return []
        state.last_access = now
        return list(state.known_values)

    def delete_session(self, session_id: str) -> bool:
        """Elimina explícitamente una sesión de la memoria RAM."""
        self._purge_expired()
        return self._sessions.pop(session_id, None) is not None
