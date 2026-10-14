"""Prepare a dedicated GitLab demo repository. Default is a local plan; --commit writes once."""
import argparse
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from profile import load

ROOT = Path(__file__).resolve().parents[1]


def repository_files(p):
    pod = {'metadata': {'labels': {'app': 'lumen-checkout'}}, 'spec': {
        'automountServiceAccountToken': False, 'securityContext': {'runAsUser': 65532, 'runAsGroup': 65532},
        'containers': [{'name': 'checkout', 'image': p['healthy_image'], 'ports': [{'containerPort': 8080}],
            'readinessProbe': {'httpGet': {'path': '/healthz', 'port': 8080}},
            'securityContext': {'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}},
            'resources': {'requests': {'cpu': '20m', 'memory': '32Mi'}, 'limits': {'cpu': '250m', 'memory': '128Mi'}}}]}}
    deployment = {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'checkout'},
        'spec': {'replicas': 1, 'selector': {'matchLabels': {'app': 'lumen-checkout'}}, 'template': pod}}
    service = {'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'checkout'}, 'spec': {
        'selector': {'app': 'lumen-checkout'}, 'ports': [{'name': 'http', 'port': 8080, 'targetPort': 8080}]}}
    return {'application.py': (ROOT/'runtime/application.py').read_text(),
        'test_checkout.py': (ROOT/'tests/test_application.py').read_text(),
        'deploy/deployment.json': json.dumps(deployment, indent=2)+'\n',
        'deploy/service.json': json.dumps(service, indent=2)+'\n',
        'deploy/kustomization.yaml': 'apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources:\n  - deployment.json\n  - service.json\n',
        '.gitlab-ci.yml': 'checkout-tests:\n  image: python:3.12.12-slim-bookworm\n  script:\n    - python -m unittest -v test_checkout\n    - python -c "import json; d=json.load(open(\'deploy/deployment.json\')); assert d[\'spec\'][\'template\'][\'spec\'][\'containers\'][0][\'image\'] == \'%s\'"\n  rules:\n    - if: $CI_PIPELINE_SOURCE == "merge_request_event"\n    - if: $CI_COMMIT_BRANCH\n' % p['healthy_image'],
        'PI-WORK-DEMO.json': json.dumps({'run_id': p['run_id'], 'application_namespace': p['application_namespace'], 'synthetic': True}, indent=2)+'\n'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--token-file', type=Path)
    parser.add_argument('--commit', action='store_true')
    args = parser.parse_args()
    p = load(args.profile)
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=False)
    files = repository_files(p)
    for name, content in files.items():
        path = args.output/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    subprocess.run(['python3', '-m', 'unittest', '-v', 'test_checkout'], cwd=args.output, check=True)
    subprocess.run(['kubectl', '--context', p['kube_context'], 'kustomize', str(args.output/'deploy')], check=True, stdout=subprocess.DEVNULL)
    if not args.commit:
        print('PLAN_ONLY: repository files generated and checked. No GitLab write.')
        return
    if not args.token_file: raise SystemExit('--commit requires a private --token-file; do not paste a token into commands or logs')
    token = args.token_file.read_text().strip()
    def api(path='', body=None):
        request = Request(p['gitlab_api'].rstrip('/')+'/projects/'+str(p['project'])+path,
            data=json.dumps(body).encode() if body else None,
            headers={'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'})
        with urlopen(request, timeout=25) as response: return json.load(response)
    project = api()
    if project['web_url'].rstrip('/') != p['url'].rstrip('/'):
        raise SystemExit('Project ID and configured URL do not match')
    if not project.get('empty_repo'):
        raise SystemExit('Seed accepts only an empty dedicated repository. Do not overwrite an existing application.')
    receipt = api('/repository/commits', {'branch': p['target_branch'], 'commit_message': 'Seed scoped synthetic Pi checkout demo',
        'actions': [{'action': 'create', 'file_path': name, 'content': content} for name,content in files.items()]})
    (args.output/'seed-receipt.json').write_text(json.dumps({'project': p['project'], 'sha': receipt['id'], 'url': receipt['web_url']}, indent=2)+'\n')
    print(json.dumps({'status': 'SEEDED', 'sha': receipt['id'], 'url': receipt['web_url']}))


if __name__ == '__main__': main()
