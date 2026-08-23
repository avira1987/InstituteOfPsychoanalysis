"""Inter-process chaining dispatcher.

`StateMachineEngine` calls `dispatch_chaining()` once after a process starts and
once after every transition. Which handlers run is decided by
`metadata/wiring/process_links.json`, so adding a new inter-process edge never
requires touching the engine.

Handlers live in `app.services.chaining.handlers` and register themselves with
`@chaining_handler("<name>")`. They receive a `ChainingContext` and must be
individually failure-isolated: a broken edge must never roll back a transition
that already succeeded.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from app.core.wiring_registry import (
    PHASE_AFTER_TRANSITION,
    PHASE_ON_START,
    ProcessLink,
    get_registry,
)

logger = logging.getLogger(__name__)


@dataclass
class ChainingContext:
    """Everything a chaining handler is allowed to depend on."""

    db: Any
    engine: Any
    instance: Any
    process_code: str
    student_id: uuid.UUID
    actor_id: Optional[uuid.UUID]
    actor_role: Optional[str] = None
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    trigger_event: Optional[str] = None
    payload: dict = field(default_factory=dict)
    is_completed: bool = False
    phase: str = PHASE_AFTER_TRANSITION

    @property
    def instance_id(self) -> Any:
        return getattr(self.instance, "id", None)


ChainingHandler = Callable[[ChainingContext], Awaitable[None]]

_HANDLERS: dict[str, ChainingHandler] = {}
_handlers_loaded = False


def chaining_handler(name: str) -> Callable[[ChainingHandler], ChainingHandler]:
    """Register a chaining handler under a stable name used by the wiring file."""

    def decorator(func: ChainingHandler) -> ChainingHandler:
        if name in _HANDLERS and _HANDLERS[name] is not func:
            raise ValueError(f"chaining handler '{name}' is already registered")
        _HANDLERS[name] = func
        return func

    return decorator


def _ensure_handlers_loaded() -> None:
    """Import the handler module lazily to keep `app.core` free of service imports."""
    global _handlers_loaded
    if _handlers_loaded:
        return
    import app.services.chaining.handlers  # noqa: F401  (registers handlers on import)

    _handlers_loaded = True


def get_handler(name: str) -> Optional[ChainingHandler]:
    _ensure_handlers_loaded()
    return _HANDLERS.get(name)


def registered_handler_names() -> set[str]:
    _ensure_handlers_loaded()
    return set(_HANDLERS)


async def _run_link(link: ProcessLink, ctx: ChainingContext) -> Any:
    """Run one link, isolated. Returns a refetched instance when requested."""
    handler = _HANDLERS.get(link.handler)
    if handler is None:
        logger.error(
            "chaining link '%s' references unknown handler '%s' (instance=%s)",
            link.id,
            link.handler,
            ctx.instance_id,
        )
        return None

    try:
        if link.flush_before:
            await ctx.db.flush()
        await handler(ctx)
    except Exception:
        logger.exception(
            "chaining link '%s' failed (handler=%s process=%s instance=%s)",
            link.id,
            link.handler,
            ctx.process_code,
            ctx.instance_id,
        )
        return None

    if link.refetch_instance and ctx.engine is not None:
        try:
            refreshed = await ctx.engine.get_process_instance(ctx.instance_id)
            if refreshed is not None:
                ctx.instance = refreshed
                return refreshed
        except Exception:
            logger.exception(
                "chaining link '%s' could not refetch instance %s",
                link.id,
                ctx.instance_id,
            )
    return None


async def dispatch_chaining(ctx: ChainingContext) -> Any:
    """Run every declarative link matching `ctx`, in wiring-file order.

    Returns the most recently refetched instance, or None when no link asked for
    a refetch. The engine uses this to keep its local reference current.
    """
    _ensure_handlers_loaded()
    links = get_registry().links_for(
        phase=ctx.phase,
        process_code=ctx.process_code,
        from_state=ctx.from_state,
        to_state=ctx.to_state,
        trigger_event=ctx.trigger_event,
        is_completed=ctx.is_completed,
    )
    if not links:
        return None

    latest_instance = None
    for link in links:
        refreshed = await _run_link(link, ctx)
        if refreshed is not None:
            latest_instance = refreshed
    return latest_instance


async def dispatch_on_start(
    *,
    db: Any,
    engine: Any,
    instance: Any,
    actor_id: Optional[uuid.UUID],
    actor_role: Optional[str] = None,
    initial_context: Optional[dict] = None,
) -> Any:
    ctx = ChainingContext(
        db=db,
        engine=engine,
        instance=instance,
        process_code=instance.process_code,
        student_id=instance.student_id,
        actor_id=actor_id,
        actor_role=actor_role,
        payload=dict(initial_context or {}),
        is_completed=bool(getattr(instance, "is_completed", False)),
        phase=PHASE_ON_START,
    )
    return await dispatch_chaining(ctx)


async def dispatch_after_transition(
    *,
    db: Any,
    engine: Any,
    instance: Any,
    from_state: Optional[str],
    to_state: Optional[str],
    trigger_event: Optional[str],
    actor_id: Optional[uuid.UUID],
    actor_role: Optional[str] = None,
    payload: Optional[dict] = None,
) -> Any:
    ctx = ChainingContext(
        db=db,
        engine=engine,
        instance=instance,
        process_code=instance.process_code,
        student_id=instance.student_id,
        actor_id=actor_id,
        actor_role=actor_role,
        from_state=from_state,
        to_state=to_state,
        trigger_event=trigger_event,
        payload=dict(payload or {}),
        is_completed=bool(getattr(instance, "is_completed", False)),
        phase=PHASE_AFTER_TRANSITION,
    )
    return await dispatch_chaining(ctx)
