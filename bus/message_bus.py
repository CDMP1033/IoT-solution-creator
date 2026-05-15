from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Callable, Coroutine

import structlog

from .message import Message, MessageType

logger = structlog.get_logger(__name__)

Handler = Callable[[Message], Coroutine]


class MessageBus:
    """In-process async pub/sub message bus.

    Agents subscribe to their own name. The orchestrator subscribes to
    "orchestrator". No cross-agent direct messaging is allowed at the
    application level — the bus enforces delivery only to declared recipients.

    Usage:
        bus = MessageBus()
        bus.subscribe("my_agent", my_handler)
        await bus.publish(message)
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._pending: dict[str, asyncio.Future] = {}
        self._log = logger.bind(component="message_bus")

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def subscribe(self, recipient: str, handler: Handler) -> None:
        """Register an async handler for all messages addressed to *recipient*."""
        self._handlers[recipient].append(handler)
        self._log.debug("bus.subscribed", recipient=recipient)

    def unsubscribe(self, recipient: str, handler: Handler) -> None:
        handlers = self._handlers.get(recipient, [])
        if handler in handlers:
            handlers.remove(handler)

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish(self, message: Message) -> None:
        """Deliver *message* to all handlers registered for its recipient.

        Fires all handlers concurrently. If a handler raises, the error is
        logged but other handlers still run.
        """
        self._log.debug(
            "bus.publish",
            id=message.id,
            sender=message.sender,
            recipient=message.recipient,
            type=message.type,
        )

        handlers = self._handlers.get(message.recipient, [])
        if not handlers:
            self._log.warning("bus.no_handlers", recipient=message.recipient, id=message.id)

        if handlers:
            results = await asyncio.gather(*[h(message) for h in handlers], return_exceptions=True)
            for result in results:
                if isinstance(result, BaseException):
                    self._log.error("bus.handler_error", error=repr(result))

        # Resolve any futures waiting on this message's correlation_id
        if message.correlation_id and message.correlation_id in self._pending:
            future = self._pending.pop(message.correlation_id)
            if not future.done():
                if message.type == MessageType.ERROR:
                    future.set_exception(RuntimeError(message.payload.get("error", "unknown error")))
                else:
                    future.set_result(message)

    # ------------------------------------------------------------------
    # Request / reply helper
    # ------------------------------------------------------------------

    async def request(self, message: Message, timeout: float = 60.0) -> Message:
        """Publish *message* and wait for a correlated RESPONSE.

        Args:
            message: A REQUEST message to send.
            timeout: Seconds to wait before raising asyncio.TimeoutError.

        Returns:
            The correlated RESPONSE message.
        """
        loop = asyncio.get_event_loop()
        future: asyncio.Future[Message] = loop.create_future()
        self._pending[message.id] = future

        await self.publish(message)

        try:
            return await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(message.id, None)
            self._log.error("bus.request_timeout", id=message.id, recipient=message.recipient)
            raise
