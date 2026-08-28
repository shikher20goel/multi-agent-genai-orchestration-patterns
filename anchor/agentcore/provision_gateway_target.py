"""Create the Lambda tool behind the AgentCore Gateway, and attach it.

This closes the P5.gateway bound. Until now the gateway existed but exposed
no tools, so P5's hop ran on the in-memory stub and every record said so.

The Lambda is deliberately trivial. P5's structural claim is that routing
through a gateway costs an extra hop per tool call; demonstrating that needs
a tool that responds, not a tool that does anything interesting. Calling it
a stand-in in the bounds document and then shipping something elaborate
would be the wrong kind of thorough.
"""
from __future__ import annotations

import argparse
import io
import json
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

HERE = Path(__file__).resolve().parent
INVENTORY = HERE / "resources_all7.json"

FUNCTION_NAME = "agentorch-all7-tool"
TARGET_NAME = "agentorch-standin-tools"

LAMBDA_SRC = '''
import json

def handler(event, context):
    """Minimal tool behind the gateway.

    Echoes the tool name and arguments. The gateway hop is the thing under
    test; the tool's own behaviour is not.
    """
    tool = (event.get("tool")
            or (context.client_context.custom or {}).get("bedrockAgentCoreToolName")
            if getattr(context, "client_context", None) else event.get("tool"))
    return {"result": f"tool {tool or 'unknown'} ok",
            "echo": {k: v for k, v in event.items() if k != "tool"}}
'''


def _zip_source() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("index.py", LAMBDA_SRC)
    return buf.getvalue()


def ensure_lambda(lam, role_arn: str) -> str:
    try:
        r = lam.get_function(FunctionName=FUNCTION_NAME)
        arn = r["Configuration"]["FunctionArn"]
        print(f"  lambda   EXISTS  {arn}")
        return arn
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
    r = lam.create_function(
        FunctionName=FUNCTION_NAME, Runtime="python3.12", Role=role_arn,
        Handler="index.handler", Code={"ZipFile": _zip_source()},
        Description="Stand-in tool behind the AgentCore gateway (P5 hop)",
        Timeout=15, MemorySize=128)
    arn = r["FunctionArn"]
    print(f"  lambda   CREATED  {arn}")
    # A freshly created function is not immediately invokable.
    for _ in range(30):
        if lam.get_function(FunctionName=FUNCTION_NAME)[
                "Configuration"].get("State") == "Active":
            break
        time.sleep(5)
    return arn


def _p5_tools() -> list[str]:
    """The tool names P5 actually asks for, read from the released config.

    Guessing them is how the first attempt failed: the target exposed
    "search" and "lookup" while the pattern asks for search, calculator and
    crm_lookup, so the seam refused rather than substituting. Reading the
    config keeps the target honest as the pattern evolves.
    """
    import sys
    sys.path.insert(0, str(HERE.parent.parent / "src"))
    from agentorch.config import load_config
    return list(load_config().patterns.p5.tools)


def ensure_target(ctl, gateway_id: str, lambda_arn: str) -> dict:
    tools = _p5_tools()
    print(f"  tools    {tools}  (from configs/default.yaml patterns.p5.tools)")
    for t in ctl.list_gateway_targets(gatewayIdentifier=gateway_id,
                                      maxResults=50).get("items", []):
        if t.get("name") == TARGET_NAME:
            print(f"  target   DELETING stale {t.get('targetId')} to re-declare tools")
            ctl.delete_gateway_target(gatewayIdentifier=gateway_id,
                                      targetId=t.get("targetId"))
            time.sleep(10)
    spec = {
        "mcp": {"lambda": {
            "lambdaArn": lambda_arn,
            "toolSchema": {"inlinePayload": [
                {"name": name,
                 "description": f"Stand-in {name} tool for the P5 gateway hop",
                 "inputSchema": {"type": "object",
                                 "properties": {"item": {"type": "string"}}}}
                for name in tools
            ]}}}}
    r = ctl.create_gateway_target(
        gatewayIdentifier=gateway_id, name=TARGET_NAME,
        description="Stand-in tools demonstrating P5's gateway hop",
        targetConfiguration=spec,
        credentialProviderConfigurations=[
            {"credentialProviderType": "GATEWAY_IAM_ROLE"}])
    print(f"  target   CREATED  {r.get('targetId')}")
    return {"id": r.get("targetId"), "created": True}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--lambda-role",
                    default="arn:aws:iam::111789566955:role/agentorch-lambda-exec")
    a = ap.parse_args(argv)

    inv = json.loads(INVENTORY.read_text())
    lam = boto3.client("lambda", region_name=a.region)
    ctl = boto3.client("bedrock-agentcore-control", region_name=a.region)

    lambda_arn = ensure_lambda(lam, a.lambda_role)
    # The gateway invokes the function; without this it is denied.
    try:
        lam.add_permission(
            FunctionName=FUNCTION_NAME, StatementId="agentcore-gateway-invoke",
            Action="lambda:InvokeFunction",
            Principal="bedrock-agentcore.amazonaws.com")
        print("  perm     ADDED   bedrock-agentcore may invoke the function")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceConflictException":
            raise
        print("  perm     EXISTS")

    target = ensure_target(ctl, inv["gateway"]["id"], lambda_arn)
    inv["gateway"]["lambda_arn"] = lambda_arn
    inv["gateway"]["target"] = target
    INVENTORY.write_text(json.dumps(inv, indent=2) + "\n")
    print(f"\nwrote {INVENTORY.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
