"""P7 Federated Cross-Platform Bridge (task 022; latency task 101).

Every federated call pays one cross-platform round trip
(``latency.shared.cross_platform_rtt``) at the bridge, on top of the
local-cluster service time.

Work spans two platform clusters joined by a bridge; a full outage of
one cluster is contained — work for the healthy cluster still completes
and cross-cluster work degrades gracefully instead of cascading.
Instantiations: primary=Bedrock bridging to an Agentforce cluster, and
primary=Agentforce bridging to a Bedrock cluster.
"""
from __future__ import annotations

from typing import Any

from agentorch.clients.agentforce import (
    AgentforceClientError,
    MockAgentforceClient,
)
from agentorch.clients.bedrock import (
    BedrockClientError,
    MockBedrockAgentRuntime,
)
from agentorch.clients.context import CallContext
from agentorch.config import Config
from agentorch.domain import WorkItem, WorkResult
from agentorch.patterns.base import Pattern
from agentorch.types import Platform


class BridgePattern(Pattern):
    pattern_name = "P7 Federated Cross-Platform Bridge"

    def __init__(self, platform: Platform, ctx: CallContext, cfg: Config):
        super().__init__(platform, ctx, cfg)
        # Remote cluster on the *other* platform with its own fault domain
        # (separate CallContext sharing the same virtual clock).
        remote_platform = (Platform.AGENTFORCE if platform is Platform.BEDROCK
                           else Platform.BEDROCK)
        self.remote_platform = remote_platform
        # Remote cluster: independent latency stream (task 103 prefix is
        # inherited via the primary ctx builder in run_condition), shared
        # fault injector so the campaign can arm a REMOTE-CLUSTER outage
        # with unit="remote" (task 104) — local calls carry no unit and
        # are unaffected by remote-only faults.
        self.remote_ctx = CallContext.build(
            cfg, clock=ctx.clock, sink=ctx.sink,
            stream_prefix=getattr(ctx, "stream_prefix", "") + ":remote",
            fault_injector=ctx.fault_injector)
        self.remote_ctx.default_unit = "remote"
        if remote_platform is Platform.BEDROCK:
            self.remote_bedrock: MockBedrockAgentRuntime | None = (
                MockBedrockAgentRuntime(self.remote_ctx))
            self.remote_agentforce: MockAgentforceClient | None = None
        else:
            self.remote_bedrock = None
            self.remote_agentforce = MockAgentforceClient(self.remote_ctx)
            self.remote_agentforce.register_action("remote_work")
            self.remote_agentforce.register_topic("bridge", ["remote_work"])

    @classmethod
    def meta(cls) -> dict[str, Any]:
        return {
            "name": cls.pattern_name,
            "intent": "Federate agent work across heterogeneous platform clusters "
                      "through an explicit bridge with outage containment.",
            "context": "Enterprises run CRM-native agents (Agentforce) and "
                       "cloud-native agents (Bedrock) that must cooperate.",
            "problem": "Point-to-point coupling lets one platform's outage cascade "
                       "into the other and hides cross-platform data flows.",
            "forces": ["federation reach vs added bridge latency",
                       "independent fault domains vs duplicated tooling",
                       "consistency across heterogeneous semantics"],
            "solution": "A bridge component mediates cross-cluster calls; each "
                        "cluster keeps an independent fault domain; remote-cluster "
                        "outage degrades only the federated portion.",
            "platform_instantiations": {
                "bedrock": "Primary Bedrock cluster bridging into an Agentforce "
                           "cluster via the bridge hop.",
                "agentforce": "Primary Agentforce cluster bridging into a Bedrock "
                              "cluster via the bridge hop.",
            },
            "consequences": ["+ outage containment across clusters",
                             "- bridge hop latency on federated calls",
                             "- dual-platform operational surface"],
            "governance_hooks": ["bridge-level data-transfer audit",
                                 "per-cluster policy enforcement"],
        }

    def _local_work(self, item: WorkItem) -> str:
        if self.bedrock is not None:
            return self.bedrock.invoke_agent(
                "local", "prod", f"sess-{item.id}",
                str(item.payload.get("task", item.id)))["completion"]
        assert self.agentforce is not None
        self.agentforce.register_action("local_work")
        self.agentforce.register_topic("local", ["local_work"])
        return str(self.agentforce.send("local", {"item": item.id})["result"])

    def _bridge_hop(self) -> None:
        """Cross-platform RTT term (task 101): every federated call pays
        one bridge round trip (latency.shared.cross_platform_rtt)."""
        self.ctx.add_delay(
            self.ctx.latency_model.sample_shared("cross_platform_rtt"))

    def _remote_work(self, item: WorkItem) -> str:
        if self.remote_bedrock is not None:
            return self.remote_bedrock.invoke_agent(
                "remote", "prod", f"sess-{item.id}", "federated subtask")["completion"]
        assert self.remote_agentforce is not None
        return str(self.remote_agentforce.send("bridge", {"item": item.id})["result"])

    def _execute(self, item: WorkItem) -> WorkResult:
        # Track remote-cluster service time and fold it into this request's
        # accounting (the bridge waits on the federated call).
        remote_start = self.remote_ctx.elapsed_s
        # Local cluster work: must succeed for the request to succeed.
        try:
            local = self._local_work(item)
        except (BedrockClientError, AgentforceClientError) as exc:
            status = "timeout" if "timeout" in str(exc) else "error"
            return WorkResult(item_id=item.id, status=status, error=str(exc))
        # Federated work through the bridge: remote outage is contained —
        # the request degrades (no remote enrichment) but still completes.
        remote: str | None = None
        remote_error: str | None = None
        self._bridge_hop()
        try:
            remote = self._remote_work(item)
        except (BedrockClientError, AgentforceClientError) as exc:
            remote_error = str(exc)
        self.ctx.elapsed_s += self.remote_ctx.elapsed_s - remote_start
        if remote is None:
            # Task 104: remote-cluster outage is CONTAINED to the bridged
            # work — the request completes degraded, never cascades.
            self.ctx.degraded = True
        return WorkResult(item_id=item.id, status="ok",
                          payload={"local": local, "remote": remote,
                                   "degraded": remote is None,
                                   "remote_error": remote_error})
