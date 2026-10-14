"""Correlate live Pi chat with native tasks, guard usage and replay admission."""
import json
import subprocess
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parent
private = root/'.data'
binding = json.loads((private/'binding.json').read_text())
token = (private/'bridge.token').read_text().strip()
base = 'http://127.0.0.1:4798/v1/sessions/'+binding['chat']['workspace_id']
def call(path, body=None, origin=base):
    request = Request(origin+path, headers={'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'},
        data=json.dumps(body).encode() if body is not None else None)
    with urlopen(request, timeout=10) as response:
        return json.load(response)

source = '''
import json,sqlite3,sys,urllib.request
from pathlib import Path
sys.path.insert(0,'/app')
import server
config=json.loads(Path('/chat-config/runtime.json').read_text())
rpc=server.RPC('kagent-controller.kagent.svc:8083')
db=sqlite3.connect('file:/data/chat.sqlite?mode=ro',uri=True); db.row_factory=sqlite3.Row
rows=[]
for record in db.execute('SELECT * FROM messages ORDER BY id'):
 row=dict(record); row.pop('task')
 if row['task_id']:
  result=rpc.call('lf.a2a.v1.A2AService','GetTask',{'tenant':'kagent/'+config['agents'][row['role']],'id':row['task_id'],'historyLength':100})
  row['nativeTask']=result.get('task',result)
 rows.append(row)
token=Path(config['model_status_token_file']).read_text().strip()
usage=json.load(urllib.request.urlopen(urllib.request.Request(config['model_status_url'],headers={'Authorization':'Bearer '+token}),timeout=5))
print(json.dumps({'contexts':config['contexts'],'agents':config['agents'],'messages':rows,'usage':usage}))
'''
def native():
    command = ['ssh', '-F', str(Path.home()/'.dpi/remote-pi/ssh_config'), 'pi-durable-proxmox',
        'kubectl --kubeconfig /home/david/pi-durable-lab/.state/local-native/kubeconfig exec -i -n kagent deploy/'+binding['app']+' -c bridge -- python -']
    return json.loads(subprocess.check_output(command, input=source, text=True))

before = native()
assert len(before['messages']) >= 2
for row in before['messages']:
    task = row['nativeTask']
    assert task['contextId'] == before['contexts'][row['role']]
    assert task['status']['state'] == 'TASK_STATE_COMPLETED'
    assert any(m.get('messageId') == row['message_id'] for m in task['history'])
first = before['messages'][0]
replayed = call('/agents/1/messages', {'content': first['content'], 'requestId': first['request_id'], 'whenBusy': 'reject'})
assert replayed['submissionId'] == first['id']
after = native()
assert after['usage']['calls'] == before['usage']['calls']
assert len(after['messages']) == len(before['messages'])
entries = call('/agents/1/entries')['items']
assistant = [m for e in entries for m in e.get('model', []) if m['role'] == 'assistant']
texts = [p['text'] for m in assistant for p in m['content'] if p['type'] == 'text']
followup = next(r for r in after['messages'] if r['content'].startswith('What demo label did I ask you to remember'))
followup_text = '\n'.join(p.get('text', '') for a in followup['nativeTask'].get('artifacts', []) for p in a.get('parts', []))
assert 'PI-CHAT-514' in followup_text and 'read_incident' in followup_text
assert any(p.get('name') == 'read_incident' for m in assistant for p in m['content'] if p['type'] == 'toolCall')
rejected = []
for case, path, body, origin in [
    ('retained incident cannot receive ordinary approval text', '/agents/1/messages',
        {'content': 'Yes, approve', 'requestId': 'not-a-native-approval', 'whenBusy': 'reject'},
        'http://127.0.0.1:4798/v1/sessions/'+binding['run_id']),
    ('requestId cannot change content', '/agents/1/messages',
        {'content': 'Different content', 'requestId': first['request_id'], 'whenBusy': 'reject'}, base),
    ('unsupported steering', '/agents/1/messages',
        {'content': 'Not admitted', 'requestId': 'unsupported-steer', 'whenBusy': 'steer'}, base)]:
    try:
        call(path, body, origin)
        raise AssertionError('Invalid admission succeeded')
    except HTTPError as error:
        assert error.code == 409
        rejected.append({'case': case, 'status': error.code})
proof = {'workspace': binding['chat']['workspace_id'], 'native': after, 'entries': entries,
    'replayedSubmission': replayed, 'rejectedAdmissions': rejected, 'contextFollowup': 'PASS', 'modelCallReplayDelta': 0}
(private/'chat-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
print(json.dumps({'workspace': proof['workspace'], 'messages': len(after['messages']), 'nativeTasks': [r['task_id'] for r in after['messages']],
    'modelRequests': after['usage']['calls'], 'reportedTokens': after['usage']['reported_tokens'],
    'contextFollowup': 'PASS', 'replayModelCalls': 0, 'rejectedAdmissions': len(rejected)}))
