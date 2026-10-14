"""Read native TaskStore and independent tool ledger; never approve or merge."""
import datetime
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, '/bridge')
import server
from gitops import GitOps, outputs
from wire import approval

config = json.loads(Path('/gitops-config/runtime.json').read_text())
workflow = GitOps(config, server.RPC('kagent-controller.kagent.svc:8083'))
state = workflow.backend()
native = []
for row in workflow.rows():
    if row['task_id']:
        reply = workflow.call(row['role'], 'GetTask', {'id': row['task_id'], 'historyLength': 100})
        native.append({'role': row['role'], 'request_id': row['request_id'], 'task': reply.get('task', reply)})
token = Path(config['model_status_token_file']).read_text().strip()
with urlopen(Request(config['model_status_url'], headers={'Authorization': 'Bearer '+token}), timeout=5) as response:
    budget = json.load(response)
proof = {'collected_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'workspace': config['workspace_id'], 'contexts': config['contexts'], 'workflow': workflow.workflow(),
    'ledger': state, 'native_tasks': native, 'budget': budget}
if workflow.workflow()['phase'] == 'awaiting_approval':
    candidates = [r['task'] for r in native if r['role'] == 'investigator' and r['task']['status']['state'] == 'TASK_STATE_INPUT_REQUIRED']
    assert len(candidates) == 1
    tools = approval(candidates[0])['tools']
    assert len(tools) == 1 and tools[0]['name'] == 'merge_mr' and tools[0]['args']['request'] == state['mr']['binding']
    assert state['mr_info']['state'] == 'opened' and state['mr_info']['diff_valid'] and state['mr_info']['ci_pass']
    assert state['review']['binding'] == state['mr']['binding'] and state['review']['verdict'] == 'PASS'
    assert not state.get('decision') and not state.get('merged') and not state.get('merge_attempted')
if workflow.workflow()['phase'] == 'completed':
    assert state['verification']['fixed'] and state['mr_info']['state'] == 'merged'
    assert any(o.get('fixed') is True for r in native for o in outputs(r['task'], 'verify_application'))
print(json.dumps(proof))
