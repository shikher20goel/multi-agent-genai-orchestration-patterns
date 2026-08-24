"""Deploy the RELEASED agentorch pattern modules onto AgentCore Runtime.

Separate runtimes from the hand-written anchor agents (anchorp1/anchorp2),
so the timing results those produced keep their exact provenance and this
deployment answers a different question: does the released implementation
itself run on a real hyperscaler agent runtime?

The image is built from the repository root because it ships src/ and
configs/ as committed.

Usage:
    python anchor/agentcore/deploy_released.py --region us-east-1 \
        --copy-role-from p7probe --tag v1
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import boto3

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
AGENT_DIR = HERE / "agent_released"
RUNTIMES_FILE = HERE / "runtimes_released.json"

_spec = importlib.util.spec_from_file_location(
    "_deploy_agentcore", HERE / "deploy_agentcore.py")
_dep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_dep)

REPO_NAME = "anchor-agentcore-released"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--role-arn")
    ap.add_argument("--copy-role-from", default="p7probe")
    ap.add_argument("--model-id", default="us.amazon.nova-micro-v1:0")
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--skip-build", action="store_true")
    a = ap.parse_args(argv)

    account = boto3.client("sts").get_caller_identity()["Account"]
    ecr = boto3.client("ecr", region_name=a.region)
    ac_ctl = boto3.client("bedrock-agentcore-control", region_name=a.region)
    role_arn = a.role_arn or _dep.role_of(ac_ctl, a.copy_role_from)

    _dep.REPO_NAME, _dep.IMAGE_TAG = REPO_NAME, a.tag
    image_uri = _dep.ensure_ecr(ecr, account, a.region)
    if not a.skip_build:
        _dep.docker_login(ecr, account, a.region)
        _dep.build_and_push(image_uri, context=REPO_ROOT,
                            dockerfile=AGENT_DIR / "Dockerfile")

    common = {"ANCHOR_MODEL_ID": a.model_id, "ANCHOR_MODEL_REGION": a.region}
    out = {"region": a.region, "image_uri": image_uri, "role_arn": role_arn,
           "model_id": a.model_id, "runtimes": {}}
    out["runtimes"]["P1"] = _dep.upsert(
        ac_ctl, "anchorp1rel", image_uri, role_arn,
        {**common, "ANCHOR_PATTERN": "P1"})
    out["runtimes"]["P2"] = _dep.upsert(
        ac_ctl, "anchorp2rel", image_uri, role_arn,
        {**common, "ANCHOR_PATTERN": "P2"})
    RUNTIMES_FILE.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
