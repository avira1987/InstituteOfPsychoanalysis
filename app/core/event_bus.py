"""Event Bus - Publishes events for notifications, sub-process triggers, and integrations."""

import logging
from typing import Any, Callable, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class Event:
    """An event published by the system."""
    def __init__(self, event_type: str, payload: dict, source: Optional[str] = None):
        self.event_type = event_type
        self.payload = payload
        self.source = source
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self):
        return {
            "event_type": self.event_type,
            "payload": self.payload,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }


class EventBus:
    """
    Simple in-process event bus for publishing and subscribing to events.

    Supports:
    - Subscribing handlers to event types
    - Publishing events to all registered handlers
    - Wildcard subscriptions (subscribe to all events with "*")
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}
        self._global_handlers: list[Callable] = []

    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe a handler to a specific event type."""
        if event_type == "*":
            self._global_handlers.append(handler)
        else:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable):
        """Unsubscribe a handler from an event type."""
        if event_type == "*":
            self._global_handlers.remove(handler)
        elif event_type in self._handlers:
            self._handlers[event_type].remove(handler)

    async def publish(self, event: Event):
        """Publish an event to all subscribed handlers."""
        handlers = self._handlers.get(event.event_type, []) + self._global_handlers

        for handler in handlers:
            try:
                result = handler(event)
                # Support async handlers
                if hasattr(result, "__await__"):
                    await result
            except Exception as e:
                logger.error(f"Event handler error for '{event.event_type}': {e}", exc_info=True)

    async def publish_transition(
        self,
        process_code: str,
        instance_id: str,
        from_state: str,
        to_state: str,
        trigger_event: str,
        actor_id: str,
        actions: list[dict] | None = None,
    ):
        """Publish a transition event with standard payload."""
        event = Event(
            event_type=f"transition.{process_code}.{trigger_event}",
            payload={
                "process_code": process_code,
                "instance_id": instance_id,
                "from_state": from_state,
                "to_state": to_state,
                "trigger_event": trigger_event,
                "actor_id": actor_id,
                "actions": actions or [],
            },
            source="state_machine_engine",
        )
        await self.publish(event)

        # Also publish individual action events
        for action in (actions or []):
            action_event = Event(
                event_type=f"action.{action.get('type', 'unknown')}",
                payload={
                    **action,
                    "process_code": process_code,
                    "instance_id": instance_id,
                },
                source="state_machine_engine",
            )
            await self.publish(action_event)


# Singleton event bus
event_bus = EventBus()
