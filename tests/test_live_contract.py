"""Contract tests: live clients must match the mock interface they replace.

The manuscript claims the mock boundary is "a single call-context seam" and
that swapping in a live client leaves the orchestration untouched. That claim
is only true while the live clients keep the mocks' exact method surface --
including argument NAMES, because the patterns call with keywords.

Nothing here touches the network or needs credentials; these run in the
ordinary offline suite so drift is caught before any spend.
"""
from __future__ import annotations

import ast
import inspect
import json
import re
from pathlib import Path

from agentorch.clients.bedrock import MockAgentCore, MockGuardrails

REPO = Path(__file__).resolve().parent.parent
SEAM_FIXTURE = Path(__file__).parent / "fixtures" / "seam_surface.json"


def assert_signature_compatible(mock_cls, live_cls, method: str) -> None:
    """A live client must accept the same parameters, by name and order.

    Name equality matters because the patterns call these with keywords; a
    live client that renamed a parameter would pass a presence check and then
    fail at runtime, inside a deployed container, mid-run.
    """
    mock_fn = getattr(mock_cls, method, None)
    live_fn = getattr(live_cls, method, None)
    assert mock_fn is not None, f"{mock_cls.__name__} has no {method}"
    assert live_fn is not None, (
        f"{live_cls.__name__} is missing {method}; the seam is broken")
    mp = [p for p in inspect.signature(mock_fn).parameters if p != "self"]
    lp = [p for p in inspect.signature(live_fn).parameters if p != "self"]
    assert mp == lp, (
        f"{method}: mock takes {mp}, live takes {lp} -- the patterns call "
        f"this with keywords, so the names must match")


SEAM_METHODS_AGENTCORE = ("gateway_call", "memory_get", "memory_put",
                          "observability_emit")


def test_mock_agentcore_exposes_the_seam_methods() -> None:
    """The four methods the patterns reach for beyond invoke_agent."""
    for name in SEAM_METHODS_AGENTCORE:
        assert callable(getattr(MockAgentCore, name, None)), \
            f"MockAgentCore lost {name}; the seam surface changed"


def test_mock_guardrails_exposes_apply() -> None:
    assert callable(getattr(MockGuardrails, "apply", None))


def test_existing_live_bedrock_client_matches_the_mock() -> None:
    """LiveBedrockAgentRuntime already backs the P1/P2 live runs."""
    import sys
    sys.path.insert(0, str(REPO))
    from anchor.agentcore.agent_released.agent_app import LiveBedrockAgentRuntime
    from agentorch.clients.bedrock import MockBedrockAgentRuntime
    assert_signature_compatible(MockBedrockAgentRuntime,
                                LiveBedrockAgentRuntime, "invoke_agent")


def _bedrock_branch_seam_calls(path: Path) -> set[str]:
    """Seam methods a pattern's Bedrock branch calls, read from its AST.

    Both branches are walked and the Agentforce-only clients filtered out,
    rather than trying to slice the `if self.bedrock is not None` block --
    the branch shape differs between patterns and a slicing heuristic would
    silently under-report.
    """
    tree = ast.parse(path.read_text())
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not isinstance(f, ast.Attribute):
            continue
        owner = f.value
        if (isinstance(owner, ast.Attribute) and isinstance(owner.value, ast.Name)
                and owner.value.id == "self"
                and owner.attr in ("bedrock", "agentcore", "guardrails")):
            found.add(f"{owner.attr}.{f.attr}")
    return found


def test_seam_fixture_covers_all_seven_patterns() -> None:
    fixture = json.loads(SEAM_FIXTURE.read_text())
    assert set(fixture) == {f"P{i}" for i in range(1, 8)}


def test_seam_fixture_matches_pattern_source() -> None:
    """The fixture is a reviewed baseline; drift shows up as a diff."""
    fixture = json.loads(SEAM_FIXTURE.read_text())
    pdir = REPO / "src" / "agentorch" / "patterns"
    files = {f"P{m.group(1)}": p
             for p in pdir.glob("p*.py")
             if (m := re.match(r"p(\d)_", p.name))}
    for pid, path in sorted(files.items()):
        actual = _bedrock_branch_seam_calls(path)
        expected = set(fixture[pid])
        assert actual == expected, (
            f"{pid} ({path.name}) seam surface drifted: "
            f"source has {sorted(actual)}, fixture has {sorted(expected)}")


def test_live_clients_never_call_boundary_call() -> None:
    """The rule that keeps the live and emulated timing models separate.

    ctx.boundary_call drives the virtual clock, the latency model and the
    fault injector. A live client invoking it would contaminate the
    deterministic study, so its absence is asserted rather than trusted.
    """
    src = (REPO / "anchor" / "agentcore" / "live_clients.py").read_text()
    # Parse rather than grep: the module docstring legitimately NAMES the rule
    # it is documenting, and a substring search would flag the explanation
    # while missing, say, getattr(ctx, "boundary_" + "call").
    tree = ast.parse(src)
    offenders = [n.attr for n in ast.walk(tree)
                 if isinstance(n, ast.Attribute) and n.attr == "boundary_call"]
    assert not offenders, \
        "a live client calls boundary_call; that contaminates the study"


def test_every_seam_method_is_signature_compatible() -> None:
    """Cover every method in the fixture, not just the interesting ones."""
    import sys
    sys.path.insert(0, str(REPO))
    from anchor.agentcore.live_clients import (LiveAgentCore, LiveGuardrails,
                                               LiveBedrockAgentRuntime)
    from agentorch.clients.bedrock import MockBedrockAgentRuntime
    mocks = {"bedrock": MockBedrockAgentRuntime, "agentcore": MockAgentCore,
             "guardrails": MockGuardrails}
    lives = {"bedrock": LiveBedrockAgentRuntime, "agentcore": LiveAgentCore,
             "guardrails": LiveGuardrails}
    fixture = json.loads(SEAM_FIXTURE.read_text())
    seen = set()
    for methods in fixture.values():
        for entry in methods:
            owner, method = entry.split(".")
            assert_signature_compatible(mocks[owner], lives[owner], method)
            seen.add(entry)
    assert len(seen) >= 6, f"expected the full seam surface, saw {sorted(seen)}"


def test_gateway_call_keeps_the_two_call_accounting() -> None:
    """P5's extra hop is its structural consequence; it must stay visible."""
    import sys
    sys.path.insert(0, str(REPO))
    from anchor.agentcore.live_clients import LiveAgentCore
    ac = LiveAgentCore()
    before = ac.service_calls
    ac.gateway_call("search", {"q": 1})
    assert ac.service_calls - before == 2, \
        "gateway hop plus tool call must count as two, as the mock does"


def test_memory_get_returns_none_for_a_missing_key() -> None:
    """P4 depends on the mock's contract; raising would change its flow."""
    import sys
    sys.path.insert(0, str(REPO))
    from anchor.agentcore.live_clients import LiveAgentCore
    assert LiveAgentCore().memory_get("absent") is None


def test_guardrails_rejects_an_invalid_mode() -> None:
    import sys
    import pytest
    sys.path.insert(0, str(REPO))
    from anchor.agentcore.live_clients import LiveGuardrails
    with pytest.raises(ValueError):
        LiveGuardrails().apply("x", mode="enforce")
