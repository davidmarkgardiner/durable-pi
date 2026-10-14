"""Create a fresh bounded live chat pair without changing retained incident agents."""
import argparse
import json
import os
import secrets
import subprocess
import time
import uuid
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--binding', type=Path, required=True)
parser.add_argument('--state', type=Path, required=True)
parser.add_argument('--lab-dir', type=Path, default=Path.home()/'pi-durable-lab')
parser.add_argument('--bridge-image', required=True)
parser.add_argument('--mode', choices=['chat', 'gitops'], default='chat')
parser.add_argument('--gitops-runtime', type=Path)
args = parser.parse_args()
os.umask(0o077)
args.state.mkdir(parents=True, exist_ok=False)
kube = ['kubectl', '--kubeconfig', str(args.lab_dir/'.state/local-native/kubeconfig')]
def k(*words, body=None):
    return subprocess.check_output(kube+list(words), input=body, text=True, timeout=160).strip()
assert k('config', 'current-context') == 'kind-pi-durable-local'
binding = json.loads(args.binding.read_text())
if binding.get(args.mode):
    raise SystemExit('This workspace already exists. Preserve its native sessions')
gitops = args.mode == 'gitops'
gitops_runtime = json.loads(args.gitops_runtime.read_text()) if gitops else None
directory = '/gitops-config' if gitops else '/chat-config'
max_calls, token_budget = (24, 80000) if gitops else (8, 20000)
suffix = secrets.token_hex(4)
workspace = ('native-gitops-' if gitops else 'native-chat-')+suffix
model = 'pi-hub-'+args.mode+'-model-'+suffix
config_name = workspace+'-config'
token = secrets.token_urlsafe(32)
gateway = json.loads((args.lab_dir/'.state/live-model/config.json').read_text())
assert gateway['model'] == 'kimi-for-coding' and gateway['upstream'].endswith('/kimi/v1')
guard = {'model': 'kimi-for-coding', 'upstream': gateway['upstream'], 'token_budget': token_budget,
    'max_calls': max_calls, 'max_output_tokens': 2048 if gitops else 1024, 'forwarding_enabled': True, 'client_tokens': {args.mode: token}}
guard_source = (args.lab_dir/'model_guard.py').read_text()
if gitops:
    guard_source = guard_source.replace('size > 16384', 'size > 65536').replace('Request must fit within 16 KiB', 'Request must fit within 64 KiB')
documents = [
    {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': model+'-config', 'namespace': 'kagent'},
        'immutable': True, 'stringData': {'config.json': json.dumps(guard)}},
    {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': model+'-key', 'namespace': 'kagent'},
        'immutable': True, 'stringData': {'api-key': token}},
    {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': model+'-code', 'namespace': 'kagent'},
        'immutable': True, 'data': {'model_guard.py': guard_source}},
    {'apiVersion': 'v1', 'kind': 'PersistentVolumeClaim', 'metadata': {'name': model+'-data', 'namespace': 'kagent'},
        'spec': {'accessModes': ['ReadWriteOnce'], 'resources': {'requests': {'storage': '256Mi'}}}},
    {'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': model, 'namespace': 'kagent'},
        'spec': {'selector': {'app': model}, 'ports': [{'port': 4795, 'targetPort': 4795}]}},
    {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': model, 'namespace': 'kagent'},
        'spec': {'replicas': 1, 'strategy': {'type': 'Recreate'}, 'selector': {'matchLabels': {'app': model}},
            'template': {'metadata': {'labels': {'app': model}}, 'spec': {
                'automountServiceAccountToken': False, 'securityContext': {'runAsUser': 65532, 'runAsGroup': 65532, 'fsGroup': 65532},
                'containers': [{'name': 'model', 'image': 'durable-agent-showcase:20261014-live-2', 'imagePullPolicy': 'Never',
                    'command': ['python', '/guard/model_guard.py', '--config', '/config/config.json', '--ledger', '/data/budget.sqlite'],
                    'readinessProbe': {'httpGet': {'path': '/healthz', 'port': 4795}},
                    'resources': {'requests': {'cpu': '30m', 'memory': '48Mi'}, 'limits': {'cpu': '500m', 'memory': '192Mi'}},
                    'securityContext': {'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}},
                    'volumeMounts': [{'name': 'config', 'mountPath': '/config', 'readOnly': True},
                        {'name': 'code', 'mountPath': '/guard', 'readOnly': True}, {'name': 'data', 'mountPath': '/data'}]}],
                'volumes': [{'name': 'config', 'secret': {'secretName': model+'-config'}},
                    {'name': 'code', 'configMap': {'name': model+'-code'}},
                    {'name': 'data', 'persistentVolumeClaim': {'claimName': model+'-data'}}]}}}},
    {'apiVersion': 'api.kagent.dev/v1alpha3', 'kind': 'ModelConfig', 'metadata': {'name': model, 'namespace': 'kagent'},
        'spec': {'provider': 'OpenAI', 'model': 'kimi-for-coding', 'stream': False, 'apiKeySecret': model+'-key',
            'apiKeySecretKey': 'api-key', 'openAI': {'baseUrl': 'http://'+model+'.kagent.svc:4795/v1',
                'apiFormat': 'chatCompletions', 'maxTokens': 2048 if gitops else 1024, 'reasoningEffort': 'low'}}}]
source_agent = json.loads(k('get', 'agent', binding['agents']['reviewer'], '-n', 'kagent', '-o', 'json'))
template = json.loads(k('get', 'agenttemplate', source_agent['spec']['templateRef']['name'], '-n', 'kagent', '-o', 'json'))
harness = json.loads(k('get', 'harness', source_agent['spec']['harnessRef']['name'], '-n', 'kagent', '-o', 'json'))
agents, create_ids = {}, {}
for role in ('investigator', 'reviewer'):
    name = workspace+'-'+role
    agents[role], create_ids[role] = name, str(uuid.uuid4())
    prompt = ('You are a live application specialist for a synthetic guest-checkout application in this Proxmox Kubernetes lab. '
        'Answer user messages normally and remember this native session context. Use read_incident when asked to investigate. '
        'Use get_operation or read_result with op_id proactive-operation when you need proposal or effect evidence. '
        'Your tools only read the protected synthetic comparison fixture in namespace durable-fixture. '
        'You cannot edit source, change Kubernetes, publish a proposal, create or merge PRs, or approve a human gate. '
        'Explain evidence and propose next steps. Do not claim unavailable actions happened. '
        'The retained incident and its human decision are separate from this chat. '
        'Use at most three read-tool calls per user message and stop after obtaining enough evidence. '
        'For ordinary follow-up questions use session context without unnecessary tool calls. Keep answers concise.')
    if role == 'reviewer':
        prompt += ' Your role is to review supplied reasoning and proposals against available incident evidence.'
    if gitops:
        prompt = ('You are the '+role+' for Lumen synthetic guest checkout in namespace lumen-gitops in kind-pi-durable-local. '
            'Your model is live; all tool evidence must come from the configured real application, GitLab project and Flux. '
            'Image lumen-checkout:v2 assumes a guest has a loyalty account and throws KeyError. Image lumen-checkout:v1 is the known healthy rollback. '
            'The only allowed remediation is a real GitLab MR changing deploy/deployment.json image v2 to v1. '
            'Use the exact binding returned by create_rollback_mr for inspect_mr, merge_mr and verify_application. Never invent IDs or SHAs. '
            'merge_mr requires the native human approval and an independent decision. Do not retry it or bypass it. '
            'After approval, merge and call verify_application once. If fixed=false, report waiting for Flux; never claim the app is fixed. '
            'Keep each response concise. Do not loop while waiting for CI or Flux; the pane will hand off review and verification when ready.')
        if role == 'reviewer':
            prompt += ' You are strictly read-only. Call inspect_mr, check diff_valid and ci_pass for the exact supplied binding, and return PASS plus its full head SHA only if both checks are true.'
    spec = {**template['spec'], 'description': 'Live Pi-pane '+role+' with read-only incident tools',
        'modelConfig': {'name': model}, 'systemPrompt': prompt}
    if gitops:
        remote = workspace+'-'+role+'-mcp'
        docs = [
            {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': remote+'-key', 'namespace': 'kagent'}, 'immutable': True,
                'stringData': {'Authorization': 'Bearer '+gitops_runtime['tokens'][role]}},
            {'apiVersion': 'api.kagent.dev/v1alpha3', 'kind': 'RemoteMCPServer', 'metadata': {'name': remote, 'namespace': 'kagent'},
                'spec': {'description': 'Exact-project Lumen rollback tools for '+role, 'protocol': 'STREAMABLE_HTTP', 'url': 'http://lumen-tools.kagent.svc:8080/mcp', 'timeout': '60s',
                    'headersFrom': [{'name': 'Authorization', 'valueFrom': {'name': remote+'-key', 'key': 'Authorization', 'type': 'Secret'}}]}}]
        documents.extend(docs)
        spec['tools'] = [{'mcp': {'server': {'kind': 'RemoteMCPServer', 'name': remote},
            'tools': ['read_incident', 'read_deployment', 'read_gitops', 'inspect_mr', 'verify_application']+(['create_rollback_mr'] if role == 'investigator' else [])}}]
        if role == 'investigator':
            spec['tools'].append({'mcp': {'requireApproval': True, 'server': {'kind': 'RemoteMCPServer', 'name': remote}, 'tools': ['merge_mr']}})
    hs = json.loads(json.dumps(harness['spec']))
    hs['substrate']['snapshotPolicy']['location'] = 's3://ate-snapshots/native-chat/'+suffix+'/'
    documents.extend([
        {'apiVersion': template['apiVersion'], 'kind': 'AgentTemplate', 'metadata': {'name': name+'-template', 'namespace': 'kagent'}, 'spec': spec},
        {'apiVersion': harness['apiVersion'], 'kind': 'Harness', 'metadata': {'name': name+'-harness', 'namespace': 'kagent'}, 'spec': hs},
        {'apiVersion': source_agent['apiVersion'], 'kind': 'Agent', 'metadata': {'name': name, 'namespace': 'kagent'},
            'spec': {'templateRef': {'name': name+'-template'}, 'harnessRef': {'name': name+'-harness'}}}])
plan = {'workspace_id': workspace, 'model': model, 'agents': agents, 'create_ids': create_ids, 'contexts': {}}
(args.state/'binding.json').write_text(json.dumps(plan, indent=2)+'\n')
path = args.state/'resources.json'
path.write_text('\n---\n'.join(json.dumps(d) for d in documents))
k('create', '--dry-run=server', '-f', str(path))
k('create', '-f', str(path))
k('rollout', 'status', '-n', 'kagent', 'deployment/'+model, '--timeout=120s')
deadline = time.monotonic()+120
for name in agents.values():
    while True:
        agent = json.loads(k('get', 'agent', name, '-n', 'kagent', '-o', 'json'))
        if any(c['type'] == 'Ready' and c['status'] == 'True' for c in agent.get('status', {}).get('conditions', [])):
            break
        if time.monotonic() > deadline:
            raise SystemExit('Native chat agent not ready. Preserve deployment receipts')
        time.sleep(2)
source = """
import json,sys
sys.path.insert(0,'/app')
import server
rpc=server.RPC('kagent-controller.kagent.svc:8083')
contexts={}
for role,name in AGENTS.items():
 result=rpc.call('kagent.api.v1alpha1.SessionService','CreateSession',{'agent':{'namespace':'kagent','name':name},'requestId':IDS[role],'name':'Live Kimi chat - '+role})
 contexts[role]=result['session']['id']
 rpc.call('kagent.api.v1alpha1.SessionService','ResumeSession',{'sessionId':contexts[role]})
print(json.dumps(contexts))
""".replace('AGENTS', repr(agents)).replace('IDS', repr(create_ids))
plan['contexts'] = json.loads(k('exec', '-i', '-n', 'kagent', 'deploy/'+binding['app'], '-c', 'bridge', '--', 'python', '-', body=source))
(args.state/'binding.json').write_text(json.dumps(plan, indent=2)+'\n')
runtime = {**plan, 'data': '/data', 'created_at': int(time.time()*1000), 'max_calls': max_calls, 'token_budget': token_budget,
    'model_status_url': 'http://'+model+'.kagent.svc:4795/status', 'model_status_token_file': directory+'/model-status.token'}
if gitops:
    runtime.update(database='gitops-chat.sqlite', backend='http://lumen-tools.kagent.svc:8080')
secret = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': config_name, 'namespace': 'kagent'}, 'immutable': True,
    'stringData': {'runtime.json': json.dumps(runtime), 'model-status.token': token}}
if gitops:
    secret['stringData']['control.token'] = gitops_runtime['tokens']['control']
secret_path = args.state/'chat-config.json'
secret_path.write_text(json.dumps(secret))
k('create', '-f', str(secret_path))
deployment = json.loads(k('get', 'deployment', binding['app'], '-n', 'kagent', '-o', 'json'))
pod = deployment['spec']['template']['spec']
pod['volumes'].append({'name': args.mode+'-config', 'secret': {'secretName': config_name}})
for container in pod['containers']+pod.get('initContainers', []):
    container['image'] = args.bridge_image
    if container['name'] == 'bridge':
        container['volumeMounts'].append({'name': args.mode+'-config', 'mountPath': directory, 'readOnly': True})
patch = json.dumps({'spec': {'template': {'spec': pod}}})
binding.update(image=args.bridge_image)
binding[args.mode] = plan
args.binding.write_text(json.dumps(binding, indent=2)+'\n')
k('patch', 'deployment', binding['app'], '-n', 'kagent', '--type=merge', '-p', patch)
k('rollout', 'status', '-n', 'kagent', 'deployment/'+binding['app'], '--timeout=120s')
print(json.dumps({'workspace': workspace, 'agents': agents, 'contexts': plan['contexts'], 'maxCalls': max_calls, 'tokenBudget': token_budget, 'messagesSent': 0}))
