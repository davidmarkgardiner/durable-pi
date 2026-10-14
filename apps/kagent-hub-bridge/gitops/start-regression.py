"""Capture healthy live evidence before committing the isolated demo regression."""
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('rollback', '/code/mcp.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
backend = module.Rollback(json.loads(Path('/config/config.json').read_text()))
state = backend.state()
if state.get('regression_commit'):
    print(json.dumps({'already_started': True, 'sha': state['regression_commit']}))
    raise SystemExit()
probes = [backend.probe() for _ in range(3)]
deployment = backend.read_deployment({})
manifest, baseline_sha = backend.manifest()
if not all(p['status'] == 200 and p['body'].get('version') == 'v1' for p in probes) or deployment['image'] != 'lumen-checkout:v1':
    raise SystemExit('Healthy application baseline is not verified. Do not inject a fault')
if manifest['spec']['template']['spec']['containers'][0]['image'] != 'lumen-checkout:v1':
    raise SystemExit('Main is not at the healthy baseline')
backend.save(baseline={'probes': probes, 'deployment': deployment, 'sha': baseline_sha})
manifest['spec']['template']['spec']['containers'][0]['image'] = 'lumen-checkout:v2'
commit = backend.api('repository/commits', 'POST', {'branch': 'main', 'commit_message': 'Demo setup: deploy v2 guest-checkout regression',
    'actions': [{'action': 'update', 'file_path': 'deploy/deployment.json', 'content': json.dumps(manifest, indent=2)+'\n'}]})
backend.save(regression_commit=commit['id'])
print(json.dumps({'baseline_statuses': [p['status'] for p in probes], 'baseline_image': deployment['image'], 'regression_commit': commit['id']}))
