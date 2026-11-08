"""Trusted operator entrypoint for the local-only effect qualification canary.

Run this module in a separate operator process. Do not expose its PostgreSQL
DSN or provider keys to model inference or live environments.
"""
import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path

from neuron.effect_canary import (
    ApprovedAction,
    AttenuatedCapability,
    EffectCoordinator,
    EffectError,
    HttpObjectProvider,
    PostgresAuthorityRepository,
    ResolvedImplementation,
)


def repository():
    dsn=os.environ.get("VAMS_EFFECT_DATABASE_URL","")
    repo=PostgresAuthorityRepository(dsn)
    repo.initialize()
    return repo


def secret(name):
    raw=os.environ.get(name,"")
    try:
        value=bytes.fromhex(raw)
    except ValueError as exc:
        raise EffectError(f"{name} must contain hex bytes") from exc
    if len(value)<32:
        raise EffectError(f"{name} must contain at least 32 bytes")
    return value


def provider():
    base=os.environ.get("VAMS_EFFECT_PROVIDER_URL","")
    return HttpObjectProvider(base,secret("VAMS_EFFECT_WRITER_KEY"),secret("VAMS_EFFECT_OBSERVER_KEY"))


def build_parser():
    parser=argparse.ArgumentParser(description="Provision or run the local-only VAMS effect canary.")
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("init",help="initialize/version-check the PostgreSQL application schema")
    grant=sub.add_parser("provision",help="provision one principal capability using operator-controlled database credentials")
    for name in ("principal","task","target","implementation-digest","object-prefix"):
        grant.add_argument("--"+name,required=True)
    for name in ("budget-units","max-cost-units","policy-revision","authority-epoch","expires-at"):
        grant.add_argument("--"+name,type=int,required=True)
    write=sub.add_parser("write",help="write one synthetic object under a provisioned capability")
    write.add_argument("--principal",required=True)
    write.add_argument("--task",required=True)
    write.add_argument("--target",required=True)
    write.add_argument("--implementation-digest",required=True)
    write.add_argument("--object-key",required=True)
    write.add_argument("--cost-units",type=int,required=True)
    write.add_argument("--policy-revision",type=int,required=True)
    write.add_argument("--authority-epoch",type=int,required=True)
    write.add_argument("--expires-at",type=int,required=True)
    write.add_argument("--content-file",type=Path,required=True)
    write.add_argument("--operation-id",default=None)
    return parser


def main(argv=None):
    if os.environ.get("VAMS_ENV") not in {"local","test","demo"}:
        raise EffectError("operator canary is restricted to explicit local/test/demo mode")
    args=build_parser().parse_args(argv)
    repo=repository()
    if args.command=="init":
        print("PostgreSQL effect schema v1 is available.")
        return 0
    if args.command=="provision":
        capability=AttenuatedCapability(
            principal_id=args.principal,task_id=args.task,target=args.target,
            implementation_digest=args.implementation_digest,max_cost_units=args.max_cost_units,
            policy_revision=args.policy_revision,authority_epoch=args.authority_epoch,
            expires_at=args.expires_at,object_prefix=args.object_prefix,
        )
        repo.provision_capability(capability,args.budget_units)
        print(json.dumps({"provisioned":True,"principal_id":args.principal,"task_id":args.task,"policy_revision":args.policy_revision,"authority_epoch":args.authority_epoch}))
        return 0
    if args.content_file.stat().st_size>1_048_576:
        raise EffectError("synthetic object exceeds 1 MiB")
    content=args.content_file.read_bytes()
    operation=args.operation_id or str(uuid.uuid4())
    action=ApprovedAction(
        principal_id=args.principal,task_id=args.task,operation_id=operation,target=args.target,
        implementation=ResolvedImplementation("operator-pinned-object-provider","1",args.implementation_digest),
        object_key=args.object_key,content_hash=hashlib.sha256(content).hexdigest(),
        cost_units=args.cost_units,policy_revision=args.policy_revision,
        authority_epoch=args.authority_epoch,expires_at=args.expires_at,
    )
    result=EffectCoordinator(repo,provider()).execute(action,content)
    print(json.dumps({"operation_id":result.operation_id,"status":result.status.value,"receipt":result.receipt}))
    return 0


if __name__=="__main__":
    try:
        sys.exit(main())
    except (EffectError,OSError) as exc:
        print(f"effect canary failed closed: {exc}",file=sys.stderr)
        sys.exit(2)
