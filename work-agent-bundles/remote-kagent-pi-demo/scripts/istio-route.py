"""Render only a VirtualService for an existing AKS Istio Gateway. Never changes the add-on."""
import argparse
import json
from profile import load

parser = argparse.ArgumentParser()
parser.add_argument('--profile', required=True)
args = parser.parse_args()
p = load(args.profile)
for key in ('istio_gateway', 'istio_host'):
    if not p.get(key) or 'REPLACE' in p[key] or '.invalid' in p[key]: raise SystemExit('Provide an approved '+key)
print(json.dumps({'apiVersion': 'networking.istio.io/v1beta1', 'kind': 'VirtualService',
    'metadata': {'name': p['run_id']+'-bridge', 'namespace': p['agent_namespace']},
    'spec': {'hosts': [p['istio_host']], 'gateways': [p['istio_gateway']], 'http': [{
        'match': [{'uri': {'prefix': '/'}}], 'timeout': '0s', 'route': [{'destination': {
            'host': p['run_id']+'-bridge.'+p['agent_namespace']+'.svc.cluster.local', 'port': {'number': 8080}}}]}]}}, indent=2))
