"""Probe every provisioned resource read-only before anything depends on it.

IAM propagation is not immediate: the released-module deployment was denied
on first attempt and succeeded 30 seconds later. So a first AccessDenied is
retried, and a persistent one is reported as a real failure rather than
waited out forever.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

HERE = Path(__file__).resolve().parent
INVENTORY = HERE / "resources_all7.json"


def probe(label: str, fn, deadline: float) -> tuple[bool, str]:
    last = ""
    while time.time() < deadline:
        try:
            fn()
            return True, "reachable"
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            last = f"{code}: {exc.response['Error']['Message'][:110]}"
            if code not in ("AccessDeniedException", "AccessDenied",
                            "ResourceNotFoundException", "ValidationException"):
                return False, last
            time.sleep(10)
        except Exception as exc:              # noqa: BLE001
            last = f"{type(exc).__name__}: {str(exc)[:110]}"
            time.sleep(10)
    return False, last or "timed out"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args(argv)

    inv = json.loads(INVENTORY.read_text())
    region = inv.get("region", "us-east-1")
    ctl = boto3.client("bedrock-agentcore-control", region_name=region)
    br = boto3.client("bedrock", region_name=region)
    logs = boto3.client("logs", region_name=region)
    deadline = time.time() + a.timeout

    checks = [
        ("memory", lambda: ctl.get_memory(memoryId=inv["memory"]["id"])),
        ("gateway", lambda: ctl.get_gateway(gatewayIdentifier=inv["gateway"]["id"])),
        ("guardrail", lambda: br.get_guardrail(
            guardrailIdentifier=inv["guardrail"]["id"],
            guardrailVersion=str(inv["guardrail"].get("version", "DRAFT")))),
        ("logs", lambda: logs.describe_log_groups(
            logGroupNamePrefix="/agentorch/all7")),
    ]
    ok = True
    for label, fn in checks:
        good, detail = probe(label, fn, deadline)
        ok &= good
        print(f"  {label:<11}{'OK  ' if good else 'FAIL'}  {detail}")
    print("\nall reachable" if ok else "\nNOT all reachable")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
