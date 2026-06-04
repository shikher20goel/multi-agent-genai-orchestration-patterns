"""Local mock of Salesforce Agentforce semantics (no network).

Models topics routing to actions, Agent Script sequential action
chaining, platform events with subscribers, and Omni-Channel handoff
to human queues with fallback — per the architecture contract.
"""
from __future__ import annotations

from typing import Any, Callable

from agentorch.clients.context import CallContext, CallOutcome
from agentorch.domain import WorkItem
from agentorch.types import Component, Platform


class AgentforceClientError(RuntimeError):
    """Raised when a mocked Agentforce call fails (fault injected)."""

    def __init__(self, message: str, outcome: CallOutcome):
        super().__init__(message)
        self.outcome = outcome


class MockAgentforceClient:
    """Topics -> actions routing, Agent Script chaining, platform events."""

    def __init__(self, ctx: CallContext):
        self._ctx = ctx
        self._topics: dict[str, list[str]] = {}
        self._actions: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}
        self._subscribers: dict[str, list[Callable[[dict[str, Any]], None]]] = {}
        self._sessions: dict[str, dict[str, Any]] = {}
        self._session_counter = 0

    # -- session / topic / action registry -------------------------------
    def start_session(self, user_id: str = "user", channel: str = "web") -> str:
        self._session_counter += 1
        session_id = f"af-session-{self._session_counter}"
        self._sessions[session_id] = {"user_id": user_id, "channel": channel, "turns": []}
        return session_id

    def register_topic(self, topic: str, actions: list[str]) -> None:
        self._topics[topic] = list(actions)

    def register_action(self, name: str,
                        fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> None:
        self._actions[name] = fn or (lambda args: {"action": name, "ok": True, **args})

    # -- core invocation paths --------------------------------------------
    def _run_action(self, action: str, args: dict[str, Any]) -> dict[str, Any]:
        ctx = self._ctx
        outcome = ctx.boundary_call(Platform.AGENTFORCE, "action", Component.TOOL)
        if not outcome.success:
            raise AgentforceClientError(
                f"action {action} failed: "
                f"{outcome.fault.value if outcome.fault else 'unknown'}",
                outcome,
            )
        ctx.service_calls += 1
        fn = self._actions.get(action)
        if fn is None:
            raise KeyError(f"action {action!r} not registered")
        return fn(args)

    def send(self, topic: str, message: dict[str, Any]) -> dict[str, Any]:
        """Route a message to a topic; the topic's actions run as pass-through chain.

        Each action receives the previous action's output merged into the
        message — pass-through chaining.
        """
        ctx = self._ctx
        # Model reasoning step (topic classification + planning).
        outcome = ctx.boundary_call(Platform.AGENTFORCE, "model_invoke", Component.MODEL_BACKEND)
        if not outcome.success:
            raise AgentforceClientError(
                f"topic routing failed: "
                f"{outcome.fault.value if outcome.fault else 'unknown'}",
                outcome,
            )
        tokens_cfg = ctx.cfg.tokens
        ctx.model_invocations += 1
        ctx.tokens_in += int(tokens_cfg.input_mean)
        ctx.tokens_out += int(tokens_cfg.output_mean)
        if topic not in self._topics:
            raise KeyError(f"topic {topic!r} not registered")
        carried: dict[str, Any] = dict(message)
        trace: list[dict[str, Any]] = []
        for action in self._topics[topic]:
            result = self._run_action(action, carried)
            trace.append(result)
            carried = {**carried, **result}  # pass-through chaining
        return {"topic": topic, "result": carried, "trace": trace}

    def run_agent_script(self, script: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sequential Agent Script: each step {'action': name, 'args': {...}}.

        Outputs chain forward: step N's output is merged into step N+1's args.
        """
        carried: dict[str, Any] = {}
        results: list[dict[str, Any]] = []
        for step in script:
            args = {**carried, **step.get("args", {})}
            result = self._run_action(step["action"], args)
            results.append(result)
            carried = {**carried, **result}
        return results

    # -- platform events ----------------------------------------------------
    def subscribe(self, event_type: str, handler: Callable[[dict[str, Any]], None]) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish_event(self, event_type: str, payload: dict[str, Any]) -> int:
        """Publish a platform event; deliver to all subscribers. Returns count."""
        ctx = self._ctx
        outcome = ctx.boundary_call(Platform.AGENTFORCE, "event_bus", Component.EVENT_BUS)
        if not outcome.success:
            raise AgentforceClientError(
                f"publish_event failed: "
                f"{outcome.fault.value if outcome.fault else 'unknown'}",
                outcome,
            )
        ctx.service_calls += 1
        handlers = self._subscribers.get(event_type, [])
        for h in handlers:
            h(payload)
        return len(handlers)


class OmniChannel:
    """Omni-Channel work routing to human queues with default fallback."""

    DEFAULT_QUEUE = "default"

    def __init__(self, ctx: CallContext):
        self._ctx = ctx
        self.queues: dict[str, list[WorkItem]] = {self.DEFAULT_QUEUE: []}
        self.agents_available: dict[str, int] = {self.DEFAULT_QUEUE: 1}

    def add_queue(self, name: str, agents: int = 1) -> None:
        self.queues[name] = []
        self.agents_available[name] = agents

    def handoff(self, item: WorkItem, queue: str) -> dict[str, Any]:
        """Route `item` to `queue`; fall back to default when target empty/absent."""
        ctx = self._ctx
        outcome = ctx.boundary_call(Platform.AGENTFORCE, "omni_channel", Component.HUMAN_QUEUE)
        if not outcome.success:
            raise AgentforceClientError(
                f"omni-channel handoff failed: "
                f"{outcome.fault.value if outcome.fault else 'unknown'}",
                outcome,
            )
        ctx.service_calls += 1
        target = queue
        fallback = False
        if queue not in self.queues or self.agents_available.get(queue, 0) <= 0:
            target = self.DEFAULT_QUEUE
            fallback = True
        self.queues[target].append(item)
        return {"queue": target, "fallback": fallback, "item_id": item.id}
