"""Read native version and optionally an existing task. No session or model invocation."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'runtime'))
from rpc import RPC

parser = argparse.ArgumentParser()
parser.add_argument('--controller', required=True)
parser.add_argument('--task-id')
parser.add_argument('--tenant')
args = parser.parse_args()
rpc = RPC(args.controller)
version = rpc.call('kagent.api.v1alpha1.SystemService', 'GetVersion', {})
if not version['kagentVersion'].lstrip('v').startswith('1.'): raise SystemExit('BLOCKED: native 1.x required')
result = {'version': version, 'model_calls': 0}
if args.task_id:
    if not args.tenant: raise SystemExit('An exact namespace/agent tenant is required')
    task = rpc.call('lf.a2a.v1.A2AService', 'GetTask', {'id': args.task_id, 'tenant': args.tenant, 'historyLength': 0})
    result['task'] = {k: task.get(k) for k in ('id', 'contextId', 'status')}
print(json.dumps(result, indent=2))
