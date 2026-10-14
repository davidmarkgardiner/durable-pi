"""Preserve all existing volumes and sessions while updating the bridge container."""
import json
import argparse
import subprocess
from pathlib import Path

root = Path.home()/'.dpi/kagent-bridge'
parser = argparse.ArgumentParser()
parser.add_argument('--image', required=True)
args = parser.parse_args()
path = root/'run-20261014/binding.json'
binding = json.loads(path.read_text())
kube = ['kubectl', '--kubeconfig', str(Path.home()/'pi-durable-lab/.state/local-native/kubeconfig')]
assert subprocess.check_output(kube+['config', 'current-context'], text=True).strip() == 'kind-pi-durable-local'
deployment = json.loads(subprocess.check_output(kube+['get', 'deployment', binding['app'], '-n', 'kagent', '-o', 'json'], text=True))
pod = deployment['spec']['template']['spec']
image = args.image
for container in pod['containers']+pod.get('initContainers', []):
    container['image'] = image
subprocess.run(kube+['patch', 'deployment', binding['app'], '-n', 'kagent', '--type=merge', '-p', json.dumps({'spec': {'template': {'spec': pod}}})], check=True)
binding['image'] = image
path.write_text(json.dumps(binding, indent=2)+'\n')
