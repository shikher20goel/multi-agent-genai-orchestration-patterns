"""Build and deploy the anchor agents onto Bedrock AgentCore Runtime.

Deploys ONE image twice, as two single-pattern agent runtimes whose only
difference is the ``ANCHOR_PATTERN`` environment variable (see
agent/agent_app.py). Writes the resulting ARNs to runtimes.json so the
harness never has an ARN typed into it by hand.

The execution role is not created here. Pass --role-arn, or let the
script read it off an existing runtime with --copy-role-from <name>
(the P7 probe's runtime is the obvious donor). Whatever role is used
must additionally allow ``bedrock:InvokeModel`` on the anchor model,
because these agents -- unlike the P7 probe's -- call the model.

Usage:
    python anchor/agentcore/deploy_agentcore.py --region us-east-1 \
        --copy-role-from p7probe
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

import boto3

HERE = Path(__file__).resolve().parent
AGENT_DIR = HERE / "agent"
RUNTIMES_FILE = HERE / "runtimes.json"
REPO_NAME = "anchor-agentcore"
IMAGE_TAG = "v1"


def _sh(cmd, **kw):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def ensure_ecr(ecr, account, region) -> str:
    try:
        ecr.create_repository(repositoryName=REPO_NAME)
        print(f"created ECR repository {REPO_NAME}")
    except ecr.exceptions.RepositoryAlreadyExistsException:
        print(f"ECR repository {REPO_NAME} already exists")
    return f"{account}.dkr.ecr.{region}.amazonaws.com/{REPO_NAME}:{IMAGE_TAG}"


def docker_login(ecr, account, region):
    tok = ecr.get_authorization_token()["authorizationData"][0]
    user, pwd = base64.b64decode(tok["authorizationToken"]).decode().split(":", 1)
    _sh(["docker", "login", "--username", user, "--password-stdin",
         f"{account}.dkr.ecr.{region}.amazonaws.com"],
        input=pwd.encode())


def build_and_push(image_uri, context=None, dockerfile=None):
    """Build arm64 and push. AgentCore runs arm64 only, so buildx emulates.

    context/dockerfile are split because the released-module image must be
    built from the REPO ROOT (it ships src/ and configs/) while its
    Dockerfile lives beside the agent.
    """
    cmd = ["docker", "buildx", "build", "--platform", "linux/arm64",
           "-t", image_uri, "--push"]
    if dockerfile:
        cmd += ["-f", str(dockerfile)]
    cmd.append(str(context or AGENT_DIR))
    _sh(cmd)


def role_of(ac_ctl, name) -> str:
    for rt in ac_ctl.get_paginator("list_agent_runtimes").paginate():
        for r in rt.get("agentRuntimes", []):
            if r["agentRuntimeName"] == name:
                d = ac_ctl.get_agent_runtime(agentRuntimeId=r["agentRuntimeId"])
                return d["roleArn"]
    sys.exit(f"no agent runtime named {name} in this account/region")


def find_runtime(ac_ctl, name):
    for page in ac_ctl.get_paginator("list_agent_runtimes").paginate():
        for r in page.get("agentRuntimes", []):
            if r["agentRuntimeName"] == name:
                return r
    return None


def upsert(ac_ctl, name, image_uri, role_arn, env) -> str:
    spec = dict(
        agentRuntimeArtifact={"containerConfiguration":
                              {"containerUri": image_uri}},
        networkConfiguration={"networkMode": "PUBLIC"},
        roleArn=role_arn,
        environmentVariables=env,
    )
    existing = find_runtime(ac_ctl, name)
    if existing:
        print(f"updating existing runtime {name}")
        r = ac_ctl.update_agent_runtime(
            agentRuntimeId=existing["agentRuntimeId"], **spec)
    else:
        print(f"creating runtime {name}")
        r = ac_ctl.create_agent_runtime(agentRuntimeName=name, **spec)
    arn = r["agentRuntimeArn"]
    rid = arn.rsplit("/", 1)[-1]
    for _ in range(60):
        st = ac_ctl.get_agent_runtime(agentRuntimeId=rid)["status"]
        if st == "READY":
            print(f"{name}: READY")
            return arn
        if st in ("CREATE_FAILED", "UPDATE_FAILED"):
            sys.exit(f"{name}: {st}")
        time.sleep(10)
    sys.exit(f"{name}: never reached READY")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--role-arn")
    ap.add_argument("--copy-role-from",
                    help="name of an existing runtime to borrow the role from")
    ap.add_argument("--model-id", default="us.amazon.nova-micro-v1:0")
    ap.add_argument("--n-collaborators", default="3")
    ap.add_argument("--skip-build", action="store_true")
    a = ap.parse_args(argv)

    account = boto3.client("sts").get_caller_identity()["Account"]
    ecr = boto3.client("ecr", region_name=a.region)
    ac_ctl = boto3.client("bedrock-agentcore-control", region_name=a.region)

    role_arn = a.role_arn or (a.copy_role_from
                              and role_of(ac_ctl, a.copy_role_from))
    if not role_arn:
        sys.exit("need --role-arn or --copy-role-from")

    image_uri = ensure_ecr(ecr, account, a.region)
    if not a.skip_build:
        docker_login(ecr, account, a.region)
        build_and_push(image_uri)

    common = {"ANCHOR_MODEL_ID": a.model_id, "ANCHOR_MODEL_REGION": a.region}
    out = {"region": a.region, "image_uri": image_uri, "role_arn": role_arn,
           "model_id": a.model_id, "runtimes": {}}
    out["runtimes"]["P1"] = upsert(
        ac_ctl, "anchorp1", image_uri, role_arn,
        {**common, "ANCHOR_PATTERN": "P1",
         "ANCHOR_N_COLLABORATORS": str(a.n_collaborators)})
    out["runtimes"]["P2"] = upsert(
        ac_ctl, "anchorp2", image_uri, role_arn,
        {**common, "ANCHOR_PATTERN": "P2"})
    RUNTIMES_FILE.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
