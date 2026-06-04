"""P3 Event-Driven Choreography (task 018).

No central coordinator: agents react to events and emit follow-on
events until a terminal event appears. Bedrock instantiation: events on
a mocked bus with observability_emit per hop. Agentforce instantiation:
platform events with subscribed agent handlers.
"""
from __future__ import annotations

from typing import Any

from agentorch.clients.agentforce import AgentforceClientError
from agentorch.clients.bedrock import BedrockClientError
from agentorch.domain import WorkItem, WorkResult
from agentorch.patterns.base import Pattern
from agentorch.types import Component, Platform

EVENT_CHAIN = ("item_received", "item_enriched", "item_resolved")


class ChoreographyPattern(Pattern):
    pattern_name = "P3 Event-Driven Choreography"

    @classmethod
    def meta(cls) -> dict[str, Any]:
        return {
            "name": cls.pattern_name,
            "intent": "Coordinate agents through events instead of a central "
                      "controller; each agent reacts and emits.",
            "context": "Loosely coupled steps owned by different teams or systems; "
                       "fan-out/fan-in flows.",
            "problem": "Central orchestrators couple all steps and become "
                       "evolution bottlenecks.",
            "forces": ["loose coupling vs global visibility",
                       "autonomy vs end-to-end tracing difficulty",
                       "bus reliability becomes critical"],
            "solution": "A typed event chain; each agent subscribes to its trigger "
                        "event and publishes its completion event.",
            "platform_instantiations": {
                "bedrock": "Mocked event bus; each hop = model call + "
                           "observability_emit of the next event.",
                "agentforce": "Platform events (publish_event/subscribe) drive "
                              "agent handlers in a chain.",
            },
            "consequences": ["+ independent agent evolution, + natural fan-out",
                             "- harder end-to-end debugging",
                             "- event bus is a shared dependency"],
            "governance_hooks": ["event-log audit trail",
                                 "schema validation at the bus boundary"],
        }

    def _execute(self, item: WorkItem) -> WorkResult:
        try:
            if self.bedrock is not None:
                return self._execute_bedrock(item)
            return self._execute_agentforce(item)
        except (BedrockClientError, AgentforceClientError) as exc:
            status = "timeout" if "timeout" in str(exc) else "error"
            return WorkResult(item_id=item.id, status=status, error=str(exc))

    def _execute_bedrock(self, item: WorkItem) -> WorkResult:
        assert self.bedrock is not None and self.agentcore is not None
        session = f"sess-{item.id}"
        hops = []
        for event in EVENT_CHAIN:
            resp = self.bedrock.invoke_agent(f"agent-{event}", "prod", session,
                                             f"react to {event}")
            self.agentcore.observability_emit({"event": event, "item": item.id})
            hops.append(resp["completion"])
        return WorkResult(item_id=item.id, status="ok",
                          payload={"events": list(EVENT_CHAIN), "hops": len(hops)})

    def _ensure_subscribed(self) -> None:
        """Register the event-chain handlers exactly once per client.

        Re-subscribing per request would multiply handlers and fan the
        chain out combinatorially across requests (root-cause fix).
        """
        if getattr(self, "_chain_subscribed", False):
            return
        af = self.agentforce
        assert af is not None

        def make_handler(idx: int):
            def handler(payload: dict[str, Any]) -> None:
                # Each subscriber is a model-backed agent: reacting to an
                # event costs one model reasoning step (task 101 parity
                # with the Bedrock instantiation).
                outcome = self.ctx.boundary_call(
                    Platform.AGENTFORCE, "model_invoke", Component.MODEL_BACKEND)
                if not outcome.success:
                    raise AgentforceClientError(
                        f"choreography handler failed: "
                        f"{outcome.fault.value if outcome.fault else 'unknown'}",
                        outcome)
                tokens_cfg = self.ctx.cfg.tokens
                self.ctx.model_invocations += 1
                self.ctx.tokens_in += int(tokens_cfg.input_mean)
                self.ctx.tokens_out += int(tokens_cfg.output_mean)
                self._request_log.append(EVENT_CHAIN[idx])
                if idx + 1 < len(EVENT_CHAIN):
                    af.publish_event(EVENT_CHAIN[idx + 1], payload)
            return handler

        for i, event in enumerate(EVENT_CHAIN):
            af.subscribe(event, make_handler(i))
        self._chain_subscribed = True

    def _execute_agentforce(self, item: WorkItem) -> WorkResult:
        assert self.agentforce is not None
        af = self.agentforce
        self._request_log: list[str] = []
        log = self._request_log
        self._ensure_subscribed()
        af.publish_event(EVENT_CHAIN[0], {"item": item.id})
        ok = log == list(EVENT_CHAIN)
        return WorkResult(item_id=item.id, status="ok" if ok else "error",
                          payload={"events": log, "hops": len(log)},
                          error=None if ok else "event chain incomplete")
