"""P1 Supervisor-Collaborator Hierarchy (task 016).

A supervisor agent decomposes the work item, fans tasks out to N
collaborator agents, and synthesizes their outputs. Bedrock
instantiation: supervisor + collaborators are separate agent runtimes
invoked via ``invoke_agent``. Agentforce instantiation: the supervisor
is a topic whose actions are the collaborator agents, plus an explicit
synthesis model call.
"""
from __future__ import annotations

from typing import Any

from agentorch.clients.agentforce import AgentforceClientError
from agentorch.clients.bedrock import BedrockClientError
from agentorch.domain import Agent, WorkItem, WorkResult
from agentorch.patterns.base import Pattern


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
        plan = self.bedrock.invoke_agent("supervisor", "prod", session,
                                         f"plan: {task}")
        parts = []
        for agent in self._collaborators():
            sub = self.bedrock.invoke_agent(agent.id, "prod", session,
                                            f"subtask for {agent.role}: {task}")
            parts.append(sub["completion"])
        synthesis = self.bedrock.invoke_agent("supervisor", "prod", session,
                                              f"synthesize: {' | '.join(parts)}")
        return WorkResult(item_id=item.id, status="ok",
                          payload={"plan": plan["completion"],
                                   "answer": synthesis["completion"],
                                   "n_collaborators": len(parts)})

    def _execute_agentforce(self, item: WorkItem, task: str) -> WorkResult:
        assert self.agentforce is not None
        af = self.agentforce
        collaborators = self._collaborators()
        for agent in collaborators:
            af.register_action(agent.id,
                               lambda args, a=agent: {f"part_{a.id}": f"{a.role} done"})
        topic = "supervised_work"
        af.register_topic(topic, [a.id for a in collaborators])
        routed = af.send(topic, {"task": task})
        return WorkResult(item_id=item.id, status="ok",
                          payload={"answer": routed["result"],
                                   "n_collaborators": len(collaborators)})
