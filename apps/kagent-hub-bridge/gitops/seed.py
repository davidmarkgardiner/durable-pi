"""Create the dedicated private repository; secrets and receipts stay in ignored state."""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument('--state', type=Path, required=True)
args = parser.parse_args()
os.umask(0o077)
args.state.mkdir(parents=True, exist_ok=True)
auth = subprocess.run(['glab', 'auth', 'status', '--hostname', 'gitlab.com', '--show-token'], capture_output=True, text=True, check=True)
token = re.search(r'Token found: (\S+)', auth.stdout+auth.stderr).group(1)


def api(path, method='GET', body=None):
    req = Request('https://gitlab.com/api/v4/'+path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'})
    with urlopen(req, timeout=30) as response:
        return json.load(response)


path = 'davidmarkgardiner/durable-pi-lumen-gitops'
try:
    project = api('projects/'+quote(path, safe=''))
except HTTPError as error:
    if error.code != 404:
        raise
    project = api('projects', 'POST', {'name': 'Durable Pi Lumen GitOps', 'path': 'durable-pi-lumen-gitops',
        'visibility': 'private', 'initialize_with_readme': True, 'default_branch': 'main',
        'description': 'Isolated synthetic checkout rollback and human-approved native kagent demo.'})
identity = project['id']
deployment = {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'checkout', 'namespace': 'lumen-gitops'},
    'spec': {'replicas': 1, 'selector': {'matchLabels': {'app': 'lumen-checkout'}}, 'template': {
        'metadata': {'labels': {'app': 'lumen-checkout'}}, 'spec': {'automountServiceAccountToken': False,
            'containers': [{'name': 'checkout', 'image': 'lumen-checkout:v1', 'imagePullPolicy': 'Never',
                'ports': [{'containerPort': 8080}], 'readinessProbe': {'httpGet': {'path': '/healthz', 'port': 8080}},
                'resources': {'requests': {'cpu': '10m', 'memory': '24Mi'}, 'limits': {'cpu': '100m', 'memory': '64Mi'}}}]}}}}
service = {'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'checkout', 'namespace': 'lumen-gitops'},
    'spec': {'selector': {'app': 'lumen-checkout'}, 'ports': [{'port': 8080, 'targetPort': 8080}]}}
tests = '''import importlib.util,json,os,unittest
from pathlib import Path
os.environ['APP_VERSION']='v1'
spec=importlib.util.spec_from_file_location('app','application.py')
app=importlib.util.module_from_spec(spec); spec.loader.exec_module(app)
class Checkout(unittest.TestCase):
 def test_guest(self): self.assertEqual(app.checkout({'name':'Guest'})['total'],20)
 def test_loyalty(self): self.assertEqual(app.checkout({'loyalty':{'discount':3}})['total'],17)
 def test_regression(self):
  app.VERSION='v2'
  try:
   with self.assertRaises(KeyError): app.checkout({'name':'Guest'})
  finally: app.VERSION='v1'
 def test_manifest(self):
  d=json.loads(Path('deploy/deployment.json').read_text())
  self.assertEqual(d['metadata']['namespace'],'lumen-gitops')
  self.assertIn(d['spec']['template']['spec']['containers'][0]['image'],('lumen-checkout:v1','lumen-checkout:v2'))
if __name__=='__main__': unittest.main()
'''
files = {'application.py': (Path(__file__).parent/'application.py').read_text(),
    'deploy/deployment.json': json.dumps(deployment, indent=2)+'\n',
    'deploy/service.json': json.dumps(service, indent=2)+'\n',
    'deploy/kustomization.yaml': 'resources:\n  - deployment.json\n  - service.json\n',
    'test_checkout.py': tests,
    '.gitlab-ci.yml': 'image: python:3.12-slim\nstages: [test]\ncheckout-tests:\n  stage: test\n  script: ["python -m unittest -v test_checkout"]\n',
    'README.md': '# Lumen checkout rollback demo\n\nSynthetic app; real GitLab MR, native kagent approval and Flux rollout. v2 breaks guest checkout. v1 is the known healthy image. Only deploy/deployment.json may change in the rollback MR.\n'}
if not (args.state/'seed.json').exists():
    actions = []
    for name, content in files.items():
        tree = api(f'projects/{identity}/repository/tree?per_page=100&recursive=true')
        actions.append({'action': 'update' if any(x['path'] == name for x in tree) else 'create', 'file_path': name, 'content': content})
    commit = api(f'projects/{identity}/repository/commits', 'POST', {'branch': 'main',
        'commit_message': 'Seed isolated checkout and GitOps deployment', 'actions': actions})
    (args.state/'seed.json').write_text(json.dumps({'project': identity, 'path': path, 'url': project['web_url'],
        'baseline_sha': commit['id']}, indent=2)+'\n')
(args.state/'gitlab.token').write_text(token)
print((args.state/'seed.json').read_text())
