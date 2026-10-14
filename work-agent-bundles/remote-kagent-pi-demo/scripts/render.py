"""Render fresh demo resources from existing native agent infrastructure. No apply or Secret reads."""
import argparse
import datetime
import json
import os
import secrets
import subprocess
import uuid
from pathlib import Path
from profile import load

parser = argparse.ArgumentParser()
parser.add_argument('--profile', required=True)
parser.add_argument('--state', type=Path, required=True)
args = parser.parse_args()
p = load(args.profile)
os.umask(0o077)
args.state.mkdir(parents=True, exist_ok=False)
kube = ['kubectl', '--context', p['kube_context']]


def get(resource, name):
    return json.loads(subprocess.check_output(kube+['get', resource, name, '-n', p['agent_namespace'], '-o', 'json'], text=True))


seed = get('agent', p['seed_agent'])
template = get('agenttemplate', seed['spec']['templateRef']['name'])
harness = get('harness', seed['spec']['harnessRef']['name'])
model = get('modelconfig', p['model_config'])
ns, appns, name = p['agent_namespace'], p['application_namespace'], p['run_id']
tokens = {role: secrets.token_urlsafe(32) for role in ('investigator', 'reviewer', 'control', 'bridge')}
agents = {r: name+'-'+r for r in ('investigator', 'reviewer')}
backend = name+'-tools'
config_name = name+'-config'
runtime = {**p, 'namespace': ns, 'workspace_id': name, 'agents': agents, 'database': 'native-admissions.sqlite',
    'data': '/data', 'device_uid': str(uuid.uuid4()), 'created_at': int(datetime.datetime.now(datetime.timezone.utc).timestamp()*1000),
    'controller': p['controller_service']+'.'+ns+'.svc:'+str(p['controller_port']),
    'backend': 'http://'+backend+'.'+ns+'.svc:8080', 'model_id': model['spec']['model'],
    'application_url': 'http://checkout.'+appns+'.svc:8080', 'rollback_branch': 'agent/'+name+'-rollback',
    'max_calls': 24, 'token_budget': 80000, 'tokens': tokens}
descriptions = {'read_incident': 'Read actual checkout and pod logs', 'read_deployment': 'Read live image and rollout',
    'read_gitops': 'Read the exact repository manifest', 'create_rollback_mr': 'Create the image-only rollback MR',
    'inspect_mr': 'Read exact diff and current-head CI', 'merge_mr': 'Merge only the native and independently approved head',
    'verify_application': 'Read merged SHA, Flux revision, image and checkout probes'}
runtime['tool_descriptions'] = descriptions
runtime['capabilities'] = {}
documents = [{'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': appns, 'labels': {'app.kubernetes.io/part-of': 'pi-work-demo'}}}]
for role, agent_name in agents.items():
    prompt = ('You are the '+role+' for a synthetic guest-checkout application in namespace '+appns+' on '+p['cluster_label']+'. '
        'Classification is a scripted synthetic decision service, not Jev or a learned decision model. '
        'Your investigation, tool calls, repository changes and approval are real. '
        'This is guided remediation: v2 fails guest checkout with KeyError loyalty; the configured v1 image is the known healthy rollback. '
        'Only use the configured app-specific MCP tools and exact returned MR binding. '
        'The only allowed change is the deployment image in '+p['manifest_file']+'. '
        'Request merge_mr and wait for a real native human decision. Never infer approval from these instructions. '
        'After approved merge, call verify_application once; report waiting if fixed is false. '
        'Do not loop while waiting for CI or Flux. Keep the final report concise, with actual receipt IDs. '
        'Use no more than eight tool calls per task. Reconcile uncertain writes through read tools; do not blindly repeat writes.')
    if role == 'reviewer': prompt += ' You are read-only. Inspect the supplied exact MR and CI; return PASS plus the full head SHA only when diff_valid and ci_pass are both true.'
    spec = {**template['spec'], 'description': 'Pi work demonstration '+role, 'modelConfig': {'name': p['model_config']}, 'systemPrompt': prompt}
    server = agent_name+'-mcp'
    spec['tools'] = [{'mcp': {'server': {'kind': 'RemoteMCPServer', 'name': server},
        'tools': ['read_incident', 'read_deployment', 'read_gitops', 'inspect_mr', 'verify_application']+(['create_rollback_mr'] if role == 'investigator' else [])}}]
    if role == 'investigator': spec['tools'].append({'mcp': {'server': {'kind': 'RemoteMCPServer', 'name': server}, 'tools': ['merge_mr'], 'requireApproval': True}})
    hs = json.loads(json.dumps(harness['spec']))
    documents += [
        {'apiVersion': 'api.kagent.dev/v1alpha3', 'kind': 'RemoteMCPServer', 'metadata': {'name': server, 'namespace': ns},
            'spec': {'description': 'Scoped work demo tools', 'protocol': 'STREAMABLE_HTTP', 'url': runtime['backend']+'/mcp', 'timeout': '60s',
                'headersFrom': [{'name': 'Authorization', 'valueFrom': {'type': 'Secret', 'name': config_name, 'key': role+'.authorization'}}]}},
        {'apiVersion': template['apiVersion'], 'kind': 'AgentTemplate', 'metadata': {'name': agent_name+'-template', 'namespace': ns}, 'spec': spec},
        {'apiVersion': harness['apiVersion'], 'kind': 'Harness', 'metadata': {'name': agent_name+'-harness', 'namespace': ns}, 'spec': hs},
        {'apiVersion': seed['apiVersion'], 'kind': 'Agent', 'metadata': {'name': agent_name, 'namespace': ns},
            'spec': {'templateRef': {'name': agent_name+'-template'}, 'harnessRef': {'name': agent_name+'-harness'}}}]
    runtime['capabilities'][role] = {'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source': 'Rendered work-agent manifest; verify native discovery before launch', 'cluster': p['cluster_label']+'/'+ns,
        'template': agent_name+'-template', 'harness': agent_name+'-harness', 'instructions': prompt, 'skills': [],
        'models': [{'name': p['model_config'], 'provider': model['spec']['provider'], 'model': model['spec']['model'], 'selected': True, 'mode': 'Existing approved model; invocation requires work proof'}],
        'runtime': {'snapshots': hs.get('substrate', {}).get('snapshotPolicy', {}).get('location', 'Discover on work cluster'),
            'compaction': 'Reuse existing native configuration; automatic compaction is not verified by this bundle'}}
# Skills inherited from the seed can refer to unrelated applications. Bind only explicitly reviewed skills.
for document in documents:
    if document['kind'] == 'AgentTemplate': document['spec'].pop('skills', None)
documents.append({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': config_name, 'namespace': ns}, 'immutable': True,
    'stringData': {'runtime.json': json.dumps(runtime), 'config.json': json.dumps(runtime), 'control.token': tokens['control'],
        'bridge.token': tokens['bridge'], **{r+'.authorization': 'Bearer '+tokens[r] for r in ('investigator', 'reviewer')}}})
for app, command, sa in ((backend, 'tools.py', name+'-reader'), (name+'-bridge', 'work_bridge.py', None)):
    documents += [{'apiVersion': 'v1', 'kind': 'PersistentVolumeClaim', 'metadata': {'name': app+'-data', 'namespace': ns},
        'spec': {'storageClassName': p['storage_class'], 'accessModes': ['ReadWriteOnce'], 'resources': {'requests': {'storage': '256Mi'}}}},
        {'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': app, 'namespace': ns},
            'spec': {'selector': {'app': app}, 'ports': [{'name': 'http', 'port': 8080, 'targetPort': 8080}]}},
        {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': app, 'namespace': ns}, 'spec': {'replicas': 1,
            'strategy': {'type': 'Recreate'}, 'selector': {'matchLabels': {'app': app}}, 'template': {'metadata': {'labels': {'app': app}},
                'spec': {'automountServiceAccountToken': bool(sa), **({'serviceAccountName': sa} if sa else {}),
                    'securityContext': {'runAsUser': 65532, 'runAsGroup': 65532, 'fsGroup': 65532},
                    'containers': [{'name': 'runtime', 'image': p['runtime_image'], 'command': ['python', '/app/'+command],
                        'resources': {'requests': {'cpu': '30m', 'memory': '64Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}},
                        'securityContext': {'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}},
                        'readinessProbe': {'httpGet': {'path': '/healthz', 'port': 8080}},
                        'volumeMounts': [{'name': 'config', 'mountPath': '/gitops-config', 'readOnly': True},
                            {'name': 'config', 'mountPath': '/config', 'readOnly': True}, {'name': 'data', 'mountPath': '/data'},
                            *([{'name': 'gitlab', 'mountPath': '/gitlab', 'readOnly': True}] if sa else [])]}],
                    'volumes': [{'name': 'config', 'secret': {'secretName': config_name}},
                        {'name': 'data', 'persistentVolumeClaim': {'claimName': app+'-data'}},
                        *([{'name': 'gitlab', 'secret': {'secretName': p['gitlab_secret'], 'items': [{'key': p['gitlab_secret_key'], 'path': 'gitlab.token'}]}}] if sa else [])]}}}}]
documents += [
    {'apiVersion': 'v1', 'kind': 'ServiceAccount', 'metadata': {'name': name+'-reader', 'namespace': ns}},
    {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'Role', 'metadata': {'name': name+'-reader', 'namespace': appns},
        'rules': [{'apiGroups': ['apps'], 'resources': ['deployments'], 'resourceNames': ['checkout'], 'verbs': ['get']},
            {'apiGroups': [''], 'resources': ['pods'], 'verbs': ['get', 'list']}, {'apiGroups': [''], 'resources': ['pods/log'], 'verbs': ['get']}]},
    {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding', 'metadata': {'name': name+'-reader', 'namespace': appns},
        'subjects': [{'kind': 'ServiceAccount', 'name': name+'-reader', 'namespace': ns}],
        'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': name+'-reader'}},
    {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'Role', 'metadata': {'name': name+'-flux-read', 'namespace': p['flux_namespace']},
        'rules': [{'apiGroups': ['source.toolkit.fluxcd.io'], 'resources': ['gitrepositories'], 'resourceNames': [p['flux_name']], 'verbs': ['get']},
            {'apiGroups': ['kustomize.toolkit.fluxcd.io'], 'resources': ['kustomizations'], 'resourceNames': [p['flux_name']], 'verbs': ['get']}]},
    {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding', 'metadata': {'name': name+'-flux-read', 'namespace': p['flux_namespace']},
        'subjects': [{'kind': 'ServiceAccount', 'name': name+'-reader', 'namespace': ns}],
        'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': name+'-flux-read'}},
    {'apiVersion': 'v1', 'kind': 'ServiceAccount', 'metadata': {'name': name+'-gitops', 'namespace': p['flux_namespace']}},
    {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'Role', 'metadata': {'name': name+'-gitops', 'namespace': appns},
        'rules': [{'apiGroups': ['apps'], 'resources': ['deployments'], 'verbs': ['get', 'list', 'watch', 'create', 'patch', 'update', 'delete']},
            {'apiGroups': [''], 'resources': ['services'], 'verbs': ['get', 'list', 'watch', 'create', 'patch', 'update', 'delete']}]},
    {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding', 'metadata': {'name': name+'-gitops', 'namespace': appns},
        'subjects': [{'kind': 'ServiceAccount', 'name': name+'-gitops', 'namespace': p['flux_namespace']}],
        'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': name+'-gitops'}},
    {'apiVersion': 'source.toolkit.fluxcd.io/v1', 'kind': 'GitRepository', 'metadata': {'name': p['flux_name'], 'namespace': p['flux_namespace']},
        'spec': {'interval': '15s', 'url': p['url']+'.git', 'ref': {'branch': p['target_branch']}, 'secretRef': {'name': p['git_read_secret']}}},
    {'apiVersion': 'kustomize.toolkit.fluxcd.io/v1', 'kind': 'Kustomization', 'metadata': {'name': p['flux_name'], 'namespace': p['flux_namespace']},
        'spec': {'interval': '15s', 'retryInterval': '10s', 'timeout': '1m', 'path': './deploy', 'prune': True,
            'serviceAccountName': name+'-gitops', 'targetNamespace': appns, 'sourceRef': {'kind': 'GitRepository', 'name': p['flux_name']}}}]
runtime_file = args.state/'runtime.json'
runtime_file.write_text(json.dumps(runtime, indent=2)+'\n')
(args.state/'bridge.token').write_text(tokens['bridge'])
(args.state/'resources.json').write_text('\n---\n'.join(json.dumps(d) for d in documents))
print(json.dumps({'rendered': str(args.state/'resources.json'), 'context': p['kube_context'], 'agents': agents,
    'bridge_service': name+'-bridge', 'secret_values_read': 0, 'status': 'PLAN_ONLY'}, indent=2))
