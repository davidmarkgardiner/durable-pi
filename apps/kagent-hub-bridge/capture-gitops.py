"""Read live proof through independent native, GitLab and Kubernetes paths."""
import argparse
import json
import os
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument('--expect', choices=['awaiting_approval', 'completed'], required=True)
args = parser.parse_args()
os.umask(0o077)
root = Path(__file__).resolve().parent
binding = json.loads((root/'.data/binding.json').read_text())
ssh = ['ssh', '-F', str(Path.home()/'.dpi/remote-pi/ssh_config'), 'pi-durable-proxmox']
kube = 'kubectl --kubeconfig /home/david/pi-durable-lab/.state/local-native/kubeconfig'
command = kube+' exec -i -n kagent deploy/'+binding['app']+' -c bridge -- python -'
raw = subprocess.check_output(ssh+[command], input=(root/'capture-gitops-native.py').read_text(), text=True, timeout=60)
proof = json.loads(raw)
assert proof['workflow']['phase'] == args.expect, 'Native workflow is not at the requested proof stage'
mr_binding = proof['ledger']['mr']['binding']
token = (root/'.data/gitops/gitlab.token').read_text().strip()


def api(path):
    request = Request('https://gitlab.com/api/v4/projects/'+str(mr_binding['project'])+'/'+path,
        headers={'Authorization': 'Bearer '+token})
    with urlopen(request, timeout=15) as response:
        return json.load(response)


mr = api('merge_requests/'+str(mr_binding['iid']))
diffs = api('merge_requests/'+str(mr_binding['iid'])+'/diffs')
pipeline = api('pipelines/'+str(proof['ledger']['mr_info']['pipeline']['id']))
jobs = api('pipelines/'+str(pipeline['id'])+'/jobs')
trace = api('repository/commits/'+mr_binding['head_sha'])
assert mr['sha'] == mr_binding['head_sha'] and mr['target_branch'] == 'main'
assert len(diffs) == 1 and diffs[0]['old_path'] == diffs[0]['new_path'] == 'deploy/deployment.json'
assert pipeline['sha'] == mr_binding['head_sha'] and pipeline['status'] == 'success'
assert any(j['name'] == 'checkout-tests' and j['status'] == 'success' for j in jobs)
assert mr['state'] == ('opened' if args.expect == 'awaiting_approval' else 'merged')
deployment = json.loads(subprocess.check_output(ssh+[kube+' get deployment checkout -n lumen-gitops -o json'], text=True, timeout=15))
pods = json.loads(subprocess.check_output(ssh+[kube+' get pods -n lumen-gitops -l app=lumen-checkout -o json'], text=True, timeout=15))
expected = 'lumen-checkout:v2' if args.expect == 'awaiting_approval' else 'lumen-checkout:v1'
assert deployment['spec']['template']['spec']['containers'][0]['image'] == expected
proof['independent_gitlab'] = {'mr': mr, 'diffs': diffs, 'pipeline': pipeline, 'jobs': jobs, 'commit': trace}
proof['independent_kubernetes'] = {'deployment': deployment, 'pods': pods}
path = root/'.data'/('gitops-'+args.expect+'-proof.json')
path.write_text(json.dumps(proof, indent=2)+'\n')
print(json.dumps({'proof': str(path), 'phase': args.expect, 'mr': mr['web_url'], 'head': mr['sha'],
    'pipeline': pipeline['id'], 'pipeline_status': pipeline['status'], 'live_image': expected,
    'classifier_calls': proof['ledger']['calls'], 'model_calls': proof['budget']['calls'],
    'reported_tokens': proof['budget']['reported_tokens'], 'decision_recorded': bool(proof['ledger'].get('decision')),
    'merged_sha': mr.get('merge_commit_sha')}, indent=2))
