"""Capture the live bridge and reject malformed approvals without choosing a decision."""
import datetime
import copy
import json
import subprocess
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen

root=Path(__file__).resolve().parent
private=root/'.data'
binding=json.loads((private/'binding.json').read_text())
token=(private/'bridge.token').read_text().strip()
base='http://127.0.0.1:4798'

def call(path,body=None):
    request=Request(base+path,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},
        data=json.dumps(body).encode() if body is not None else None)
    with urlopen(request,timeout=15) as response:return json.load(response)

session='/v1/sessions/'+binding['run_id']
info=call('/v1/device')
shared=call('/v1/docs/app.shared-state')['value']['proactive']
capabilities={role:call(session+'/agents/'+str(identity)) for role,identity in [('investigator',1),('reviewer',2)]}
assert any(t.get('requireApproval') and t['name']=='publish_proposal' for t in capabilities['investigator']['tools'])
assert 'publish_proposal' not in [t['name'] for t in capabilities['reviewer']['tools']]
doc=call(session+'/agents/1/docs/demo.job-runs')['value']
job=next(iter(doc['items'].values()))
rejected=[]
if job.get('approval')=='pending':
    stale=copy.deepcopy(job['approvalBinding'])
    stale['request']['proposal_hash']='not-the-displayed-proposal'
    for case,identity,body in [
        ('wrong task','not-the-task',{'approved':True,'binding':job['approvalBinding']}),
        ('non-boolean decision',str(job['id']),{'approved':'invalid','binding':job['approvalBinding']}),
        ('missing binding',str(job['id']),{'approved':True}),
        ('stale proposal',str(job['id']),{'approved':True,'binding':stale})]:
        try:
            call(session+'/agents/1/demo/jobs/'+identity+'/approval',body)
            raise AssertionError('Invalid decision was accepted')
        except HTTPError as error:
            assert error.code==409
            rejected.append({'case':case,'httpStatus':error.code})
source=(root/'capture-native.py').read_text()
command=['ssh','-F',str(Path.home()/'.dpi/remote-pi/ssh_config'),'pi-durable-proxmox',
    'kubectl --kubeconfig /home/david/pi-durable-lab/.state/local-native/kubeconfig exec -i -n kagent deploy/'+binding['app']+' -c bridge -- python -']
native=json.loads(subprocess.check_output(command,input=source,text=True))
if job.get('approval')=='pending':
    assert native['fixture']['decisions']==native['fixture']['effects']==native['fixture']['publish_attempts']==0
    assert native['native_roles']['investigator']['state']=='TASK_STATE_INPUT_REQUIRED'
proof={'observedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'status':'APPROVAL_PENDING' if job.get('approval')=='pending' else job['status'],
    'ui':'http://127.0.0.1:4781/','device':info,'classifier':shared['classifier'],'trigger':shared['trigger'],
    'classifiedRows':[r for r in shared['logs'] if r.get('classification')=='judged'],
    'review':shared['review'],'actors':shared['nativeActors'],'native':native,'approvalDisplay':job,
    'capabilities':{role:{'tools':d['tools'],'inventory':d.get('capabilityInventory')} for role,d in capabilities.items()},
    'rejectedInvalidApprovals':rejected,'scope':shared['scope']}
(private/'live-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'status':proof['status'],'jevRequests':proof['classifier']['requests'],
    'triggerLogIds':proof['trigger']['logIds'],'nativeTask':native['native_roles']['investigator']['taskId'],
    'review':proof['review']['verdict'],'fixtureEffects':native['fixture']['effects'],'invalidDecisionChecks':len(rejected)}))
