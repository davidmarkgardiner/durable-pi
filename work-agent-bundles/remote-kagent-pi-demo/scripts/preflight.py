"""Read-only cluster discovery. Never changes the current context or reads Secret values."""
import argparse
import json
import subprocess
from profile import load

parser = argparse.ArgumentParser()
parser.add_argument('--profile', required=True)
args = parser.parse_args()
p = load(args.profile)
kube = ['kubectl', '--context', p['kube_context'], '--request-timeout=15s']


def get(*words):
    return json.loads(subprocess.check_output(kube+['get', *words, '-o', 'json'], text=True, timeout=20))


crd = get('crd', 'agents.api.kagent.dev')
if not any(v['name'] == 'v1alpha3' and v.get('served') for v in crd['spec']['versions']):
    raise SystemExit('BLOCKED: native 1.x AgentTemplate/Harness and controller APIs required. Report version mismatch; do not upgrade the platform automatically')
agent = get('agent', p['seed_agent'], '-n', p['agent_namespace'])
assert any(c['type'] == 'Ready' and c['status'] == 'True' for c in agent.get('status', {}).get('conditions', [])), 'Seed native agent is not Ready'
get('agenttemplate', agent['spec']['templateRef']['name'], '-n', p['agent_namespace'])
get('harness', agent['spec']['harnessRef']['name'], '-n', p['agent_namespace'])
get('modelconfig', p['model_config'], '-n', p['agent_namespace'])
svc = get('service', p['controller_service'], '-n', p['agent_namespace'])
assert any(port['port'] == p['controller_port'] for port in svc['spec']['ports']), 'Controller port differs from the native API profile'
get('crd', 'gitrepositories.source.toolkit.fluxcd.io')
get('crd', 'kustomizations.kustomize.toolkit.fluxcd.io')
get('storageclass', p['storage_class'])
permissions = [
    ('create', 'deployments', p['application_namespace']), ('create', 'agents.api.kagent.dev', p['agent_namespace']),
    ('create', 'agenttemplates.api.kagent.dev', p['agent_namespace']), ('create', 'harnesses.api.kagent.dev', p['agent_namespace'])]
for verb, resource, namespace in permissions:
    allowed = subprocess.check_output(kube+['auth', 'can-i', verb, resource, '-n', namespace], text=True).strip()
    assert allowed == 'yes', 'Missing permission: '+verb+' '+resource+' in '+namespace
print(json.dumps({'status': 'PASS_METADATA', 'context': p['kube_context'], 'namespace': p['agent_namespace'],
    'seed_agent': p['seed_agent'], 'model_config': p['model_config'], 'controller': p['controller_service'],
    'secret_values_read': 0, 'next': 'Verify GetVersion and real authenticated GitLab/MCP reads before enabling the demo'}, indent=2))
