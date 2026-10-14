"""Read Kubernetes metadata into the bridge's capability inventory. Never read Secrets."""
import argparse
import datetime
import json
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


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
    namespace = 'kagent'
    models = get('modelconfigs')['items']
    observed = datetime.datetime.now(datetime.timezone.utc).isoformat()
    roles = {}
    agents = {**binding['agents'], **{'chat-'+r: n for r,n in binding.get('chat', {}).get('agents', {}).items()}}
    agents.update({'gitops-'+r: n for r,n in binding.get('gitops', {}).get('agents', {}).items()})
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
                    'writes': tool_name in ('record_proposal', 'publish_proposal', 'create_rollback_mr', 'merge_mr'), 'offered': True,
                    'replay': 'unsafe' if tool_name in ('record_proposal', 'publish_proposal', 'create_rollback_mr', 'merge_mr') else 'safe'})
        selected = template.get('modelConfig', {}).get('name')
        routes = [{'name': m['metadata']['name'], 'provider': m['spec']['provider'], 'model': m['spec']['model'],
            'selected': m['metadata']['name'] == selected,
            'mode': 'Scripted comparison route' if m['metadata']['name'] in (binding['model']+'-native', binding['model']+'-reviewer')
                else 'Live Kimi through the bounded gateway' if m['metadata']['name'] in (binding.get('chat', {}).get('model'), binding.get('gitops', {}).get('model'))
                else 'Configured route; invocation not verified by this inventory'} for m in models]
        roles[role] = {'tools': tools, 'capabilityInventory': {'observedAt': observed,
            'source': 'Kubernetes Agent, AgentTemplate, Harness, ModelConfig and RemoteMCPServer discovery status',
            'cluster': 'kind-pi-durable-local / '+namespace, 'template': template_name, 'harness': harness_name,
            'instructions': template.get('systemPrompt', 'Prompt referenced externally; not collected'),
            'skills': [{'name': s['name'], 'source': skill_source(s['source'])} for s in template.get('skills', [])],
            'models': sorted(routes, key=lambda m: (not m['selected'], m['name'])),
            'runtime': {'snapshots': harness.get('substrate', {}).get('snapshotPolicy', {}).get('location', 'Not configured'),
                'compaction': 'No explicit compaction policy in this native Harness. Automatic compaction is not verified.'}}}
    return {'observedAt': observed, 'roles': roles}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binding', type=Path, required=True)
    parser.add_argument('--kubeconfig', required=True)
    args = parser.parse_args()
    binding = json.loads(args.binding.read_text())
    command = ['kubectl', '--kubeconfig', args.kubeconfig]
    context = subprocess.check_output(command+['config', 'current-context'], text=True).strip()
    if context != 'kind-pi-durable-local':
        raise SystemExit('Unexpected cluster context')
    def get(resource, name=None):
        return json.loads(subprocess.check_output(command+['get', resource]+([name] if name else [])+['-n', 'kagent', '-o', 'json'], timeout=20))
    data = inventory(get, binding)
    writer = "import os,sys; p='/data/capabilities.json'; f=open(p+'.tmp','w'); f.write(sys.stdin.read()); f.close(); os.replace(p+'.tmp',p)"
    subprocess.run(command+['exec', '-i', '-n', 'kagent', 'deploy/'+binding['app'], '-c', 'bridge', '--', 'python', '-c', writer],
        input=json.dumps(data), text=True, check=True, timeout=30)
    print(json.dumps({'observedAt': data['observedAt'], 'roles': list(data['roles']), 'secretReads': 0}))


if __name__ == '__main__':
    main()
