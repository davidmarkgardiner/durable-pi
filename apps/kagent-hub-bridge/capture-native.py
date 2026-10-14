"""Read native controller tasks and the independent fixture from inside the bridge pod."""
import json
import sqlite3
import sys
import urllib.request
from pathlib import Path
sys.path.insert(0, '/app')
import server as native

config=json.loads(Path('/config/runtime.json').read_text())
with sqlite3.connect('file:/data/showcase.sqlite?mode=ro',uri=True) as db:
    state=json.loads(db.execute('SELECT value FROM state WHERE id=1').fetchone()[0])
rpc=native.RPC(config['controller'])
roles={}
for role,data in state['roles'].items():
    task=rpc.call('lf.a2a.v1.A2AService','GetTask',{'tenant':'kagent/'+data['agent'],'id':data['task_id'],'historyLength':20})
    task=task.get('task',task)
    roles[role]={'agent':data['agent'],'contextId':data['context'],'taskId':data['task_id'],'state':task['status']['state'],
        'pending':native.pending(task),'tools':[p['data'] for a in task.get('artifacts',[]) for p in a.get('parts',[]) if p.get('data',{}).get('name')]}
token=Path('/config/controller.token').read_text().strip()
request=urllib.request.Request(config['fixture']+'/control/'+config['trial_id'],headers={'Authorization':'Bearer '+token})
ledger=json.load(urllib.request.urlopen(request))
print(json.dumps({'observedAt':native.now(),'native_roles':roles,'fixture':{'trial':config['trial_id'],
    'decisions':sum(e['kind']=='decision_recorded' for e in ledger['events']), 'effects':len(ledger['effects']),
    'publish_attempts':sum(e['kind']=='publish_attempt' for e in ledger['events']), 'ledger':ledger}},indent=2))
