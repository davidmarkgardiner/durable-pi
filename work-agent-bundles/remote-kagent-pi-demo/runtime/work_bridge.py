"""Pi device HTTP adapter. Agents and MCP calls remain on the remote Kubernetes cluster."""
import hmac
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError

from gitops import GitOps
from rpc import RPC
from wire import ROLES


def initialize(config, rpc):
    path = Path(config['data'])/'native-sessions.json'
    identity = {k: config[k] for k in ('workspace_id', 'namespace', 'agents')}
    if path.exists():
        saved = json.loads(path.read_text())
        if saved['identity'] != identity:
            raise ValueError('State belongs to different native agents; preserve it')
    else:
        saved = {'identity': identity, 'contexts': {}, 'request_ids': {role: str(uuid.uuid5(uuid.NAMESPACE_URL,
            config['namespace']+'/'+config['agents'][role]+'/'+config['workspace_id']+'/'+role+'/create-session')) for role in ROLES}}
        path.write_text(json.dumps(saved))
    for role in ROLES:
        if role not in saved['contexts']:
            result = rpc.call('kagent.api.v1alpha1.SessionService', 'CreateSession', {
                'agent': {'namespace': config['namespace'], 'name': config['agents'][role]},
                'requestId': saved['request_ids'][role], 'name': 'Synthetic decision demo - '+role})
            saved['contexts'][role] = result['session']['id']
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(saved))
            temporary.replace(path)
        rpc.call('kagent.api.v1alpha1.SessionService', 'ResumeSession', {'sessionId': saved['contexts'][role]})
    return {**config, 'contexts': saved['contexts']}


class Engine:
    def __init__(self, config):
        self.config = config
        rpc = RPC(config['controller'])
        self.rpc = rpc
        self.version = rpc.call('kagent.api.v1alpha1.SystemService', 'GetVersion', {})
        if not self.version['kagentVersion'].lstrip('v').startswith('1.'):
            raise ValueError('Native 1.x controller APIs required. Do not silently upgrade or replace existing agents')
        self.config = initialize(config, rpc)
        self.workflow = GitOps(self.config, rpc)
        self.token = Path('/gitops-config/bridge.token').read_text().strip()

    def loop(self):
        while True:
            try:
                self.workflow.tick()
            except Exception as error:
                self.workflow.connection_error = type(error).__name__+': '+str(error)[:150]
            time.sleep(2)

    def device(self):
        return {'uid': self.config['device_uid'], 'name': 'work-kagent', 'hostname': self.config['cluster_label'],
            'platform': 'linux', 'apiVersion': 1, 'durableVersion': self.version['kagentVersion'],
            'startedAt': self.config['created_at'], 'startDirs': [], 'models': [{'id': self.config['model_id'],
                'provider': 'kagent', 'name': 'Configured work model', 'tier': 'live', 'icon': 'server', 'contextWindow': 0,
                'reasoning': True, 'cost': {'input': 0, 'output': 0}}], 'defaultModel': self.config['model_id'],
            'storage': {'dataDir': 'Native TaskStore + observer PVC', 'catalogPath': 'kagent', 'appStatePath': '/data'},
            'capabilities': ['events', 'docs', 'logs', 'agent-capabilities'], 'jobs': [],
            'clientControls': {'createSessions': False, 'createAgents': False, 'messages': False, 'configure': False}}

    def capabilities(self, role, fallback_tools):
        path = Path(self.config['data'])/'capabilities.json'
        if path.exists():
            data = json.loads(path.read_text())
            if data.get('workspace_id') != self.config['workspace_id']:
                raise ValueError('Capability inventory belongs to a different workspace')
            return data['roles'][role]
        return {'tools': fallback_tools, 'capabilityInventory': self.config['capabilities'][role]}

    def shared(self):
        return {'gitops': {**self.workflow.observed, 'workspaceId': self.config['workspace_id'], 'workflow': self.workflow.workflow(),
            'connectionError': self.workflow.connection_error, 'classifier': {'mode': 'synthetic',
                'provider': 'Scripted HTTP-status rule', 'model': 'synthetic-http-status-rule/v1'}}}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        return hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer '+self.server.engine.token)

    def role(self, parts):
        return next((r for r,n in ROLES.items() if str(n) == parts[4]), None)

    def frames(self, parts):
        e = self.server.engine
        w = e.workflow
        if len(parts) == 2:
            return [{'type': 'tree', 'tree': {'uid': e.config['device_uid'], 'name': 'work-kagent',
                'sessions': [w.session()], 'at': int(time.time()*1000)}},
                {'type': 'doc', 'kind': 'app.shared-state', 'value': e.shared(), 'revision': int(time.time()*1000)}]
        if len(parts) == 4:
            return [{'type': 'session', 'agents': w.session()['agents'], 'tasks': w.tasks(), 'usage': {'models': {}, 'tools': {}}}]
        role = self.role(parts)
        if not role:
            raise ValueError('Unknown native role')
        return [{'type': 'snapshot', 'snapshot': w.snapshot(role), 'inbox': []}, {'type': 'doc', 'kind': 'demo.job-runs',
            'value': self.jobs(role)}]

    def jobs(self, role):
        w = self.server.engine.workflow
        if role != 'investigator': return {'counts': {}, 'items': {}}
        value = w.jobs()
        for run in value['items'].values():
            run['canStartIncident'] = not w.observed.get('regression_commit') and not w.observed.get('starting') and not w.rows()
        return value

    def stream(self, parts):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(('data: '+json.dumps({'type': 'hello', 'apiVersion': 1, 'serverTime': int(time.time()*1000),
            'scope': {'kind': 'device' if len(parts) == 2 else 'session' if len(parts) == 4 else 'agent'}})+'\n\n').encode())
        try:
            while True:
                for frame in self.frames(parts):
                    self.wfile.write(('data: '+json.dumps(frame)+'\n\n').encode())
                self.wfile.flush()
                time.sleep(2)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if self.path == '/healthz': return self.reply(200, {'ok': True})
        if not self.authorized(): return self.reply(401, {'error': {'code': 'unauthorized', 'message': 'Bridge token required'}})
        e, w = self.server.engine, self.server.engine.workflow
        parts = urlparse(self.path).path.strip('/').split('/')
        if len(parts) >= 3 and parts[1] == 'sessions' and parts[2] != w.config['workspace_id']:
            return self.reply(404, {'error': {'code': 'not_found', 'message': 'Unknown workspace'}})
        if parts[-1] == 'events': return self.stream(parts)
        if parts == ['v1', 'demo-proof']:
            tasks = []
            for row in w.rows():
                if row['task_id']:
                    task = w.call(row['role'], 'GetTask', {'id': row['task_id'], 'historyLength': 100})
                    tasks.append({'role': row['role'], 'request_id': row['request_id'], 'message_id': row['message_id'],
                        'instruction': row['content'], 'task': task.get('task', task)})
            return self.reply(200, {'version': e.version, 'workflow': w.workflow(), 'observed': w.backend(),
                'contexts': w.config['contexts'], 'tasks': tasks})
        if parts == ['v1', 'device']: return self.reply(200, e.device())
        if parts == ['v1', 'tree']: return self.reply(200, self.frames(['v1', 'events'])[0]['tree'])
        if parts == ['v1', 'sessions']: return self.reply(200, [w.session()])
        if parts == ['v1', 'docs', 'app.shared-state']: return self.reply(200, {'kind': 'app.shared-state', 'value': e.shared(), 'revision': int(time.time()*1000)})
        if len(parts) == 3: return self.reply(200, w.session())
        if len(parts) == 4 and parts[3] == 'agents': return self.reply(200, w.session()['agents'])
        if len(parts) == 4 and parts[3] == 'tasks': return self.reply(200, w.tasks())
        if len(parts) >= 5 and parts[3] == 'agents':
            role = self.role(parts)
            if not role: return self.reply(404, {'error': {'code': 'not_found', 'message': 'Unknown role'}})
            config = {'model': {'provider': 'kagent', 'modelId': e.config['model_id']}, 'thinkingLevel': 'low',
                'cwd': 'Remote Kubernetes native actor', 'readOnly': role == 'reviewer'}
            if len(parts) == 5:
                tools = [{'name': n, 'description': d, 'replay': 'unsafe' if n in ('create_rollback_mr', 'merge_mr') else 'safe',
                    'writes': n in ('create_rollback_mr', 'merge_mr'), 'offered': True, 'requireApproval': n == 'merge_mr',
                    'server': e.config['agents'][role]+'-mcp'} for n,d in e.config['tool_descriptions'].items()
                    if role == 'investigator' or n not in ('create_rollback_mr', 'merge_mr')]
                return self.reply(200, {**w.summary(role), 'sessionId': w.config['workspace_id'], 'config': config,
                    **e.capabilities(role, tools), 'extensions': [], 'interaction': w.interaction()})
            if parts[5:] == ['config']: return self.reply(200, config)
            if parts[5:] == ['entries']: return self.reply(200, {'items': w.snapshot(role)['entries']})
            if parts[5:] == ['docs', 'demo.job-runs']: return self.reply(200, {'kind': 'demo.job-runs', 'value': self.jobs(role)})
            if parts[5:] == ['extensions']: return self.reply(200, {'extensions': [], 'builtIn': ['Native kagent MCP and HITL']})
        return self.reply(404, {'error': {'code': 'not_found', 'message': 'Unsupported route'}})

    def do_POST(self):
        if not self.authorized(): return self.reply(401, {'error': {'code': 'unauthorized', 'message': 'Bridge token required'}})
        parts = urlparse(self.path).path.strip('/').split('/')
        w = self.server.engine.workflow
        try:
            if len(parts) != 9 or parts[1] != 'sessions' or parts[2] != w.config['workspace_id'] or parts[3] != 'agents' or self.role(parts) != 'investigator' or parts[5:7] != ['demo','jobs']:
                raise ValueError('Only the scoped native workflow actions are supported')
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 2048: raise ValueError('Invalid action body length')
            body = json.loads(self.rfile.read(length))
            if parts[8] == 'approval': return self.reply(200, w.decide(parts[7], body))
            if parts[8] == 'start' and parts[7] == str(w.job_id()) and body == {} and not w.rows():
                w.backend({'action': 'start_demo'})
                return self.reply(200, {'ok': True})
            raise ValueError('The start action is available only before this single demonstration run')
        except HTTPError as error:
            return self.reply(409, {'error': {'code': 'conflict', 'message': 'Workflow backend rejected the action with HTTP '+str(error.code)+'. Check its persisted state before retrying.'}})
        except URLError:
            return self.reply(503, {'error': {'code': 'unavailable', 'message': 'Workflow backend is unreachable. Reconcile its state before retrying.'}})
        except (ValueError, KeyError, TypeError) as error:
            return self.reply(409, {'error': {'code': 'conflict', 'message': str(error)}})


if __name__ == '__main__':
    config = json.loads(Path('/gitops-config/runtime.json').read_text())
    Path(config['data']).mkdir(parents=True, exist_ok=True)
    engine = Engine(config)
    threading.Thread(target=engine.loop, daemon=True).start()
    server = ThreadingHTTPServer(('0.0.0.0', 8080), Handler)
    server.engine = engine
    server.serve_forever()
