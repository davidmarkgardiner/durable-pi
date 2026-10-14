"""Install this demo in the isolated Pi Kind cluster, never the older work contexts."""
import json
import os
import secrets
import subprocess
from pathlib import Path

os.umask(0o077)
root = Path(__file__).resolve().parent
lab = Path.home()/'pi-durable-lab'
kube = ['kubectl', '--kubeconfig', str(lab/'.state/local-native/kubeconfig')]


def k(*args, body=None):
    return subprocess.check_output(kube+list(args), input=body, text=True, timeout=180).strip()


assert k('config', 'current-context') == 'kind-pi-durable-local'
seed = json.loads((root/'seed.json').read_text())
if (root/'runtime.json').exists():
    raise SystemExit('Demo already provisioned; retain its state')
tokens = {role: secrets.token_urlsafe(32) for role in ('investigator', 'reviewer', 'control')}
runtime = {**seed, 'tokens': tokens}
(root/'runtime.json').write_text(json.dumps(runtime))
for version in ('v1', 'v2'):
    subprocess.run(['docker', 'build', '-f', str(root/'Dockerfile.app'), '--build-arg', 'APP_VERSION='+version,
        '-t', 'lumen-checkout:'+version, str(root)], check=True, timeout=180)
    subprocess.run(['kind', 'load', 'docker-image', '--name', 'pi-durable-local', 'lumen-checkout:'+version], check=True, timeout=180)
k('apply', '-f', str(root/'flux.yaml'))
docs = [
    {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': 'lumen-gitops'}},
    {'apiVersion': 'v1', 'kind': 'ServiceAccount', 'metadata': {'name': 'lumen-reconciler', 'namespace': 'lumen-gitops'}},
    {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'Role', 'metadata': {'name': 'lumen-reconciler', 'namespace': 'lumen-gitops'},
        'rules': [{'apiGroups': ['apps'], 'resources': ['deployments'], 'verbs': ['get', 'list', 'watch', 'create', 'patch', 'update', 'delete']},
            {'apiGroups': [''], 'resources': ['services'], 'verbs': ['get', 'list', 'watch', 'create', 'patch', 'update', 'delete']}]},
    {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding', 'metadata': {'name': 'lumen-reconciler', 'namespace': 'lumen-gitops'},
        'subjects': [{'kind': 'ServiceAccount', 'name': 'lumen-reconciler', 'namespace': 'lumen-gitops'}],
        'roleRef': {'kind': 'Role', 'name': 'lumen-reconciler', 'apiGroup': 'rbac.authorization.k8s.io'}},
    {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'lumen-git', 'namespace': 'flux-lumen'},
        'stringData': {'username': 'oauth2', 'password': (root/'gitlab.token').read_text().strip()}},
    {'apiVersion': 'source.toolkit.fluxcd.io/v1', 'kind': 'GitRepository', 'metadata': {'name': 'lumen', 'namespace': 'flux-lumen'},
        'spec': {'interval': '15s', 'url': seed['url']+'.git', 'ref': {'branch': 'main'}, 'secretRef': {'name': 'lumen-git'}}},
    {'apiVersion': 'kustomize.toolkit.fluxcd.io/v1', 'kind': 'Kustomization', 'metadata': {'name': 'lumen', 'namespace': 'flux-lumen'},
        'spec': {'interval': '15s', 'retryInterval': '10s', 'path': './deploy', 'prune': True,
            'targetNamespace': 'lumen-gitops', 'serviceAccountName': 'lumen-reconciler',
            'sourceRef': {'kind': 'GitRepository', 'name': 'lumen'}, 'timeout': '1m'}},
    {'apiVersion': 'v1', 'kind': 'ServiceAccount', 'metadata': {'name': 'lumen-reconciler', 'namespace': 'flux-lumen'}},
    {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding', 'metadata': {'name': 'flux-lumen-reconciler', 'namespace': 'lumen-gitops'},
        'subjects': [{'kind': 'ServiceAccount', 'name': 'lumen-reconciler', 'namespace': 'flux-lumen'}],
        'roleRef': {'kind': 'Role', 'name': 'lumen-reconciler', 'apiGroup': 'rbac.authorization.k8s.io'}},
    {'apiVersion': 'v1', 'kind': 'ServiceAccount', 'metadata': {'name': 'lumen-tools', 'namespace': 'kagent'}},
    {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'Role', 'metadata': {'name': 'lumen-tools', 'namespace': 'lumen-gitops'},
        'rules': [{'apiGroups': ['apps'], 'resources': ['deployments'], 'resourceNames': ['checkout'], 'verbs': ['get']},
            {'apiGroups': [''], 'resources': ['pods'], 'verbs': ['get', 'list']},
            {'apiGroups': [''], 'resources': ['pods/log'], 'verbs': ['get']}]},
    {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding', 'metadata': {'name': 'lumen-tools', 'namespace': 'lumen-gitops'},
        'subjects': [{'kind': 'ServiceAccount', 'name': 'lumen-tools', 'namespace': 'kagent'}],
        'roleRef': {'kind': 'Role', 'name': 'lumen-tools', 'apiGroup': 'rbac.authorization.k8s.io'}},
    {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'Role', 'metadata': {'name': 'lumen-tools', 'namespace': 'flux-lumen'},
        'rules': [{'apiGroups': ['source.toolkit.fluxcd.io'], 'resources': ['gitrepositories'], 'resourceNames': ['lumen'], 'verbs': ['get']},
            {'apiGroups': ['kustomize.toolkit.fluxcd.io'], 'resources': ['kustomizations'], 'resourceNames': ['lumen'], 'verbs': ['get']}]},
    {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding', 'metadata': {'name': 'lumen-tools', 'namespace': 'flux-lumen'},
        'subjects': [{'kind': 'ServiceAccount', 'name': 'lumen-tools', 'namespace': 'kagent'}],
        'roleRef': {'kind': 'Role', 'name': 'lumen-tools', 'apiGroup': 'rbac.authorization.k8s.io'}},
    {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'lumen-tools-config', 'namespace': 'kagent'}, 'immutable': True,
        'stringData': {'config.json': json.dumps(runtime), 'gitlab.token': (root/'gitlab.token').read_text().strip(),
            'typesafe.key': (Path.home()/'.dpi/kagent-bridge/typesafe.key').read_text().strip()}},
    {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'lumen-tools-code', 'namespace': 'kagent'},
        'data': {'mcp.py': (root/'mcp.py').read_text()}},
    {'apiVersion': 'v1', 'kind': 'PersistentVolumeClaim', 'metadata': {'name': 'lumen-tools-data', 'namespace': 'kagent'},
        'spec': {'accessModes': ['ReadWriteOnce'], 'resources': {'requests': {'storage': '256Mi'}}}},
    {'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'lumen-tools', 'namespace': 'kagent'},
        'spec': {'selector': {'app': 'lumen-tools'}, 'ports': [{'port': 8080, 'targetPort': 8080}]}},
    {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'lumen-tools', 'namespace': 'kagent'},
        'spec': {'replicas': 1, 'strategy': {'type': 'Recreate'}, 'selector': {'matchLabels': {'app': 'lumen-tools'}},
            'template': {'metadata': {'labels': {'app': 'lumen-tools'}}, 'spec': {'serviceAccountName': 'lumen-tools',
                'securityContext': {'runAsUser': 65532, 'runAsGroup': 65532, 'fsGroup': 65532},
                'containers': [{'name': 'tools', 'image': 'durable-agent-showcase:20261014-3', 'imagePullPolicy': 'Never',
                    'command': ['python', '/code/mcp.py'], 'readinessProbe': {'httpGet': {'path': '/healthz', 'port': 8080}},
                    'resources': {'requests': {'cpu': '20m', 'memory': '48Mi'}, 'limits': {'cpu': '300m', 'memory': '192Mi'}},
                    'securityContext': {'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}},
                    'volumeMounts': [{'name': 'config', 'mountPath': '/config', 'readOnly': True},
                        {'name': 'code', 'mountPath': '/code', 'readOnly': True}, {'name': 'data', 'mountPath': '/data'}]}],
                'volumes': [{'name': 'config', 'secret': {'secretName': 'lumen-tools-config'}},
                    {'name': 'code', 'configMap': {'name': 'lumen-tools-code'}},
                    {'name': 'data', 'persistentVolumeClaim': {'claimName': 'lumen-tools-data'}}]}}}}]
resources = root/'resources.json'
resources.write_text('\n---\n'.join(json.dumps(d) for d in docs))
k('apply', '-f', str(resources))
print(json.dumps({'project': seed['project'], 'namespace': 'lumen-gitops', 'flux': 'v2.9.6', 'tools': 'lumen-tools'}))
