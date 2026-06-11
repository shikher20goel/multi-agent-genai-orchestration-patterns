"""P5 Tool-Routed Gateway with bulkhead isolation (task 020).

All tool calls go through a gateway; each tool sits behind its own
bulkhead so one tool's fault cannot take down the others. Bedrock
instantiation: AgentCore gateway_call. Agentforce instantiation: actions
as gated tools.
"""
from __future__ import annotations

from typing import Any

from agentorch.clients.agentforce import AgentforceClientError
from agentorch.clients.bedrock import BedrockClientError
from agentorch.domain import WorkItem, WorkResult
from agentorch.patterns.base import Pattern, work_steps


class GatewayPattern(Pattern):
    pattern_name = "P5 Tool-Routed Gateway"

    @classmethod
    def meta(cls) -> dict[str, Any]:
        return {
            "name": cls.pattern_name,
            "intent": "Route every tool invocation through a governed gateway with "
                      "per-tool bulkheads so faults stay contained.",
            "context": "Agents call many heterogeneous tools with differing "
                       "reliability and security profiles.",
            "problem": "Direct tool wiring spreads credentials and lets one flaky "
                       "tool degrade the whole agent.",
            "forces": ["central governance vs extra hop latency",
                       "bulkhead isolation vs resource duplication",
                       "uniform policy vs per-tool flexibility"],
            "solution": "A gateway mediates all tool calls; each tool runs behind a "
                        "bulkhead; a failed tool yields a per-tool error, not a "
                        "request-wide crash.",
            "platform_instantiations": {
                "bedrock": "AgentCore gateway_call(tool, args) adds the governed "
                           "hop; tool faults surface per call.",
                "agentforce": "Registered actions as gated tools; per-action error "
                              "containment in the dispatch loop.",
            },
            "consequences": ["+ blast-radius containment, + single policy point",
                             "- one extra hop on every tool call",
                             "- gateway availability is critical"],
            "governance_hooks": ["gateway-level allowlist and audit",
                                 "per-tool rate/identity policy"],
        }

    def _tools(self) -> list[str]:
        return list(self.cfg.patterns.p5.tools)

    def _execute(self, item: WorkItem) -> WorkResult:
        tools = self._tools()
        tool_results: dict[str, Any] = {}
        failures: dict[str, str] = {}
        # Task 105: every scenario step needs a routed tool execution, so
        # the tool-call list is one full pass over the tool set, extended
        # round-robin to cover multi-step items (S2 costs more per request
        # than S1 on both platforms: tokens on Bedrock, Flex-credit
        # actions on Agentforce).
        steps = work_steps(item)
        n_calls = max(len(tools), steps)
        calls = [tools[j % len(tools)] for j in range(n_calls)]
        try:
            # Initial reasoning step that decides which tools to call;
            # its plan covers the item's full multi-step content.
            if self.bedrock is not None:
                self.ctx.content_scale = steps
                self.bedrock.invoke_agent("router", "prod", f"sess-{item.id}",
                                          f"plan tools for {item.id}")
                self.ctx.content_scale = 1.0
            else:
                assert self.agentforce is not None
                for t in tools:
                    self.agentforce.register_action(f"tool_{t}",
                                                    lambda a, t=t: {"tool": t, "ok": True})
                self.agentforce.register_topic("route", [])
                self.ctx.content_scale = steps
                self.agentforce.send("route", {"item": item.id})
                self.ctx.content_scale = 1.0
        except (BedrockClientError, AgentforceClientError) as exc:
            status = "timeout" if "timeout" in str(exc) else "error"
            return WorkResult(item_id=item.id, status=status, error=str(exc))

        # Bulkhead: each tool call is individually guarded; one tool's fault
        # is contained and the loop continues with the remaining tools.
        for j, tool in enumerate(calls):
            try:
                if self.agentcore is not None:
                    res = self.agentcore.gateway_call(tool, {"item": item.id,
                                                             "step": j})
                else:
                    assert self.agentforce is not None
                    res = self.agentforce.run_agent_script(
                        [{"action": f"tool_{tool}"}])[0]
                tool_results[tool] = res
            except (BedrockClientError, AgentforceClientError) as exc:
                failures[tool] = str(exc)

        all_failed = len(failures) == len(set(calls))
        status = "error" if all_failed else "ok"
        if failures and not all_failed:
            # Bulkhead isolation (task 104): the request completes but the
            # faulted tool's contribution is lost — degraded, not failed.
            self.ctx.degraded = True
        return WorkResult(item_id=item.id, status=status,
                          payload={"tools_ok": sorted(tool_results),
                                   "tools_failed": sorted(failures),
                                   "degraded": bool(failures and not all_failed)},
                          error="; ".join(failures.values()) or None)
