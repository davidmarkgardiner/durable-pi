"""Create fresh POC resources in the already-installed isolated Proxmox lab."""
import argparse
import importlib.util
import json
import os
import secrets
import subprocess
import time
import uuid
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--lab-dir', type=Path, default=Path.home()/'pi-durable-lab')
parser.add_argument('--key-file', type=Path, required=True)
parser.add_argument('--image', required=True)
parser.add_argument('--state', type=Path, required=True)
options=parser.parse_args()
os.umask(0o077)
options.state.mkdir(parents=True, exist_ok=False)
os.chdir(options.lab_dir)
spec=importlib.util.spec_from_file_location('deploy_helpers', 'showcase/deploy.py')
helper=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
k=helper.k
assert k('config','current-context')=='kind-pi-durable-local'
suffix=secrets.token_hex(4)
run='proactive-'+suffix
app='pi-hub-bridge-'+suffix
model='pi-hub-model-'+suffix
trial='proactive-'+suffix
fixture_task='proactive-task-'+suffix
op='proactive-operation'
decision='proactive-human-decision'
created=helper.controller('trials', {'trial_id':trial,'task_id':fixture_task,'arm':'native','mode':'protected'})
cap=created['agent_token']
roles={}
clients=[]
model_tokens={}
resources=[]
for role,client in [('investigator','native'),('reviewer','reviewer')]:
    identity=suffix+('01' if role=='investigator' else '02')
    name='durable-native-agent-'+identity
    roles[role]=name
    token=secrets.token_urlsafe(32)
    model_tokens[client+'.token']=token
    clients.append({'name':client,'token_file':client+'.token','op_id':op,'decision_id':decision,'trial_id':trial,'fixture_task_id':fixture_task})
    template=Path('native-agent-bindings.yaml').read_text().replace('{{SUFFIX}}',identity).replace('{{FIXTURE_TASK_ID}}',fixture_task)
    docs=[json.loads(k('create','--dry-run=client','-f','-','-o','json',body=v)) for v in template.split('---\n') if v.strip()]
    docs=[d for d in docs if d['kind']!='ModelConfig']
    for doc in docs:
        if doc['kind']=='AgentTemplate':
            doc['spec']['modelConfig']={'name':model+'-'+client}
            doc['spec']['description']='Proactive hub POC '+role
            if role=='reviewer':
                doc['spec']['tools']=[{'mcp':{'server':{'kind':'RemoteMCPServer','name':'durable-native-fixture-'+identity},'tools':['read_incident','get_operation','read_result']}}]
                doc['spec']['systemPrompt']='Read the synthetic incident and proposal ledger. Review only. Never publish, record proposals or modify state. Return a verdict for the exact proposal hash and revision.'
    docs.extend([
        {'apiVersion':'v1','kind':'Secret','metadata':{'name':'durable-native-cap-'+identity,'namespace':'kagent'},'stringData':{'Authorization':'Bearer '+cap}},
        {'apiVersion':'v1','kind':'Secret','metadata':{'name':model+'-'+client,'namespace':'kagent'},'stringData':{'api-key':token}},
        {'apiVersion':'api.kagent.dev/v1alpha3','kind':'ModelConfig','metadata':{'name':model+'-'+client,'namespace':'kagent'},'spec':{'provider':'OpenAI','model':'kimi-for-coding','stream':False,'apiKeySecret':model+'-'+client,'apiKeySecretKey':'api-key','openAI':{'baseUrl':'http://'+model+'.kagent.svc:4795/v1','apiFormat':'chatCompletions','maxTokens':2048,'reasoningEffort':'low'}}}])
    resources+=docs
model_tokens['config.json']=json.dumps({'model':'kimi-for-coding','max_unique_requests':8,'clients':clients})
bridge_token=secrets.token_urlsafe(32)
control_token=k('exec','-n','durable-fixture','deploy/fixture','--','cat','/data/controller.token')
prompt=Path('paired-preflight/shared-input.txt').read_text().replace('{{OP_ID}}',op).replace('{{DECISION_ID}}',decision)
config={'run_id':run,'device_uid':str(uuid.uuid4()),'title':'Proactive guest checkout incident','controller':'kagent-controller.kagent.svc:8083',
    'data':'/data','agents':roles,'fixture':'http://fixture.durable-fixture.svc:4790','trial_id':trial,'fixture_task_id':fixture_task,
    'controller_token_file':'/config/controller.token','max_jev_requests':48,'prompt':prompt,
    'review_prompt':'Read the incident and get_operation for '+op+'. Verify the proposal hash and revision with zero effects. Return a read-only verdict. Do not change anything.'}
secret={'runtime.json':json.dumps(config),'controller.token':control_token,'bridge.token':bridge_token,'typesafe.key':options.key_file.read_text().strip()}
resources.extend([
    {'apiVersion':'v1','kind':'Secret','metadata':{'name':app+'-config','namespace':'kagent'},'immutable':True,'stringData':secret},
    {'apiVersion':'v1','kind':'Secret','metadata':{'name':model+'-config','namespace':'kagent'},'immutable':True,'stringData':model_tokens}])
for component,port,command in [(app,8080,['python','/bridge/bridge.py']),(model,4795,['python','/app/model.py','--config','/config/config.json','--state','/data'])]:
    labels={'app':component,'proactive-poc':run}
    resources.extend([
        {'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':component+'-data','namespace':'kagent'},'spec':{'accessModes':['ReadWriteOnce'],'resources':{'requests':{'storage':'512Mi'}}}},
        {'apiVersion':'v1','kind':'Service','metadata':{'name':component,'namespace':'kagent'},'spec':{'selector':labels,'ports':[{'port':port,'targetPort':port}]}}])
    image=options.image if component==app else 'durable-agent-showcase:20261014-3'
    container={'name':'bridge' if component==app else 'model','image':image,'imagePullPolicy':'Never','command':command,
        'ports':[{'containerPort':port}], 'readinessProbe':{'httpGet':{'path':'/healthz','port':port},'initialDelaySeconds':2},
        'resources':{'requests':{'cpu':'30m','memory':'64Mi'},'limits':{'cpu':'500m','memory':'256Mi'}},
        'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}},
        'volumeMounts':[{'name':'config','mountPath':'/config','readOnly':True},{'name':'data','mountPath':'/data'}]}
    pod={'automountServiceAccountToken':False,'securityContext':{'runAsUser':65532,'runAsGroup':65532,'fsGroup':65532},
        'containers':[container], 'volumes':[{'name':'config','secret':{'secretName':component+'-config'}},{'name':'data','persistentVolumeClaim':{'claimName':component+'-data'}}]}
    if component==app:
        mounts=[{'name':'data','mountPath':'/data'},{'name':'data','mountPath':'/demo/.data','subPath':'logs'},{'name':'data','mountPath':'/demo/workspace','subPath':'workspace'}]
        pod['initContainers']=[{'name':'seed','image':image,'imagePullPolicy':'Never', 'workingDir':'/demo',
            'command':['sh','-c','mkdir -p /data/logs /data/workspace; if [ ! -d /demo/workspace/checkout-api/.git ]; then node scripts/reset.ts; fi'],
            'env':[{'name':'NODE_NO_WARNINGS','value':'1'}], 'volumeMounts':mounts,
            'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}}}]
        pod['containers'].append({'name':'synthetic-checkout-logs','image':image,'imagePullPolicy':'Never','workingDir':'/demo',
            'command':['node','apps/proactive-dpi-logs/src/main.ts','--rate','0.3','--bug-at','15','--quiet'],
            'env':[{'name':'NODE_NO_WARNINGS','value':'1'}], 'resources':{'requests':{'cpu':'20m','memory':'48Mi'},'limits':{'cpu':'300m','memory':'192Mi'}},
            'volumeMounts':mounts,'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}}})
    resources.append({'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':component,'namespace':'kagent'},
        'spec':{'replicas':1,'strategy':{'type':'Recreate'},'selector':{'matchLabels':labels},'template':{'metadata':{'labels':labels},'spec':pod}}})
path=options.state/'resources.json'
path.write_text('\n---\n'.join(json.dumps(v) for v in resources))
k('create','--dry-run=server','-f',str(path))
k('create','-f',str(path))
binding={'run_id':run,'app':app,'model':model,'agents':roles,'trial_id':trial,'image':options.image,
    'max_jev_requests':48,'native_model_mode':'scripted','device_uid':config['device_uid']}
(options.state/'binding.json').write_text(json.dumps(binding,indent=2)+'\n')
(options.state/'bridge.token').write_text(bridge_token+'\n')
for component in (app,model):
    k('rollout','status','-n','kagent','deploy/'+component,'--timeout=120s')
print(json.dumps(binding))
