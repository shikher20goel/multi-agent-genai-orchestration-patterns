"""P2 Sequential Pipeline (task 017; latency task 101).

End-to-end service time is ADDITIVE over stages: S2 (4-8 stages) is
structurally slower than S1 (single stage) on both p50 and p99.

Work flows through an ordered chain of stages; each stage's output is
the next stage's input. Bedrock instantiation: a chain of invoke_agent
calls sharing one session. Agentforce instantiation: run_agent_script
with sequential action chaining.
"""
from __future__ import annotations

from typing import Any

from agentorch.clients.agentforce import AgentforceClientError
from agentorch.clients.bedrock import BedrockClientError
from agentorch.domain import WorkItem, WorkResult
from agentorch.patterns.base import Pattern

DEFAULT_STAGES = ("extract", "draft", "review")


class PipelinePattern(Pattern):
    pattern_name = "P2 Sequential Pipeline"

    @classmethod
    def meta(cls) -> dict[str, Any]:
        return {
            "name": cls.pattern_name,
            "intent": "Process a work item through an ordered chain of specialist "
                      "stages, each consuming the previous stage's output.",
            "context": "Multi-step transformations (extract -> draft -> review) with "
                       "a fixed, known order.",
            "problem": "Interleaving all steps in one agent prompt loses checkpoint "
                       "boundaries and makes per-step retry impossible.",
            "forces": ["throughput vs end-to-end latency",
                       "stage isolation vs data-passing overhead",
                       "fixed order vs flexibility"],
            "solution": "An explicit stage list; output of stage k feeds stage k+1; "
                        "failures localize to a stage.",
            "platform_instantiations": {
                "bedrock": "Chain of invoke_agent calls sharing one sessionId, one "
                           "agent alias per stage.",
                "agentforce": "Agent Script: sequential actions with pass-through "
                              "output chaining.",
            },
            "consequences": ["+ per-stage observability and retry",
                             "- latency adds up across stages",
                             "- rigid ordering"],
            "governance_hooks": ["stage-boundary audit records",
                                 "policy gate between draft and publish stages"],
        }

    def _stages(self, item: WorkItem) -> list[str]:
        """Stage list for this item (task 101: latency is additive over
        stages, so stage count must follow the scenario's step count).

        Priority: an explicit ``stages`` list in the payload (S2 carries
        4-8 stages); else the payload's ``steps`` count maps onto the
        default stage prefix (S1 is single-step); else DEFAULT_STAGES.
        """
        if "stages" in item.payload:
            return list(item.payload["stages"])
        steps = int(item.payload.get("steps", len(DEFAULT_STAGES)))
        steps = max(1, min(steps, len(DEFAULT_STAGES)))
        return list(DEFAULT_STAGES[:steps])

    def _execute(self, item: WorkItem) -> WorkResult:
        stages = self._stages(item)
        try:
            if self.bedrock is not None:
                session = f"sess-{item.id}"
                carried = str(item.payload.get("task", item.id))
                outputs = []
                for stage in stages:
                    resp = self.bedrock.invoke_agent(f"agent-{stage}", "prod",
                                                     session, carried)
                    carried = resp["completion"]
                    outputs.append(carried)
                return WorkResult(item_id=item.id, status="ok",
                                  payload={"stages": stages, "final": carried,
                                           "n_steps": len(outputs)})
            assert self.agentforce is not None
            # Each stage is a model-backed agent step (Agent Script step =
            # topic dispatch with one model reasoning call + the stage
            # action), so latency is additive over model steps (task 101).
            carried: dict = {"item": item.id}
            for stage in stages:
                self.agentforce.register_action(
                    stage, lambda args, s=stage: {f"out_{s}": f"{s} complete",
                                                  "last_stage": s})
                self.agentforce.register_topic(f"stage_{stage}", [stage])
                carried = self.agentforce.send(f"stage_{stage}", carried)["result"]
            return WorkResult(item_id=item.id, status="ok",
                              payload={"stages": stages,
                                       "final": carried,
                                       "n_steps": len(stages)})
        except (BedrockClientError, AgentforceClientError) as exc:
            status = "timeout" if "timeout" in str(exc) else "error"
            return WorkResult(item_id=item.id, status=status, error=str(exc))
