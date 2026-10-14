"""Bounded proactive demo and Pi display adapter for native kagent sessions."""
import hashlib
import hmac
import json
import os
import sqlite3
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

sys.path.insert(0, '/app')
import server as native
from wire import ROLES, approval, jobs, number, snapshot, summary, timestamp, validate_decision, fixture_decision
from chat import NativeChat, Conflict
from gitops import GitOps

QUESTIONS = {
    'verdict': {'type': 'choice', 'instructions': 'You watch the production log stream of Lumen Market, an online store. Decide what this one log entry means for the on-call engineer.', 'criteria': {
        'normal': 'Routine and expected. Successful requests, debug and cache output, deploy and autoscaling notices, and expected client outcomes: 404 unknown product, 401 expired session, 402 card declined, 429 rate limit on a scraper bot.',
        'suspicious': 'Worth a look but not clearly broken. Slow queries, upstream timeouts that recovered on retry, unusual warnings.',
        'incident': 'Our code is failing real customers. Unhandled exceptions, stack traces, 5xx responses on core flows such as checkout, crashes, data loss.'}},
    'impact': {'type': 'score', 'instructions': 'How much does this entry show customers being hurt?',
        'criteria': ['No customer impact', 'Minor or cosmetic', 'Degraded but working', 'A customer is blocked from buying or signing in', 'Many customers blocked and revenue is being lost']}}


def validate_response(value):
    answers = value['answers']
    choice, score = answers['verdict'], answers['impact']
    if choice['type'] != 'choice' or choice['choice'] not in QUESTIONS['verdict']['criteria'] or score['type'] != 'score':
        raise ValueError('Invalid Jev answer type or decision')
    probabilities = choice['probabilities']
    if set(probabilities) != set(QUESTIONS['verdict']['criteria']):
        raise ValueError('Incomplete Jev choice distribution')
    if any(type(p) not in (int, float) or not 0 <= p <= 1 for p in probabilities.values()) or abs(sum(probabilities.values())-1) > .02:
        raise ValueError('Invalid Jev probabilities')
    if type(score['score']) not in (int, float) or not 0 <= score['score'] <= 4:
        raise ValueError('Invalid Jev impact score')
    return choice, score


class Classifier:
    def __init__(self, engine):
        self.engine = engine
        self.path = Path(engine.config['data'])/'verdicts.sqlite'
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('CREATE TABLE IF NOT EXISTS calls(id INTEGER PRIMARY KEY, log_id INTEGER, started REAL, result TEXT, error TEXT); CREATE TABLE IF NOT EXISTS verdicts(log_id INTEGER PRIMARY KEY, fingerprint TEXT, decision TEXT, probability REAL, body TEXT);')
        self.db.commit()
        self.lock = threading.RLock()
        self.key = Path('/config/typesafe.key').read_text().strip()
        if not self.key:
            raise ValueError('Missing TypeSafe key')
        self.error = None

    def rows(self):
        path = Path(self.engine.config['data'])/'logs/logs.sqlite'
        if not path.exists():
            return []
        with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            with self.lock:
                judged = [r[0] for r in self.db.execute('SELECT log_id FROM verdicts')]
            slots = ','.join('?' for _ in judged) or 'NULL'
            return [dict(r) for r in db.execute(f'SELECT * FROM logs WHERE id IN ({slots}) OR id >= (SELECT max(id)-30 FROM logs) ORDER BY id', judged)]

    def stats(self):
        with self.lock:
            calls = self.db.execute('SELECT count(*) FROM calls').fetchone()[0]
            judged = self.db.execute('SELECT count(*) FROM verdicts').fetchone()[0]
        triggered = bool(self.engine.store.get().get('proactive_trigger'))
        return {'provider': 'TypeSafe', 'model': 'jev-latest', 'requests': calls,
            'maxRequests': self.engine.config.get('max_jev_requests', 48), 'judged': judged,
            'status': 'paused after automatic dispatch' if triggered else 'request limit reached' if calls >= self.engine.config.get('max_jev_requests', 48) else 'watching', 'error': self.error}

    def view(self):
        rows = self.rows()
        with self.lock:
            verdicts = {r[0]: json.loads(r[1]) for r in self.db.execute('SELECT log_id,body FROM verdicts')}
        return [{'id': r['id'], 'at': r['ts'], 'service': r['service'], 'severity': r['severity'],
            'message': r['message'], 'status': r['status'], 'revision': r['revision'],
            'raw': json.loads(r['entry']), **verdicts.get(r['id'], {'classification': 'unjudged'})} for r in rows]

    def judge(self, row):
        payload = json.loads(row['entry']).get('jsonPayload', {'message': row['message']})
        state = {'severity': row['severity'], 'service': row['service'], 'revision': row['revision'],
            'request': f"{row['method']} {row['route']} -> {row['status']}" if row['method'] else None, **payload}
        started = time.time()
        with self.lock:
            identity = self.db.execute('INSERT INTO calls(log_id,started) VALUES(?,?)', (row['id'], started)).lastrowid
            self.db.commit()
        request = Request('https://api.typesafe.ai/v1/systemone', data=json.dumps({'model': 'jev-latest', 'state': state, 'questions': QUESTIONS}).encode(),
            headers={'Authorization': 'Bearer '+self.key, 'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=20) as response:
                body = json.load(response)
            choice, score = validate_response(body)
            fingerprint = '|'.join(str(v) for v in [row['service'], row['method'], row['route'], row['error_type'] or row['status'] or row['message'][:60]])
            verdict = {'classification': 'judged', 'decision': choice['choice'],
                'probability': choice['probabilities'][choice['choice']], 'probabilities': choice['probabilities'],
                'confidence': choice['confidence'], 'impact': score['score'], 'model': body['model'],
                'latencyMs': round((time.time()-started)*1000), 'usage': body.get('usage', {})}
            with self.lock:
                self.db.execute('UPDATE calls SET result=? WHERE id=?', (json.dumps(body), identity))
                self.db.execute('INSERT INTO verdicts VALUES(?,?,?,?,?)', (row['id'], fingerprint, verdict['decision'], verdict['probability'], json.dumps(verdict)))
                self.db.commit()
                hits = [r[0] for r in self.db.execute("SELECT log_id FROM verdicts WHERE fingerprint=? AND decision='incident' AND probability>=0.6", (fingerprint,))]
            self.error = None
            log_times = {r['id']: timestamp(r['ts']) for r in self.rows()}
            hits = [identity for identity in hits if log_times.get(identity, 0) >= int(time.time()*1000)-120000]
            if len(hits) >= 3 and not self.engine.store.get().get('proactive_trigger'):
                trigger = {'fingerprint': fingerprint, 'logIds': hits, 'threshold': 3,
                    'decision': 'incident', 'at': native.now(), 'classifier': body['model']}
                self.engine.store.change(lambda value: value.update(proactive_trigger=trigger))
                self.engine.store.event('jev_threshold_reached', trigger)
        except Exception as error:
            self.error = type(error).__name__ + ': ' + str(error)[:150]
            with self.lock:
                self.db.execute('UPDATE calls SET error=? WHERE id=?', (self.error, identity))
                self.db.commit()
            # No synthetic decision replaces a missing classifier result.

    def loop(self):
        while True:
            try:
                if not self.engine.store.get().get('proactive_trigger') and self.stats()['requests'] < self.stats()['maxRequests']:
                    with self.lock:
                        attempted = {r[0] for r in self.db.execute('SELECT log_id FROM calls')}
                    row = next((r for r in self.rows() if r['id'] not in attempted), None)
                    if row:
                        self.judge(row)
            except Exception as error:
                self.error = type(error).__name__+': '+str(error)[:150]
            time.sleep(.3)


class Engine(native.Engine):
    def __init__(self, config):
        super().__init__(config)
        self.classifier = Classifier(self)
        self.token = Path('/config/bridge.token').read_text().strip()
        self.started = int(time.time()*1000)
        self.uid = config['device_uid']
        chat_config = Path('/chat-config/runtime.json')
        self.chat = NativeChat(json.loads(chat_config.read_text()), self.rpc) if chat_config.exists() else None
        gitops_config = Path('/gitops-config/runtime.json')
        self.gitops = GitOps(json.loads(gitops_config.read_text()), self.rpc) if gitops_config.exists() else None

    def loop(self):
        while True:
            try:
                state = self.store.get()
                if state['phase'] == 'ready' and state.get('proactive_trigger') and not state.get('command'):
                    self.config['prompt'] = self.config['prompt'].split('\nProactive trigger:')[0] + '\nProactive trigger: ' + json.dumps(state['proactive_trigger'])
                    self.action({'action': 'start'})
                self.tick()
                self.resume_saved_decision()
            except Exception as error:
                self.update(error={'type': type(error).__name__, 'message': str(error)[:250], 'at': native.now()}, connection={'status': 'error', 'observed_at': native.now()})
            if self.chat:
                try:
                    self.chat.tick()
                except Exception as error:
                    self.chat.connection_error = type(error).__name__+': '+str(error)[:150]
            if self.gitops:
                try:
                    self.gitops.tick()
                except Exception as error:
                    self.gitops.connection_error = type(error).__name__+': '+str(error)[:150]
            time.sleep(2)

    def fixture(self, body=None):
        return super().fixture(fixture_decision(body) if body is not None else None)

    def resume_saved_decision(self):
        state = self.store.get()
        saved = state.get('decision')
        if state['phase'] != 'decision_issued' or not saved or saved['delivery'] != 'not_sent':
            return
        task = state['roles']['investigator']['task']
        tools = (approval(task) or {}).get('tools', [])
        if len(tools) != 1:
            raise ValueError('Retained approval changed before delivery')
        tool = tools[0]
        expected = {'task_id': task['id'], 'approval_id': tool['id'], 'request': tool['args']['request']}
        if saved['command']['expected'] != expected:
            raise ValueError('Retained human decision no longer matches the native task')
        decision = fixture_decision(saved['fixture'])
        if decision['expires_at'] <= time.time():
            raise ValueError('Retained decision expired; it needs a new human decision')
        ledger = self.fixture()
        recorded = [e['body'] for e in ledger['events'] if e['kind'] == 'decision_recorded']
        if not recorded:
            self.fixture(decision)
            ledger = self.fixture()
            recorded = [e['body'] for e in ledger['events'] if e['kind'] == 'decision_recorded']
        if recorded != [decision]:
            raise ValueError('Independent decision differs from the retained authorization')
        self.store.change(lambda value: value['decision'].update(delivery='sending'))
        approved = saved['command']['action'] == 'approve'
        self.a2a('investigator', 'SendMessage', {'message': {'messageId': saved['message_id'], 'taskId': task['id'],
            'contextId': task['contextId'], 'role': 'ROLE_USER', 'parts': [{'text': 'Approve this exact synthetic proposal and verify read_result.' if approved else 'Reject this proposal; do not publish.'}],
            'extensions': [native.EXT], 'metadata': {native.EXT: {'type': 'tool_approval_response', 'approvals': [
                {'id': tool['id'], 'approved': approved, 'rejection_reason': '' if approved else 'Human declined the synthetic change.'}]}}},
            'configuration': {'returnImmediately': True, 'historyLength': 20}})
        self.store.change(lambda value: value['decision'].update(delivery='sent'))
        self.update(phase='verifying', error=None)

    def shared(self):
        state = self.store.get()
        return {'gitops': {**self.gitops.observed, 'workflow': self.gitops.workflow(), 'connectionError': self.gitops.connection_error} if self.gitops else None,
            'nativeChat': self.chat.interaction() if self.chat else None, 'proactive': {'classifier': self.classifier.stats(), 'logs': self.classifier.view(),
            'trigger': state.get('proactive_trigger'), 'phase': state['phase'], 'review': state.get('review'),
            'nativeActors': state.get('inventory', {}).get('actors', []), 'verification': state.get('verification'),
            'error': state.get('error'), 'connection': state.get('connection'), 'modelMode': 'Scripted native agent. Real Jev classifications and real Kubernetes actors.',
            'scope': 'Original synthetic checkout logs trigger the separate bounded native fixture. Autonomous source repair and rollout are not implemented in this bridge proof.'}}

    def device(self):
        return {'uid': self.uid, 'name': 'kagent-proxmox', 'hostname': 'Proxmox Kubernetes', 'platform': 'linux',
            'apiVersion': 1, 'durableVersion': 'kagent 1.0.0-alpha11 / Substrate 0.5.0-alpha2', 'startedAt': self.started,
            'startDirs': [], 'models': [{'id': 'scripted-native', 'provider': 'kagent', 'name': 'Scripted native kagent',
                'tier': 'demo', 'icon': 'server', 'contextWindow': 16384, 'reasoning': False, 'cost': {'input': 0, 'output': 0}},
                *([{'id': 'kimi-for-coding', 'provider': 'kagent', 'name': 'Live Kimi for Coding', 'tier': 'live', 'icon': 'kimi.png',
                    'contextWindow': 0, 'reasoning': True, 'cost': {'input': 0, 'output': 0}}] if self.chat else [])],
            'defaultModel': 'scripted-native', 'storage': {'dataDir': 'kagent PostgreSQL and Substrate snapshots',
                'catalogPath': 'kagent controller', 'appStatePath': 'POC observer PVC'},
            'capabilities': ['events', 'docs', 'logs', 'agent-capabilities'], 'jobs': [],
            'clientControls': {'createSessions': False, 'createAgents': False, 'messages': bool(self.chat), 'configure': False}}

    def sessions(self):
        return [self.session()]+([self.chat.session()] if self.chat else [])+([self.gitops.session()] if self.gitops else [])

    def workspace(self, identity):
        return next((w for w in (self.chat, self.gitops) if w and w.config['workspace_id'] == identity), None)

    def role_capabilities(self, role):
        try:
            return json.loads((Path(self.config['data'])/'capabilities.json').read_text())['roles'][role]
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            return {'tools': []}

    def session(self):
        state = self.store.get()
        return {'id': self.config['run_id'], 'name': 'Proactive checkout incident', 'cwd': 'Kubernetes native sessions',
            'model': 'scripted-native', 'createdAt': self.started, 'dbPath': 'kagent controller PostgreSQL',
            'busy': any(summary(state, role)['busy'] for role in ROLES), 'agents': [summary(state, r) for r in ROLES]}

    def tasks(self):
        state = self.store.get()
        return [{'id': number(d['task_id']), 'kind': 'kagent.native.task', 'conversationId': ROLES[r],
            'background': d.get('task', {}).get('status', {}).get('state') == 'TASK_STATE_INPUT_REQUIRED',
            'state': {'status': 'waiting' if approval(d.get('task', {})) else 'running'}, 'conversations': [],
            'label': d['task_id']} for r,d in state['roles'].items()
            if d['task_id'] and d.get('task', {}).get('status', {}).get('state') not in ('TASK_STATE_COMPLETED', 'TASK_STATE_FAILED', 'TASK_STATE_CANCELED')]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, value):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        return hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer '+self.server.engine.token)

    def role(self, parts):
        return {str(v): r for r,v in ROLES.items()}.get(parts[4], 'investigator' if parts[4] == 'main' else None)

    def frames(self, parts):
        engine = self.server.engine
        state = engine.store.get()
        if len(parts) == 2:
            return [{'type': 'tree', 'tree': {'uid': engine.uid, 'name': 'kagent-proxmox', 'sessions': engine.sessions(), 'at': int(time.time()*1000)}},
                {'type': 'doc', 'kind': 'app.shared-state', 'value': engine.shared(), 'revision': int(time.time()*1000)}]
        workspace = engine.workspace(parts[2]) if len(parts) >= 3 else None
        if workspace:
            if len(parts) == 4:
                return [{'type': 'session', 'agents': workspace.session()['agents'], 'tasks': workspace.tasks(), 'usage': {'models': {}, 'tools': {}}}]
            role = self.role(parts)
            if not role:
                raise ValueError('Unknown native chat role')
            return [{'type': 'snapshot', 'snapshot': workspace.snapshot(role), 'inbox': []},
                {'type': 'doc', 'kind': 'demo.job-runs', 'value': workspace.jobs() if workspace is engine.gitops and role == 'investigator' else {'counts': {}, 'items': {}}}]
        if len(parts) == 4:
            return [{'type': 'session', 'agents': engine.session()['agents'], 'tasks': engine.tasks(), 'usage': {'models': {}, 'tools': {}}}]
        role = self.role(parts)
        if not role:
            raise ValueError('Unknown native role')
        return [{'type': 'snapshot', 'snapshot': snapshot(state, role), 'inbox': []},
                {'type': 'doc', 'kind': 'demo.job-runs', 'value': jobs(state) if role == 'investigator' else {'counts': {}, 'items': {}}}]

    def stream(self, parts):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        try:
            hello = {'type': 'hello', 'apiVersion': 1, 'serverTime': int(time.time()*1000),
                'scope': {'kind': 'device' if len(parts) == 2 else 'session' if len(parts) == 4 else 'agent'}}
            self.wfile.write(('data: '+json.dumps(hello)+'\n\n').encode())
            previous = None
            while True:
                frames = self.frames(parts)
                encoded = json.dumps(frames, sort_keys=True)
                if encoded != previous:
                    for frame in frames:
                        self.wfile.write(('data: '+json.dumps(frame)+'\n\n').encode())
                    previous = encoded
                else:
                    self.wfile.write(b': ping\n\n')
                self.wfile.flush()
                time.sleep(2)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        path = urlparse(self.path).path
        engine = self.server.engine
        if path == '/healthz':
            return self.reply(200, {'ok': True})
        if not self.authorized():
            return self.reply(401, {'error': {'code': 'unauthorized', 'message': 'Bridge token required'}})
        parts = path.strip('/').split('/')
        if path.endswith('/events'):
            return self.stream(parts)
        if path == '/v1/device':
            return self.reply(200, engine.device())
        if path == '/v1/tree':
            return self.reply(200, self.frames(['v1','events'])[0]['tree'])
        if path == '/v1/docs/app.shared-state':
            return self.reply(200, {'kind': 'app.shared-state', 'value': engine.shared(), 'revision': int(time.time()*1000)})
        if path == '/v1/sessions':
            return self.reply(200, engine.sessions())
        if len(parts) >= 3 and parts[1] == 'sessions' and engine.workspace(parts[2]):
            return self.chat_get(parts, engine.workspace(parts[2]))
        if len(parts) >= 3 and parts[1] == 'sessions' and parts[2] != engine.config['run_id']:
            return self.reply(404, {'error': {'code': 'not_found', 'message': 'Unknown POC session'}})
        if len(parts) == 3:
            return self.reply(200, engine.session())
        if len(parts) == 4 and parts[3] == 'tasks':
            return self.reply(200, engine.tasks())
        if len(parts) == 4 and parts[3] == 'agents':
            return self.reply(200, engine.session()['agents'])
        if len(parts) >= 5 and parts[3] == 'agents':
            role = self.role(parts)
            if not role:
                return self.reply(404, {'error': {'code': 'not_found', 'message': 'Unknown native role'}})
            state = engine.store.get()
            capabilities = engine.role_capabilities(role)
            config = {'model': {'provider': 'kagent', 'modelId': 'scripted-native'}, 'thinkingLevel': 'off',
                'instructions': 'Native kagent '+state['roles'][role]['agent']+'; context '+str(state['roles'][role]['context'])+'. Scripted POC.',
                'readOnly': role == 'reviewer', 'cwd': 'Kubernetes native actor'}
            if len(parts) == 5:
                return self.reply(200, {**summary(state,role), 'sessionId': engine.config['run_id'], 'config': config,
                    **capabilities, 'extensions': [], 'interaction': {'kind': 'approval-only',
                        'reason': 'This retained incident uses its exact native approval card. Open Live Kimi chat to give new instructions.'}})
            if parts[5] == 'config':
                return self.reply(200, config)
            if parts[5] == 'extensions':
                return self.reply(200, {'extensions': [], 'builtIn': ['Native kagent MCP and HITL']})
            if parts[5] == 'entries':
                return self.reply(200, {'items': snapshot(state,role)['entries']})
            if parts[5] == 'docs' and parts[6] == 'demo.job-runs':
                return self.reply(200, {'kind': 'demo.job-runs', 'value': jobs(state) if role == 'investigator' else {'counts': {}, 'items': {}}})
        return self.reply(404, {'error': {'code': 'not_found', 'message': 'Route not supported by the POC bridge'}})

    def chat_get(self, parts, chat):
        engine = self.server.engine
        gitops = chat is engine.gitops
        if len(parts) == 3:
            return self.reply(200, chat.session())
        if len(parts) == 4 and parts[3] == 'agents':
            return self.reply(200, chat.session()['agents'])
        if len(parts) == 4 and parts[3] == 'tasks':
            return self.reply(200, chat.tasks())
        if len(parts) >= 5 and parts[3] == 'agents':
            role = self.role(parts)
            if not role:
                return self.reply(404, {'error': {'code': 'not_found', 'message': 'Unknown chat agent'}})
            config = {'model': {'provider': 'kagent', 'modelId': 'kimi-for-coding'}, 'thinkingLevel': 'low',
                'readOnly': not gitops or role == 'reviewer', 'cwd': 'Kubernetes native actor'}
            if len(parts) == 5:
                return self.reply(200, {**chat.summary(role), 'sessionId': chat.config['workspace_id'], 'config': config,
                    **engine.role_capabilities(('gitops-' if gitops else 'chat-')+role), 'extensions': [], 'interaction': chat.interaction()})
            if parts[5] == 'entries':
                return self.reply(200, {'items': chat.snapshot(role)['entries']})
            if parts[5] == 'config':
                return self.reply(200, config)
            if parts[5] == 'extensions':
                return self.reply(200, {'extensions': [], 'builtIn': ['Native kagent live chat']})
            if parts[5:] == ['docs', 'demo.job-runs']:
                return self.reply(200, {'kind': 'demo.job-runs', 'value': chat.jobs() if gitops and role == 'investigator' else {'counts': {}, 'items': {}}})
        return self.reply(404, {'error': {'code': 'not_found', 'message': 'Unsupported native chat route'}})

    def do_POST(self):
        if not self.authorized():
            return self.reply(401, {'error': {'code': 'unauthorized', 'message': 'Bridge token required'}})
        parts = urlparse(self.path).path.strip('/').split('/')
        engine = self.server.engine
        if len(parts) == 6 and parts[1] == 'sessions' and parts[3] == 'agents' and parts[5] == 'messages':
            try:
                if not engine.chat or parts[2] != engine.chat.config['workspace_id'] or not self.role(parts):
                    raise Conflict('New instructions belong in Live Kimi chat. The retained incident accepts only its bound approval')
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 10000:
                    raise Conflict('Invalid message body length')
                body = json.loads(self.rfile.read(length))
                return self.reply(202, engine.chat.admit(self.role(parts), body))
            except (ValueError, KeyError, TypeError) as error:
                return self.reply(409, {'error': {'code': 'conflict', 'message': str(error)}})
        if len(parts) == 9 and parts[1] == 'sessions' and parts[3] == 'agents' and parts[5:7] == ['demo','jobs'] and parts[8] == 'approval':
            try:
                if engine.gitops and parts[2] == engine.gitops.config['workspace_id']:
                    if self.role(parts) != 'investigator':
                        raise Conflict('Only the specialist owns this merge approval')
                    length = int(self.headers.get('Content-Length', 0))
                    if not 0 < length <= 2048:
                        raise Conflict('Invalid decision body')
                    return self.reply(200, engine.gitops.decide(parts[7], json.loads(self.rfile.read(length))))
                engine = self.server.engine
                state = engine.store.get()
                task = state['roles']['investigator']['task']
                if parts[2] != engine.config['run_id'] or self.role(parts) != 'investigator' or parts[7] != str(number(task['id'])):
                    raise ValueError('Approval is not bound to this native task')
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 1024:
                    raise ValueError('Invalid decision body')
                body = json.loads(self.rfile.read(length))
                expected = validate_decision(body, task)
                engine.action({'action': 'approve' if body['approved'] else 'reject',
                    'expected': expected})
                return self.reply(200, {'ok': True})
            except (ValueError, KeyError, TypeError) as error:
                return self.reply(409, {'error': {'code': 'conflict', 'message': str(error)}})
        return self.reply(409, {'error': {'code': 'conflict', 'message': 'This POC supports native approval decisions; creation and chat controls are disabled'}})


if __name__ == '__main__':
    config = json.loads(Path('/config/runtime.json').read_text())
    engine = Engine(config)
    threading.Thread(target=engine.loop, daemon=True).start()
    threading.Thread(target=engine.classifier.loop, daemon=True).start()
    server = ThreadingHTTPServer(('0.0.0.0',8080), Handler)
    server.engine = engine
    server.serve_forever()
