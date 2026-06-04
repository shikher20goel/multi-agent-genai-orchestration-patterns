"""P1 Supervisor-Collaborator Hierarchy (task 016; latency task 101).

A supervisor agent decomposes the work item, fans tasks out to N
collaborator agents IN PARALLEL, and synthesizes their outputs, so the
end-to-end service time is

    plan + max(collaborator latencies) + synthesis.

The parallel fan-out makes P1's tail follow the *tail-at-scale* result
(Dean & Barroso, "The Tail at Scale", CACM 56(2), 2013): the request
waits for the SLOWEST collaborator, so p95/p99 worsen as the fan-out k
grows even when each collaborator's marginal distribution is unchanged.

Bedrock instantiation: supervisor + collaborators are separate agent
runtimes invoked via ``invoke_agent``. Agentforce instantiation: the
supervisor topic plans, each collaborator agent is a model-backed
action invoked in parallel, and a closing model call synthesizes.
"""
from __future__ import annotations

from typing import Any

from agentorch.clients.agentforce import AgentforceClientError
from agentorch.clients.bedrock import BedrockClientError
from agentorch.domain import Agent, WorkItem, WorkResult
from agentorch.patterns.base import Pattern, work_steps


class SupervisorPattern(Pattern):
    pattern_name = "P1 Supervisor-Collaborator Hierarchy"

    @classmethod
    def meta(cls) -> dict[str, Any]:
        return {
            "name": cls.pattern_name,
            "intent": "Centralize task decomposition and result synthesis in a "
                      "supervisor that delegates subtasks to specialist collaborators.",
            "context": "A request needs heterogeneous skills (retrieval, drafting, "
                       "validation) coordinated toward one answer.",
            "problem": "A single monolithic agent overloads one prompt/context and "
                       "cannot specialize or parallelize subtasks.",
            "forces": ["specialization vs coordination overhead",
                       "single point of control vs single point of failure",
                       "latency of fan-out vs answer quality"],
            "solution": "Supervisor plans, dispatches subtasks to collaborators, "
                        "and synthesizes a final answer from their results.",
            "platform_instantiations": {
                "bedrock": "Supervisor and collaborators as separate Bedrock agents; "
                           "supervisor calls invoke_agent per collaborator.",
                "agentforce": "Supervisor as a topic whose registered actions are "
                              "collaborator agents; synthesis via a closing model call.",
            },
            "consequences": ["+ specialization, + observability of subtasks",
                             "- supervisor is a bottleneck and SPOF",
                             "- added latency per delegation hop"],
            "governance_hooks": ["per-collaborator audit of inputs/outputs",
                                 "supervisor-level policy check before synthesis"],
        }

    def _collaborators(self) -> list[Agent]:
        n = int(self.cfg.patterns.p1.n_collaborators)
        return [Agent(id=f"collab-{i}", role=f"specialist-{i}") for i in range(n)]

    def _steps_per_branch(self, item: WorkItem) -> int:
        """Each collaborator branch handles its share of the item's
        scenario steps SEQUENTIALLY within the parallel fan-out
        (task 105): a multi-step item costs more model work per branch."""
        k = max(1, int(self.cfg.patterns.p1.n_collaborators))
        return -(-work_steps(item) // k)  # ceil division

    def _execute(self, item: WorkItem) -> WorkResult:
        task = str(item.payload.get("task", item.id))
        try:
            if self.bedrock is not None:
                return self._execute_bedrock(item, task)
            return self._execute_agentforce(item, task)
        except (BedrockClientError, AgentforceClientError) as exc:
            status = "timeout" if "timeout" in str(exc) else "error"
            return WorkResult(item_id=item.id, status=status, error=str(exc))

    def _execute_bedrock(self, item: WorkItem, task: str) -> WorkResult:
        assert self.bedrock is not None
        session = f"sess-{item.id}"
        # Plan step (supervisor model call).
        plan = self.bedrock.invoke_agent("supervisor", "prod", session,
                                         f"plan: {task}")

        # Parallel fan-out: the request pays max(collaborators), not the
        # sum (tail-at-scale; Dean & Barroso 2013).
        per_branch = self._steps_per_branch(item)

        def make_branch(agent: Agent):
            def branch():
                outs = []
                for j in range(per_branch):
                    outs.append(self.bedrock.invoke_agent(
                        agent.id, "prod", session,
                        f"subtask {j} for {agent.role}: {task}")["completion"])
                return " ".join(outs)
            return branch

        parts = self._parallel([make_branch(a) for a in self._collaborators()])
        # Synthesis covers the full multi-step content (task 105).
        self.ctx.content_scale = work_steps(item)
        synthesis = self.bedrock.invoke_agent("supervisor", "prod", session,
                                              f"synthesize: {' | '.join(parts)}")
        self.ctx.content_scale = 1.0
        return WorkResult(item_id=item.id, status="ok",
                          payload={"plan": plan["completion"],
                                   "answer": synthesis["completion"],
                                   "n_collaborators": len(parts)})

    def _execute_agentforce(self, item: WorkItem, task: str) -> WorkResult:
        assert self.agentforce is not None
        af = self.agentforce
        collaborators = self._collaborators()
        # Supervisor plan: one model-backed topic dispatch.
        af.register_topic("supervise_plan", [])
        af.send("supervise_plan", {"task": task})

        # Parallel fan-out to model-backed collaborator agents
        # (tail-at-scale accounting: request pays the slowest one).
        for agent in collaborators:
            af.register_action(agent.id,
                               lambda args, a=agent: {f"part_{a.id}": f"{a.role} done"})
            af.register_topic(f"collab_{agent.id}", [agent.id])

        per_branch = self._steps_per_branch(item)

        def make_branch(agent: Agent):
            def branch():
                outs = []
                for j in range(per_branch):
                    outs.append(af.send(f"collab_{agent.id}",
                                        {"task": task, "step": j})["result"])
                return outs[-1]
            return branch

        parts = self._parallel([make_branch(a) for a in collaborators])
        # Synthesis: closing supervisor model call covering all steps.
        af.register_topic("supervise_synthesize", [])
        self.ctx.content_scale = work_steps(item)
        synthesis = af.send("supervise_synthesize", {"parts": len(parts)})
        self.ctx.content_scale = 1.0
        return WorkResult(item_id=item.id, status="ok",
                          payload={"answer": synthesis["result"],
                                   "n_collaborators": len(collaborators)})
