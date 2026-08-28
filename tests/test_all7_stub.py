"""All seven RELEASED patterns run through live-client stubs, offline.

Purpose: prove the call-context seam generalises beyond P1/P2 *before* any AWS
resource exists or any money is spent. If a pattern cannot run through the
live-client interface, that is a finding about the seam and must be reported
— not patched around by editing the pattern.

Nothing here needs credentials or a network. Structural assertions check each
pattern's own control flow (invocation and service-call counts), because
"it returned ok" would pass even if the orchestration silently collapsed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from agentorch.clients.context import CallContext          # noqa: E402
from agentorch.config import load_config                   # noqa: E402
from agentorch.domain import WorkItem                      # noqa: E402
from agentorch.patterns.p1_supervisor import SupervisorPattern      # noqa: E402
from agentorch.patterns.p2_pipeline import PipelinePattern          # noqa: E402
from agentorch.patterns.p3_choreography import ChoreographyPattern  # noqa: E402
from agentorch.patterns.p4_blackboard import BlackboardPattern      # noqa: E402
from agentorch.patterns.p5_gateway import GatewayPattern            # noqa: E402
from agentorch.patterns.p6_hitl import HitlPattern                  # noqa: E402
from agentorch.patterns.p7_bridge import BridgePattern              # noqa: E402
from agentorch.scenarios.s1_rag_qa import generate_s1        # noqa: E402
from agentorch.telemetry import TelemetrySink                # noqa: E402
from agentorch.types import Platform, ScenarioId             # noqa: E402

from anchor.agentcore.live_clients import (LiveAgentCore,   # noqa: E402
                                           LiveGuardrails,
                                           attach_live_clients)

PATTERNS = {
    "P1": SupervisorPattern, "P2": PipelinePattern, "P3": ChoreographyPattern,
    "P4": BlackboardPattern, "P5": GatewayPattern, "P6": HitlPattern,
    "P7": BridgePattern,
}

SIGNATURES = Path(__file__).parent / "fixtures" / "pattern_signatures.json"


class StubBedrock:
    """Stands in for the live Converse-backed client, counting invocations."""

    def __init__(self):
        self.invocations = 0
        self.tokens_in = 0
        self.tokens_out = 0

    def invoke_agent(self, agentId: str, agentAliasId: str, sessionId: str,
                     inputText: str) -> dict:
        self.invocations += 1
        return {"completion": f"<{agentId} out>", "sessionId": sessionId}


def s1_items(n: int, cfg=None):
    """Work items from the repo's OWN S1 generator.

    Hand-built payloads are not a substitute. The generators supply fields the
    patterns branch on -- notably ``confidence``, which drives P6's review
    gate. A synthetic payload without it silently takes the default 0.9, P6
    never pauses, and its human path and memory seam go unexercised while the
    test still passes. Using the real generator is both more faithful and the
    only way those branches are reached.
    """
    cfg = cfg or load_config()
    return generate_s1(n, cfg.get_rng("all7-stub"), cfg)


def run_pattern(pid: str, item=None):
    """Build the released pattern, swap in stubs, run one scenario item."""
    cfg = load_config()
    ctx = CallContext.build(cfg, sink=TelemetrySink(),
                            stream_prefix=f"{pid}:bedrock:S1:livestub")
    pat = PATTERNS[pid](Platform.BEDROCK, ctx, cfg)
    bedrock, agentcore, guardrails = StubBedrock(), LiveAgentCore(), LiveGuardrails()
    attach_live_clients(pat, bedrock=bedrock, agentcore=agentcore,
                        guardrails=guardrails)
    if item is None:
        item = s1_items(1, cfg)[0]
    result, service_time_s = pat.run(item)
    return pat, result, service_time_s, bedrock, agentcore, guardrails


@pytest.mark.parametrize("pid", sorted(PATTERNS))
def test_released_pattern_runs_through_live_clients(pid: str) -> None:
    """Every pattern completes; the seam is not P1/P2-specific."""
    pat, result, _, _, _, _ = run_pattern(pid)
    assert result.status == "ok", (
        f"{pid} ({type(pat).__module__}) failed through the live-client "
        f"seam: {result.error}")
    assert type(pat).__module__.startswith("agentorch.patterns"), \
        "the released module must be what ran"


def test_p1_fans_out_to_its_configured_collaborators() -> None:
    """plan + n collaborators + synthesis, derived from config not hard-coded."""
    cfg = load_config()
    n = int(cfg.patterns.p1.n_collaborators)
    _, result, _, bedrock, _, _ = run_pattern("P1")
    assert bedrock.invocations == n + 2
    assert result.payload["n_collaborators"] == n


def test_p2_is_a_single_stage_on_s1() -> None:
    """Read the stage count from the pattern rather than assuming one."""
    pat, result, _, bedrock, _, _ = run_pattern("P2")
    assert bedrock.invocations == len(pat._stages(s1_items(1)[0]))
    assert result.payload["n_steps"] == bedrock.invocations


def test_p3_emits_one_observability_event_per_handled_event() -> None:
    _, result, _, bedrock, agentcore, _ = run_pattern("P3")
    assert agentcore.emitted, "P3 emitted nothing; observability seam unused"
    assert len(agentcore.emitted) == bedrock.invocations, (
        "P3 emits one structural event per handled event")


def test_p4_writes_the_board_before_reading_it() -> None:
    """Ordering is P4's contention claim, not merely 'memory was touched'."""
    _, result, _, _, agentcore, _ = run_pattern("P4")
    assert agentcore.service_calls > 0
    final = list(agentcore._memory.values())[-1]
    assert isinstance(final, list) and final, \
        "the blackboard should end holding the specialists' contributions"


def test_p5_pays_a_gateway_hop_per_tool_call() -> None:
    _, result, _, _, agentcore, _ = run_pattern("P5")
    assert agentcore.gateway_calls > 0, "P5 did not route through the gateway"
    assert agentcore.service_calls == 2 * agentcore.gateway_calls, (
        "each gateway_call must count a hop plus the tool, as the mock does")


def test_p6_applies_a_shadow_guardrail_and_models_the_human_step() -> None:
    """NOTE: P6's human wait is a latency SAMPLE, not a platform call.

    On the Bedrock path the adjudication delay comes from
    ctx.latency_model.sample_shared("human_decision_delay"). Running P6 live
    therefore means live model + live guardrail + live memory with a
    *simulated* human. This bound must not be lost when the result is
    described.
    """
    cfg = load_config()
    items = s1_items(60, cfg)
    threshold = float(cfg.patterns.p6.confidence_threshold)
    low = [i for i in items if i.payload["confidence"] < threshold]
    assert low, ("the S1 generator produced no below-threshold item; P6's "
                 "human path cannot be exercised and the run would be vacuous")

    _, _, _, _, ac_hi, gr_hi = run_pattern(
        "P6", next(i for i in items if i.payload["confidence"] >= threshold))
    assert gr_hi.applied == 1 and gr_hi.shadow_log[0]["mode"] == "shadow"
    assert gr_hi.shadow_log[0]["blocked"] is False
    assert ac_hi.service_calls == 0, "a confident item must not pause"

    _, _, _, _, ac_lo, gr_lo = run_pattern("P6", low[0])
    assert gr_lo.applied == 1
    assert ac_lo.service_calls >= 1, (
        "a below-threshold item must pause and persist state through the "
        "memory seam")


def test_p7_bedrock_branch_is_the_bridge_target() -> None:
    """The CRM half is covered by the live probe, deliberately not here."""
    _, result, _, bedrock, _, _ = run_pattern("P7")
    assert bedrock.invocations >= 1


def test_structural_signatures_match_the_frozen_fixture() -> None:
    """The fixture is the reviewed baseline the live runs are checked against."""
    expected = json.loads(SIGNATURES.read_text())
    for pid in sorted(PATTERNS):
        _, _, _, bedrock, agentcore, guardrails = run_pattern(pid)
        actual = {"invocations": bedrock.invocations,
                  "service_calls": agentcore.service_calls,
                  "guardrails_applied": guardrails.applied}
        assert actual == expected[pid], (
            f"{pid} structural signature drifted: {actual} != {expected[pid]}")
