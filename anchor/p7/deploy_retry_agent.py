"""Build and deploy the C3/C4 retry-probe agent onto AgentCore Runtime.

Deploys to a NEW runtime (default name ``p7retry``) rather than updating
the ``p7probe`` runtime C1/C2 ran against. Overwriting that deployment
would leave the committed C1/C2 records pointing at code they were not
produced by, which is exactly the kind of provenance the manuscript
claims to have.

Writes the resulting ARN back into the probe config, so the ARN is never
hand-typed into a file a result depends on.

Usage:
    python anchor/p7/deploy_retry_agent.py --region us-east-1 \
        --copy-role-from p7probe
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import boto3
import yaml

HERE = Path(__file__).resolve().parent
AGENT_DIR = HERE / "agent_retry"
CONFIG = HERE / "p7_retry_config.yaml"

# Reuse the anchor deployer's ECR/build/upsert helpers rather than forking
# them: one build path means one place for a build bug to live.
_spec = importlib.util.spec_from_file_location(
    "_deploy_agentcore", HERE.parent / "agentcore" / "deploy_agentcore.py")
_dep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_dep)

REPO_NAME = "p7-retry-agent"
IMAGE_TAG = "v1"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--role-arn")
    ap.add_argument("--copy-role-from", default="p7probe")
    ap.add_argument("--runtime-name", default="p7retry")
    # A rebuilt agent MUST get a new tag: updating a runtime while reusing
    # a tag can leave it serving the cached image, and the run would then
    # silently measure the old code.
    ap.add_argument("--tag", default=IMAGE_TAG)
    ap.add_argument("--skip-build", action="store_true")
    a = ap.parse_args(argv)

    account = boto3.client("sts").get_caller_identity()["Account"]
    ecr = boto3.client("ecr", region_name=a.region)
    ac_ctl = boto3.client("bedrock-agentcore-control", region_name=a.region)

    role_arn = a.role_arn or _dep.role_of(ac_ctl, a.copy_role_from)

    _dep.REPO_NAME, _dep.IMAGE_TAG = REPO_NAME, a.tag
    _dep.AGENT_DIR = AGENT_DIR
    image_uri = _dep.ensure_ecr(ecr, account, a.region)
    if not a.skip_build:
        _dep.docker_login(ecr, account, a.region)
        _dep.build_and_push(image_uri)

    arn = _dep.upsert(ac_ctl, a.runtime_name, image_uri, role_arn, {})

    cfg_text = CONFIG.read_text()
    cfg = yaml.safe_load(cfg_text)
    old = cfg.get("retry_agent_runtime_arn", "")
    CONFIG.write_text(cfg_text.replace(f'"{old}"', f'"{arn}"', 1)
                      if old else cfg_text)
    if not old:
        sys.exit("could not rewrite retry_agent_runtime_arn; set it by hand")
    print(json.dumps({"runtime_name": a.runtime_name, "arn": arn,
                      "image_uri": image_uri, "role_arn": role_arn},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
