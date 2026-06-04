"""P4 Shared-Memory Blackboard (task 019; latency task 101).

Store-mediated coordination is CONTENTION-BOUND: every blackboard write
pays a serialization penalty that grows with the number of concurrent
writers (``patterns.p4.contention_per_writer_s`` x (writers - 1), with
writers = concurrent in-flight requests reported by the load
generator). Under bursty load the in-flight count rises, so P4 latency
degrades with load — the structural consequence in the paper's Table 3.

Specialists iteratively read/write a shared memory; a controller decides
when the solution is complete. Bedrock instantiation: AgentCore memory
as the blackboard. Agentforce instantiation: session context store via
memory-equivalent boundary calls (modeled with the memory service).
"""
from __future__ import annotations

from typing import Any

from agentorch.clients.agentforce import AgentforceClientError
from agentorch.clients.bedrock import BedrockClientError
from agentorch.domain import WorkItem, WorkResult
from agentorch.patterns.base import Pattern, work_steps
from agentorch.types import Component, Platform


class BlackboardPattern(Pattern):
    # Task 201: specialists contribute opportunistically against shared
    # state; decomposition is emergent, not fixed (docs/FIT_RULE.md).
    CAPABILITIES = {"adaptive_decomposition": True}
    pattern_name = "P4 Shared-Memory Blackboard"

    @classmethod
    def meta(cls) -> dict[str, Any]:
        return {
            "name": cls.pattern_name,
            "intent": "Let specialists contribute partial solutions to a shared "
                      "memory until a complete answer emerges.",
            "context": "Ill-structured problems where contribution order is not "
                       "fixed and partial results inform later steps.",
            "problem": "Pipelines force a fixed order; supervisors must know the "
                       "full decomposition up front.",
            "forces": ["opportunistic contribution vs convergence guarantees",
                       "shared state vs contention/consistency",
                       "memory store availability is critical"],
            "solution": "A blackboard (shared memory) plus N specialists that read "
                        "current state and append contributions; a controller "
                        "checks completion.",
            "platform_instantiations": {
                "bedrock": "AgentCore memory_get/memory_put as the blackboard; "
                           "specialists are Bedrock agents.",
                "agentforce": "Session context store ops as the blackboard; "
                              "specialists are topic actions.",
            },
            "consequences": ["+ flexible, order-free collaboration",
                             "- memory store is a single shared dependency",
                             "- convergence must be bounded explicitly"],
            "governance_hooks": ["versioned blackboard writes for audit",
                                 "controller-level completion policy"],
        }

    def _contention_delay(self) -> None:
        """Write-contention term (task 101): rises with concurrent writers."""
        per_writer = float(self.cfg.patterns.p4.contention_per_writer_s)
        writers = max(1, int(self.ctx.concurrent_in_flight))
        self.ctx.add_delay(per_writer * (writers - 1))

    def _execute(self, item: WorkItem) -> WorkResult:
        n = int(self.cfg.patterns.p4.n_specialists)
        try:
            if self.bedrock is not None:
                return self._execute_bedrock(item, n)
            return self._execute_agentforce(item, n)
        except (BedrockClientError, AgentforceClientError) as exc:
            status = "timeout" if "timeout" in str(exc) else "error"
            return WorkResult(item_id=item.id, status=status, error=str(exc))

    def _execute_bedrock(self, item: WorkItem, n: int) -> WorkResult:
        assert self.bedrock is not None and self.agentcore is not None
        key = f"bb-{item.id}"
        self.agentcore.memory_put(key, [])
        session = f"sess-{item.id}"
        share = -(-work_steps(item) // n)  # ceil: steps each specialist covers
        for i in range(n):
            board = self.agentcore.memory_get(key)
            # Each specialist contributes its share of the multi-step
            # content in one invocation (task 105: token volume scales).
            self.ctx.content_scale = share
            resp = self.bedrock.invoke_agent(
                f"specialist-{i}", "prod", session,
                f"contribute given {len(board)} prior entries")
            self.ctx.content_scale = 1.0
            board = list(board) + [resp["completion"]]
            self._contention_delay()
            self.agentcore.memory_put(key, board)
        final = self.agentcore.memory_get(key)
        complete = len(final) == n
        return WorkResult(item_id=item.id, status="ok" if complete else "error",
                          payload={"contributions": len(final)},
                          error=None if complete else "blackboard incomplete")

    def _execute_agentforce(self, item: WorkItem, n: int) -> WorkResult:
        assert self.agentforce is not None
        af = self.agentforce
        board: list[str] = []

        def specialist(args: dict[str, Any]) -> dict[str, Any]:
            board.append(f"contribution-{len(board)}")
            return {"board_size": len(board)}

        # Each specialist's dispatch persists its share of the item's
        # steps via per-step contribution actions (task 105: Flex-credit
        # billed even though they make no model call).
        share = -(-work_steps(item) // n)
        af.register_action("contribute", specialist)
        af.register_topic("blackboard_work",
                          ["contribute"] * max(1, share))
        for _ in range(n):
            # Each contribution: a memory read/write boundary op (paying the
            # write-contention term) + topic dispatch.
            self._contention_delay()
            outcome = self.ctx.boundary_call(Platform.AGENTFORCE, "memory",
                                             Component.MEMORY_STORE)
            if not outcome.success:
                return WorkResult(item_id=item.id, status="error",
                                  error=f"blackboard store failed: "
                                        f"{outcome.fault.value if outcome.fault else 'unknown'}")
            self.ctx.service_calls += 1
            self.ctx.content_scale = share
            af.send("blackboard_work", {"item": item.id})
            self.ctx.content_scale = 1.0
        complete = len(board) == n * max(1, share)
        return WorkResult(item_id=item.id, status="ok" if complete else "error",
                          payload={"contributions": len(board)},
                          error=None if complete else "blackboard incomplete")
