"""Provision the AWS resources the seven-pattern live run needs.

Three resources, each idempotent:
  * AgentCore Memory   -- P4's blackboard, and P6's paused-state store
  * AgentCore Gateway  -- P5's tool hop (plus one stand-in target)
  * Bedrock Guardrail  -- P6's shadow-mode check

Defaults to --dry-run. Creating these costs money and deletion is
irreversible, so the default has to be the safe one: a script whose default
mode spends is a script that will eventually spend by accident.

Deliberately does NOT reuse ``p7probe_mem-…``. That memory belongs to the P7
bridge probe whose records are cited in the manuscript; sharing it would make
the provenance of those records ambiguous.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

HERE = Path(__file__).resolve().parent
INVENTORY = HERE / "resources_all7.json"

MEMORY_NAME = "agentorch_all7_mem"
GATEWAY_NAME = "agentorch-all7-gw"
GUARDRAIL_NAME = "agentorch-all7-shadow"

# Rough, and labelled as rough. Real figures come from the console; this is
# here so the human approving the spend sees an order of magnitude.
COST_NOTE = """Estimated cost (order of magnitude, not a quote):
  AgentCore Memory    consumption-priced; a few hundred small put/get -> cents
  AgentCore Gateway   consumption-priced; ~450 tool calls           -> cents
  Bedrock Guardrail   ~$0.15 per 1k text units; ~60 applies          -> cents
  Nova Micro calls    ~1.5k invocations across seven patterns        -> <$1
  Runtimes + ECR      storage and idle, persists until retired       -> ~$0.20/mo
Total expected well under $5. Resources bill until explicitly retired."""


def _load_inventory() -> dict:
    if INVENTORY.exists():
        return json.loads(INVENTORY.read_text())
    return {}


def _save_inventory(inv: dict) -> None:
    INVENTORY.write_text(json.dumps(inv, indent=2) + "\n")


def ensure_memory(ctl, dry: bool, inv: dict) -> dict:
    existing = None
    for page in ctl.get_paginator("list_memories").paginate():
        for m in page.get("memories", []):
            name = m.get("name") or m.get("id", "")
            if name.startswith(MEMORY_NAME):
                existing = m
    if existing:
        print(f"  memory     EXISTS  {existing.get('id')}")
        return {"id": existing.get("id"), "arn": existing.get("arn"),
                "created": False}
    if dry:
        print(f"  memory     WOULD CREATE  {MEMORY_NAME}")
        return {"planned": MEMORY_NAME}
    r = ctl.create_memory(name=MEMORY_NAME,
                          description="agentorch all-seven live run (P4, P6)",
                          eventExpiryDuration=7)
    mem = r.get("memory", r)
    print(f"  memory     CREATED  {mem.get('id')}")
    return {"id": mem.get("id"), "arn": mem.get("arn"), "created": True}


def ensure_gateway(ctl, dry: bool, inv: dict, role_arn: str) -> dict:
    for page in ctl.get_paginator("list_gateways").paginate():
        for g in page.get("items", []):
            if g.get("name") == GATEWAY_NAME:
                print(f"  gateway    EXISTS  {g.get('gatewayId')}")
                return {"id": g.get("gatewayId"), "created": False}
    if dry:
        print(f"  gateway    WOULD CREATE  {GATEWAY_NAME} (+1 stand-in target)")
        return {"planned": GATEWAY_NAME}
    r = ctl.create_gateway(
        name=GATEWAY_NAME,
        roleArn=role_arn,
        protocolType="MCP",
        authorizerType="AWS_IAM",
        description="agentorch all-seven live run (P5 tool hop)")
    print(f"  gateway    CREATED  {r.get('gatewayId')}")
    return {"id": r.get("gatewayId"), "arn": r.get("gatewayArn"),
            "url": r.get("gatewayUrl"), "created": True}


def ensure_guardrail(br, dry: bool, inv: dict) -> dict:
    for g in br.list_guardrails(maxResults=100).get("guardrails", []):
        if g.get("name") == GUARDRAIL_NAME:
            print(f"  guardrail  EXISTS  {g.get('id')}")
            return {"id": g.get("id"), "version": g.get("version"),
                    "created": False}
    if dry:
        print(f"  guardrail  WOULD CREATE  {GUARDRAIL_NAME} (shadow, non-blocking)")
        return {"planned": GUARDRAIL_NAME}
    # NONE actions everywhere: P6 calls apply(mode="shadow") and its claim is
    # about the human adjudication step, not about guardrail enforcement.
    r = br.create_guardrail(
        name=GUARDRAIL_NAME,
        description="agentorch all-seven live run (P6 shadow check)",
        contentPolicyConfig={"filtersConfig": [
            {"type": "VIOLENCE", "inputStrength": "LOW",
             "outputStrength": "NONE"}]},
        blockedInputMessaging="shadow",
        blockedOutputsMessaging="shadow",
    )
    print(f"  guardrail  CREATED  {r.get('guardrailId')} v{r.get('version')}")
    return {"id": r.get("guardrailId"), "arn": r.get("guardrailArn"),
            "version": r.get("version"), "created": True}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--role-arn",
                    default="arn:aws:iam::111789566955:role/"
                            "AmazonBedrockAgentCoreSDKRuntime-us-east-1-861e6a5a2b")
    ap.add_argument("--dry-run", action="store_true", default=True,
                    help="default; shows what would be created")
    ap.add_argument("--execute", dest="dry_run", action="store_false",
                    help="actually create resources (HUMAN-APPROVED ONLY)")
    a = ap.parse_args(argv)

    mode = "DRY RUN — nothing will be created" if a.dry_run else "EXECUTING"
    print(f"provision_all7 [{mode}] region={a.region}\n")

    ctl = boto3.client("bedrock-agentcore-control", region_name=a.region)
    br = boto3.client("bedrock", region_name=a.region)
    inv = _load_inventory()

    try:
        inv["memory"] = ensure_memory(ctl, a.dry_run, inv)
        inv["gateway"] = ensure_gateway(ctl, a.dry_run, inv, a.role_arn)
        inv["guardrail"] = ensure_guardrail(br, a.dry_run, inv)
    except ClientError as exc:
        print(f"\nAWS refused: {exc.response['Error']['Code']}: "
              f"{exc.response['Error']['Message'][:200]}")
        return 1

    if a.dry_run:
        print("\n" + COST_NOTE)
        print("\nNothing was created. Re-run with --execute after approval.")
        return 0

    inv["region"] = a.region
    _save_inventory(inv)
    print(f"\nwrote {INVENTORY.name}")
    print("These resources BILL until retired. Retire via TASK 079.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
