"""Refresh native declarations and controller MCP discovery without reading Secret values."""
import argparse
import datetime
import json
import subprocess
import time
from urllib.parse import urlsplit, urlunsplit
from profile import load

def safe_url(value):
    url = urlsplit(value)
    return urlunsplit((url.scheme, url.hostname or '', url.path, '', ''))


def skill_source(source):
    if 'oci' in source:
        origin = source['oci']
    elif 'git' in source:
        origin = safe_url(source['git']['url']) + '@' + source['git']['commit']
    elif 'bucket' in source:
        s3 = source['bucket']['s3']
        origin = 's3://' + s3['bucket'] + '/' + s3['key'] + '@' + s3['versionId']
    else:
        origin = 'Unrecognized source'
    return origin + (' / ' + source['path'] if source.get('path') else '')


def inventory(get, binding):
    namespace = binding['namespace']
    models = get('modelconfigs')['items']
    observed = datetime.datetime.now(datetime.timezone.utc).isoformat()
    roles = {}
    agents = binding['agents']
    for role, name in agents.items():
        agent = get('agent', name)
        template_name = agent['spec']['templateRef']['name']
        harness_name = agent['spec']['harnessRef']['name']
        template = get('agenttemplate', template_name)['spec']
        harness = get('harness', harness_name)['spec']
        tools = []
        for entry in template.get('tools', []):
            if 'mcp' not in entry:
                continue
            mcp = entry['mcp']
            server_name = mcp['server']['name']
            server = get('remotemcpserver', server_name)
            discovered = {t['name']: t for t in server.get('status', {}).get('discoveredTools', [])}
            for tool_name in mcp.get('tools') or discovered:
                tool = discovered.get(tool_name, {})
                tools.append({'name': tool_name, 'description': tool.get('description', 'Not discovered by controller'),
                    'server': server_name, 'requireApproval': mcp.get('requireApproval', False),
                    'writes': tool_name in ('record_proposal', 'publish_proposal', 'create_rollback_mr', 'merge_mr'), 'offered': bool(tool),
                    'replay': 'unsafe' if tool_name in ('record_proposal', 'publish_proposal', 'create_rollback_mr', 'merge_mr') else 'safe'})
        selected = template.get('modelConfig', {}).get('name')
        routes = [{'name': m['metadata']['name'], 'provider': m['spec']['provider'], 'model': m['spec']['model'],
            'selected': m['metadata']['name'] == selected,
            'mode': 'Configured route; model access requires native task receipts'} for m in models]
        roles[role] = {'tools': tools, 'capabilityInventory': {'observedAt': observed,
            'source': 'Kubernetes Agent, AgentTemplate, Harness, ModelConfig and RemoteMCPServer discovery status',
            'cluster': binding['cluster_label']+' / '+namespace, 'template': template_name, 'harness': harness_name,
            'instructions': template.get('systemPrompt', 'Prompt referenced externally; not collected'),
            'skills': [{'name': s['name'], 'source': skill_source(s['source'])} for s in template.get('skills', [])],
            'models': sorted(routes, key=lambda m: (not m['selected'], m['name'])),
            'runtime': {'snapshots': harness.get('substrate', {}).get('snapshotPolicy', {}).get('location', 'Not configured'),
                'compaction': 'Existing Harness configuration retained. Automatic compaction is not verified by this inventory.'}}}
    return {'observedAt': observed, 'roles': roles}


parser = argparse.ArgumentParser()
parser.add_argument('--profile', required=True)
parser.add_argument('--watch', action='store_true')
args = parser.parse_args()
p = load(args.profile)
kube = ['kubectl', '--context', p['kube_context'], '--request-timeout=15s', '-n', p['agent_namespace']]
binding = {**p, 'namespace': p['agent_namespace'], 'model': p['model_config'],
    'agents': {r: p['run_id']+'-'+r for r in ('investigator', 'reviewer')}}
def get(resource, name=None):
    return json.loads(subprocess.check_output(kube+['get', resource]+([name] if name else [])+['-o', 'json'], timeout=20))
while True:
    data = {**inventory(get, binding), 'workspace_id': p['run_id']}
    writer = "import os,sys; p='/data/capabilities.json'; f=open(p+'.tmp','w'); f.write(sys.stdin.read()); f.close(); os.replace(p+'.tmp',p)"
    subprocess.run(kube+['exec', '-i', 'deploy/'+p['run_id']+'-bridge', '--', 'python', '-c', writer],
        input=json.dumps(data), text=True, check=True, timeout=20)
    print(json.dumps({'observedAt': data['observedAt'], 'roles': list(data['roles']), 'secret_values_read': 0}), flush=True)
    if not args.watch: break
    time.sleep(45)
