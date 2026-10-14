"""Raise this workflow's request-size ceiling without resetting or increasing its allowance."""
import json
import subprocess
from pathlib import Path

root = Path.home()/'.dpi/kagent-bridge'
binding = json.loads((root/'run-20261014/binding.json').read_text())
name = binding['gitops']['model']
kube = ['kubectl', '--kubeconfig', str(Path.home()/'pi-durable-lab/.state/local-native/kubeconfig')]
source = (Path.home()/'pi-durable-lab/model_guard.py').read_text()
assert 'size > 16384' in source
source = source.replace('size > 16384', 'size > 65536').replace('Request must fit within 16 KiB', 'Request must fit within 64 KiB')
doc = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': name+'-code-64k', 'namespace': 'kagent'},
    'immutable': True, 'data': {'model_guard.py': source}}
path = root/'gitops/guard-64k.json'
path.write_text(json.dumps(doc))
subprocess.run(kube+['apply', '-f', str(path)], check=True, stdout=subprocess.DEVNULL)
patch = {'spec': {'template': {'spec': {'volumes': [{'name': 'code', 'configMap': {'name': name+'-code-64k'}}]}}}}
subprocess.run(kube+['patch', 'deployment', name, '-n', 'kagent', '--type=strategic', '-p', json.dumps(patch)], check=True, stdout=subprocess.DEVNULL)
print(json.dumps({'model_guard': name, 'max_request_bytes': 65536, 'budget_reset': False, 'allowance_changed': False}))
