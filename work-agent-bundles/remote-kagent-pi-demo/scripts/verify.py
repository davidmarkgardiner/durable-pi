"""Read current receipts over the authenticated Pi HTTP endpoint. Never submits approval."""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'runtime'))
from gitops import outputs
from wire import approval
from profile import load

parser = argparse.ArgumentParser()
parser.add_argument('--profile', required=True)
parser.add_argument('--state', type=Path, required=True)
parser.add_argument('--expect', choices=['connected', 'awaiting_approval', 'completed'], required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
p = load(args.profile)
token = (args.state/'bridge.token').read_text().strip()
with urlopen(Request(p['bridge_url'].rstrip('/')+'/v1/demo-proof', headers={'Authorization': 'Bearer '+token}), timeout=40) as response:
    proof = json.load(response)
assert proof['version']['kagentVersion'].lstrip('v').startswith('1.'), 'Native controller version mismatch'
assert len(set(proof['contexts'].values())) == 2, 'Two distinct native contexts required'
if args.expect != 'connected':
    observed, workflow = proof['observed'], proof['workflow']
    trigger = observed['trigger']
    assert trigger['source'] == 'Synthetic decision (scripted HTTP rule)', 'Synthetic source must be explicit'
    samples = trigger['incident_samples']
    assert len(samples) == 3 and all(s['sample']['status'] == 500 and s['sample']['body']['version'] == 'v2' and s['result']['synthetic'] is True for s in samples), 'Real v2 failures and labelled scripted decisions required'
    initial = next(r for r in proof['tasks'] if r['request_id'] == 'classified-checkout-incident')
    task = initial['task']
    assert task['contextId'] == proof['contexts']['investigator']
    assert any(m['messageId'] == initial['message_id'] and '\n'.join(part.get('text', '') for part in m.get('parts', [])) == initial['instruction'] for m in task['history']), 'Native initial instruction not confirmed'
    binding = observed['mr']['binding']
    mr = observed['mr_info']
    assert mr['binding'] == binding and mr['diff_valid'] is True and mr['ci_pass'] is True, 'Exact diff or current-head CI failed'
    assert observed['review']['binding'] == binding and observed['review']['verdict'] == 'PASS'
    review = next(r['task'] for r in proof['tasks'] if r['request_id'] == 'review-rollback')
    assert review['id'] == observed['review']['task_id'] and review['status']['state'] == 'TASK_STATE_COMPLETED'
    assert any(c.get('binding') == binding and c.get('diff_valid') is True and c.get('ci_pass') is True for c in outputs(review, 'inspect_mr')), 'Native reviewer MCP receipt missing'
    if args.expect == 'awaiting_approval':
        assert workflow['phase'] == 'awaiting_approval' and not observed.get('decision') and mr['state'] == 'opened'
        pending = [r['task'] for r in proof['tasks'] if r['role'] == 'investigator' and r['task']['status']['state'] == 'TASK_STATE_INPUT_REQUIRED']
        assert len(pending) == 1
        tools = approval(pending[0])['tools']
        assert len(tools) == 1 and tools[0]['name'] == 'merge_mr' and tools[0]['args']['request'] == binding
    else:
        assert workflow['phase'] == 'completed' and observed['decision']['approved'] is True and observed['decision']['binding'] == binding
        verify = observed['verification']
        assert mr['state'] == 'merged' and mr['merge_commit_sha'] == verify['merged_sha']
        expected_revision = p['target_branch']+'@sha1:'+verify['merged_sha']
        assert verify['fixed'] is True and verify['flux_applied_revision'] == verify['source_revision'] == expected_revision
        assert verify['deployment']['image'] == p['healthy_image']
        probes = verify['probes']
        assert len(probes) == 3 and all(q['status'] == 200 and q['body']['version'] == 'v1' and q['body']['total'] == 20 for q in probes)
        native = next(r['task'] for r in proof['tasks'] if r['request_id'] == 'post-flux-verification')
        assert native['status']['state'] == 'TASK_STATE_COMPLETED'
        assert any(c.get('fixed') is True and c.get('merged_sha') == verify['merged_sha'] for c in outputs(native, 'verify_application')), 'Native final verification receipt missing'
os.umask(0o077)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(proof, indent=2)+'\n')
print(json.dumps({'status': 'PASS_'+args.expect.upper(), 'receipt': str(args.output), 'actions_submitted': 0}))
