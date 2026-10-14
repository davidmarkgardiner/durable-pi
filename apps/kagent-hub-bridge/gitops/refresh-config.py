"""Use the project-scoped agent token and repository-read-only Flux token."""
import json
import os
import subprocess
from pathlib import Path

os.umask(0o077)
root = Path(__file__).resolve().parent
kube = ['kubectl', '--kubeconfig', str(Path.home()/'pi-durable-lab/.state/local-native/kubeconfig')]
assert subprocess.check_output(kube+['config', 'current-context'], text=True).strip() == 'kind-pi-durable-local'
runtime = json.loads((root/'runtime.json').read_text())
docs = [
    {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'lumen-tools-config-scoped', 'namespace': 'kagent'}, 'immutable': True,
        'stringData': {'config.json': json.dumps(runtime), 'gitlab.token': (root/'gitlab.token').read_text().strip(),
            'typesafe.key': (Path.home()/'.dpi/kagent-bridge/typesafe.key').read_text().strip()}},
    {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'lumen-git', 'namespace': 'flux-lumen'},
        'stringData': json.loads((root/'flux-auth.json').read_text())},
    {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'lumen-tools-code', 'namespace': 'kagent'},
        'data': {'mcp.py': (root/'mcp.py').read_text()}}]
path = root/'scoped-config.json'
path.write_text('\n---\n'.join(json.dumps(d) for d in docs))
subprocess.run(kube+['apply', '-f', str(path)], check=True, stdout=subprocess.DEVNULL)
patch = {'spec': {'template': {'spec': {'volumes': [{'name': 'config', 'secret': {'secretName': 'lumen-tools-config-scoped'}}]},
    'metadata': {'annotations': {'demo-config': 'scoped-v2'}}}}}
subprocess.run(kube+['patch', 'deployment', 'lumen-tools', '-n', 'kagent', '--type=strategic', '-p', json.dumps(patch)], check=True, stdout=subprocess.DEVNULL)
print(json.dumps({'project': runtime['project'], 'agent_auth': 'project access token', 'flux_auth': 'read_repository deploy token'}))
