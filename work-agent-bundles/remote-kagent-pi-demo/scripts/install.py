"""Create a fresh scoped installation. Default validates without mutating the cluster."""
import argparse
import json
import subprocess
from pathlib import Path
from profile import load

parser = argparse.ArgumentParser()
parser.add_argument('--profile', required=True)
parser.add_argument('--state', type=Path, required=True)
parser.add_argument('--create', action='store_true')
args = parser.parse_args()
p = load(args.profile)
kube = ['kubectl', '--context', p['kube_context'], '--request-timeout=30s']
docs = [json.loads(s) for s in (args.state/'resources.json').read_text().split('\n---\n')]
if p['flux_namespace'] != p['application_namespace']:
    subprocess.run(kube+['get', 'namespace', p['flux_namespace']], check=True, stdout=subprocess.DEVNULL)
for doc in docs:
    meta = doc['metadata']
    command = kube+['get', doc['kind'], meta['name'], '--ignore-not-found', '-o', 'name']
    if meta.get('namespace'): command += ['-n', meta['namespace']]
    if subprocess.check_output(command, text=True).strip():
        raise SystemExit('Resource already exists: '+doc['kind']+'/'+meta['name']+'. Preserve it and use a fresh run/profile.')
# Validate native templates and MCP resources in the existing agent namespace first.
# Namespace-dependent objects cannot all pass server dry-run before their namespace exists.
for doc in docs:
    if doc['kind'] in ('AgentTemplate', 'Harness', 'Agent', 'RemoteMCPServer'):
        subprocess.run(kube+['create', '--dry-run=server', '-f', '-'], input=json.dumps(doc), text=True, check=True, stdout=subprocess.DEVNULL)
if not args.create:
    print('PLAN_ONLY: names are fresh and native resource schemas accepted. No cluster write.')
    raise SystemExit()
# Create instead of apply avoids replacing an existing resource on a collision.
for doc in docs:
    subprocess.run(kube+['create', '-f', '-'], input=json.dumps(doc), text=True, check=True, stdout=subprocess.DEVNULL)
print('CREATED: scoped resources only. Verify pod/agent/Flux readiness before starting an incident.')
