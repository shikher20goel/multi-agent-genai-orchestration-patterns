"""P6 Human-in-the-Loop Adjudication (task 021; latency task 101,
deferral task 104).

End-to-end latency is HUMAN-STEP-DOMINATED: an adjudicated request pays
the routing hop plus a human review decision time drawn from the
``latency.shared.human_decision_delay`` lognormal (p50 ~30 s — tens of
seconds, configurable in configs/default.yaml). A human_queue OUTAGE
window defers the decision: the item stays queued until the window
ends and is then reviewed normally — correctness is isolated (no
wrong auto-approval), latency rises, integrity is preserved.

Low-confidence outputs pause the chain, route to a human queue, and
resume with the recorded human decision. Bedrock instantiation:
guardrail/confidence gate + paused session resumed after a human-stub
decision. Agentforce instantiation: Omni-Channel handoff to a human
queue, then resume.
"""
from __future__ import annotations

from typing import Any

from agentorch.clients.agentforce import AgentforceClientError
from agentorch.clients.bedrock import BedrockClientError
from agentorch.domain import WorkItem, WorkResult
from agentorch.patterns.base import Pattern, work_steps
from agentorch.types import Component, Platform


class HitlPattern(Pattern):
    # Task 201: the confidence gate routes ONLY below-threshold items
    # to the human queue -- selective by design (docs/FIT_RULE.md).
    CAPABILITIES = {"selective_human_routing": True}
    pattern_name = "P6 Human-in-the-Loop Adjudication"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.decision_log: list[dict[str, Any]] = []
        self._paused: dict[str, dict[str, Any]] = {}
        self._deferred = False

    @classmethod
    def meta(cls) -> dict[str, Any]:
        return {
            "name": cls.pattern_name,
            "intent": "Gate consequential agent outputs behind a human decision "
                      "when confidence is below threshold.",
            "context": "Regulated or high-stakes actions (refunds, escalations, "
                       "legal text) produced by agents.",
            "problem": "Fully autonomous output of consequential actions violates "
                       "oversight requirements and risk tolerance.",
            "forces": ["safety vs throughput",
                       "human latency vs automation speed",
                       "auditability vs friction"],
            "solution": "A confidence gate pauses the run, persists state, routes "
                        "to a human queue, logs the decision, and resumes "
                        "(approve) or stops (reject).",
            "platform_instantiations": {
                "bedrock": "Guardrail-checked output + paused session state in "
                           "AgentCore memory; resume after human-stub decision.",
                "agentforce": "Omni-Channel handoff to a human queue; platform "
                              "event resumes the flow with the decision.",
            },
            "consequences": ["+ regulatory alignment, + logged accountability",
                             "- human queue latency dominates p99",
                             "- paused state must be durable"],
            "governance_hooks": ["immutable decision log entries",
                                 "EU AI Act Art. 14-style oversight point"],
        }

    # -- pause / resume API -------------------------------------------------
    def pause(self, item: WorkItem, draft: str, confidence: float) -> str:
        """Persist state and route to a human; returns a pause token."""
        token = f"pause-{item.id}"
        state = {"item_id": item.id, "draft": draft, "confidence": confidence}
        if self.agentcore is not None:
            self.agentcore.memory_put(token, state)
        else:
            assert self.omni is not None
            self.omni.add_queue("adjudication", agents=1)
            try:
                self.omni.handoff(item, "adjudication")
            except AgentforceClientError:
                # Task 104: a faulted human queue defers the handoff; the
                # paused state is durable and the caller waits out the
                # outage (deferred decision, never auto-approval).
                self._deferred = True
        self._paused[token] = state
        return token

    def resume(self, token: str, decision: str, reviewer: str = "human-stub") -> dict[str, Any]:
        """Apply the human decision to a paused run and log it."""
        if token not in self._paused:
            raise KeyError(f"no paused state for {token!r}")
        state = self._paused.pop(token)
        entry = {"token": token, "item_id": state["item_id"],
                 "decision": decision, "reviewer": reviewer,
                 "confidence": state["confidence"], "ts": self.ctx.clock.now()}
        self.decision_log.append(entry)
        return entry

    def _confidence(self, item: WorkItem) -> float:
        # Confidence supplied by the scenario payload; default mid-range.
        return float(item.payload.get("confidence", 0.9))

    def _execute(self, item: WorkItem) -> WorkResult:
        threshold = float(self.cfg.patterns.p6.confidence_threshold)
        steps = work_steps(item)
        try:
            # Task 105: the draft covers the item's full multi-step content
            # (token volume scales with steps); on Agentforce each section
            # is assembled by one Flex-credit-billed draft action.
            if self.bedrock is not None:
                self.ctx.content_scale = steps
                draft = self.bedrock.invoke_agent(
                    "drafter", "prod", f"sess-{item.id}",
                    str(item.payload.get("task", item.id)))["completion"]
                self.ctx.content_scale = 1.0
                assert self.guardrails is not None
                self.guardrails.apply(draft, mode="shadow")
            else:
                assert self.agentforce is not None
                self.agentforce.register_action("draft", lambda a: {"draft": "drafted"})
                self.agentforce.register_topic("adjudicated_work",
                                               ["draft"] * steps)
                self.ctx.content_scale = steps
                draft = str(self.agentforce.send(
                    "adjudicated_work", {"item": item.id})["result"])
                self.ctx.content_scale = 1.0
            confidence = self._confidence(item)
            adjudicated = False
            decision = "auto_approved"
            if confidence < threshold:
                self._deferred = False
                token = self.pause(item, draft, confidence)
                if self.platform is Platform.AGENTFORCE:
                    deferred = self._deferred  # handoff hop inside pause()
                else:
                    routing = self.ctx.boundary_call(
                        self.platform, "memory", Component.HUMAN_QUEUE)
                    deferred = not routing.success
                if deferred:
                    # Task 104: a human_queue fault DEFERS the decision —
                    # the item stays queued until the outage window ends,
                    # then a human reviews it normally. Never auto-approve.
                    window_end = self.ctx.fault_injector.window_end(
                        Component.HUMAN_QUEUE)
                    if window_end is not None:
                        self.ctx.add_delay(
                            max(0.0, window_end - self.ctx.sim_now),
                            blocking=False)
                    else:
                        # Probabilistic queue fault: bounded re-route delay.
                        self.ctx.add_delay(float(self.cfg.faults.throttle_delay_s),
                                           blocking=False)
                # Human review decision time (task 101): lognormal with
                # p50 in the tens of seconds; dominates P6 end-to-end
                # latency. The paused request RELEASES its compute server
                # while waiting (blocking=False): the human queue is a
                # separate resource from the model-serving pool.
                self.ctx.add_delay(
                    self.ctx.latency_model.sample_shared("human_decision_delay"),
                    blocking=False)
                entry = self.resume(token, decision="approved")
                adjudicated = True
                decision = entry["decision"]
            return WorkResult(item_id=item.id, status="ok",
                              payload={"draft": draft, "adjudicated": adjudicated,
                                       "decision": decision,
                                       "confidence": confidence})
        except (BedrockClientError, AgentforceClientError) as exc:
            status = "timeout" if "timeout" in str(exc) else "error"
            return WorkResult(item_id=item.id, status=status, error=str(exc))
