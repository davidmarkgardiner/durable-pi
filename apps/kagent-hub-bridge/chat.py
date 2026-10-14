"""Durable admission and native TaskStore observation for the bounded live chat workspace."""
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

from wire import ROLES, USAGE, entries, number, timestamp

TERMINAL = {'TASK_STATE_COMPLETED': 'completed', 'TASK_STATE_FAILED': 'failed',
            'TASK_STATE_CANCELED': 'cancelled', 'TASK_STATE_REJECTED': 'failed'}


class Conflict(ValueError):
    pass


class NativeChat:
    def __init__(self, config, rpc):
        self.config, self.rpc = config, rpc
        self.lock = threading.RLock()
        self.db = sqlite3.connect(Path(config['data'])/config.get('database', 'chat.sqlite'), check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS identity(id INTEGER PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, role TEXT, request_id TEXT,
            message_id TEXT, content TEXT, at INTEGER, status TEXT, task_id TEXT, task TEXT, error TEXT,
            UNIQUE(role,request_id));''')
        identity = json.dumps({k: config[k] for k in ('workspace_id', 'agents', 'contexts')}, sort_keys=True)
        self.db.execute('INSERT OR IGNORE INTO identity VALUES(1,?)', (identity,))
        if self.db.execute('SELECT value FROM identity WHERE id=1').fetchone()[0] != identity:
            raise Conflict('Chat database belongs to different native sessions')
        self.db.commit()
        self.db.row_factory = sqlite3.Row
        self.budget = None
        self.budget_at = 0
        self.connection_error = None

    def rows(self, role=None):
        with self.lock:
            rows = self.db.execute('SELECT * FROM messages'+(' WHERE role=?' if role else '')+' ORDER BY id',
                (role,) if role else ()).fetchall()
            return [{**dict(r), 'task': json.loads(r['task'] or '{}')} for r in rows]

    def update(self, identity, **patch):
        with self.lock:
            if 'task' in patch:
                patch['task'] = json.dumps(patch['task'])
            self.db.execute('UPDATE messages SET '+','.join(k+'=?' for k in patch)+' WHERE id=?', (*patch.values(), identity))
            self.db.commit()

    def admit(self, role, body):
        if not isinstance(body, dict) or set(body)-{'content', 'requestId', 'whenBusy', 'waitMs'}:
            raise Conflict('Invalid native message body')
        content, request = body.get('content'), body.get('requestId')
        if not isinstance(content, str) or not content.strip() or len(content) > 2000:
            raise Conflict('Message must contain 1 to 2,000 characters')
        if not isinstance(request, str) or not 1 <= len(request) <= 128:
            raise Conflict('A stable requestId is required')
        if body.get('whenBusy', 'reject') != 'reject':
            raise Conflict('Native chat currently accepts one task at a time; use reject-if-busy')
        with self.lock:
            previous = next((r for r in self.rows(role) if r['request_id'] == request), None)
            if previous:
                if previous['content'] != content:
                    raise Conflict('requestId was already used for different content')
                # An explicit native refusal admitted no input. Only an exact client retry requeues it.
                if previous['status'] == 'refused':
                    self.update(previous['id'], status='queued', error=None)
                return {'submissionId': previous['id'], 'status': 'pending'}
            if any(r['status'] not in ('completed', 'failed', 'cancelled', 'refused') for r in self.rows(role)):
                raise Conflict('This native agent has an active or unresolved task. Wait for its result before sending another message')
            if self.budget and (self.budget['halted'] or self.budget['calls'] >= self.budget['max_calls']):
                raise Conflict('The bounded live-model allowance is exhausted or halted')
            message_id = str(uuid.uuid5(uuid.NAMESPACE_URL, self.config['contexts'][role]+'/'+request))
            row = self.db.execute('INSERT INTO messages(role,request_id,message_id,content,at,status) VALUES(?,?,?,?,?,?)',
                (role, request, message_id, content, int(time.time()*1000), 'queued'))
            self.db.commit()
            return {'submissionId': row.lastrowid, 'status': 'pending'}

    def call(self, role, method, body):
        return self.rpc.call('lf.a2a.v1.A2AService', method, {'tenant': self.config.get('namespace', 'kagent')+'/'+self.config['agents'][role], **body})

    def tick(self):
        for row in self.rows():
            role = row['role']
            try:
                if row['status'] == 'queued':
                    self.update(row['id'], status='sending')
                    try:
                        reply = self.call(role, 'SendMessage', {'message': {'messageId': row['message_id'],
                            'contextId': self.config['contexts'][role], 'role': 'ROLE_USER', 'parts': [{'text': row['content']}]},
                            'configuration': {'returnImmediately': True, 'historyLength': 100}})
                        task = reply.get('task')
                        if not task:
                            raise Conflict('Native admission returned no task; reconcile before retry')
                        self.update(row['id'], task_id=task['id'], task=task, status='working', error=None)
                    except Exception as error:
                        details = error.details() if hasattr(error, 'details') else str(error)
                        refused = details == 'input was not accepted; retry after the session becomes available'
                        self.update(row['id'], status='refused' if refused else 'uncertain', error=details[:250])
                elif row['status'] in ('sending', 'uncertain') and not row['task_id']:
                    tasks = self.call(role, 'ListTasks', {'contextId': self.config['contexts'][role], 'pageSize': 20, 'historyLength': 100}).get('tasks', [])
                    matched = [t for t in tasks if any(m.get('messageId') == row['message_id'] for m in t.get('history', []))]
                    if len(matched) == 1:
                        self.update(row['id'], task_id=matched[0]['id'], task=matched[0], status='working', error=None)
                    elif len(matched) > 1:
                        self.update(row['id'], error='Ambiguous native admission. No automatic retry')
                elif row['task_id'] and row['status'] not in ('completed', 'failed', 'cancelled'):
                    reply = self.call(role, 'GetTask', {'id': row['task_id'], 'historyLength': 100})
                    task = reply.get('task', reply)
                    state = task['status']['state']
                    self.update(row['id'], task=task, status=TERMINAL.get(state, 'waiting' if state == 'TASK_STATE_INPUT_REQUIRED' else 'working'), error=None)
                self.connection_error = None
            except Exception as error:
                self.connection_error = type(error).__name__+': '+str(error)[:150]
        # The model guard holds its budget lock during a provider call. Read status after tasks settle.
        if self.config.get('model_status_url') and not any(r['status'] in ('queued', 'sending', 'working') for r in self.rows()) and time.time()-self.budget_at > 5:
            try:
                token = Path(self.config['model_status_token_file']).read_text().strip()
                with urlopen(Request(self.config['model_status_url'], headers={'Authorization': 'Bearer '+token}), timeout=2) as response:
                    self.budget = json.load(response)
                self.budget_at = time.time()
            except OSError:
                pass

    def summary(self, role):
        active = [r for r in self.rows(role) if r['status'] not in ('completed', 'failed', 'cancelled', 'refused')]
        return {'id': ROLES[role], 'name': 'Live Kimi specialist' if role == 'investigator' else 'Live Kimi reviewer',
            'named': True, 'kind': 'root', 'busy': bool(active), 'background': 0}

    def session(self):
        return {'id': self.config['workspace_id'], 'name': 'Live Kimi chat', 'cwd': 'Kubernetes native sessions',
            'model': 'kimi-for-coding', 'createdAt': self.config['created_at'], 'dbPath': 'Native kagent TaskStore + chat admission PVC',
            'busy': any(self.summary(r)['busy'] for r in ROLES), 'agents': [self.summary(r) for r in ROLES]}

    def tasks(self):
        return [{'id': number(r['task_id'] or r['message_id']), 'kind': 'kagent.chat.task', 'conversationId': ROLES[r['role']],
            'background': False, 'state': {'status': r['status']}, 'conversations': [], 'label': r['task_id'] or 'Native admission pending'}
            for r in self.rows() if r['status'] not in ('completed', 'failed', 'cancelled', 'refused')]

    def snapshot(self, role):
        rows = self.rows(role)
        result = [{'id': 1, 'conversationId': ROLES[role], 'kind': 'kagent.binding', 'data': {
            'text': 'Live Kimi native kagent chat. Agent '+self.config['agents'][role]+'; context '+self.config['contexts'][role]+'. Read-only synthetic incident tools.',
            'agent': self.config['agents'][role], 'contextId': self.config['contexts'][role]}}]
        for row in rows:
            result.append({'conversationId': ROLES[role], 'kind': 'pi.user', 'model': [{'role': 'user', 'content': row['content']}]})
            state = {'model_id': 'kimi-for-coding', 'model_label': 'Live Kimi model.', 'roles': {role: {
                'agent': self.config['agents'][role], 'context': self.config['contexts'][role], 'task_id': row['task_id'], 'task': row['task']}}}
            result.extend(e for e in entries(state, role) if e['kind'] in ('pi.assistant', 'pi.tool-result'))
            if row['error'] or row['status'] in ('failed', 'cancelled', 'waiting'):
                native_text = ' '.join(p.get('text', '') for p in row['task'].get('status', {}).get('message', {}).get('parts', []))
                result.append({'conversationId': ROLES[role], 'kind': 'kagent.binding', 'data': {
                    'text': 'Native task '+row['status']+': '+(row['error'] or native_text or row['task_id'])}})
        for index, item in enumerate(result):
            item['id'] = index+1
        value = {'type': 'snapshot', 'entries': result, 'tools': [], 'compactions': [], 'inbox': [],
            'agent': {'model': {'provider': 'kagent', 'modelId': 'kimi-for-coding'}, 'thinkingLevel': 'low'},
            'usage': {'models': {}, 'tools': {}}}
        if self.summary(role)['busy']:
            value['run'] = {'inputs': []}
        return value

    def interaction(self):
        return {'kind': 'native-chat', 'budget': self.budget, 'maxCalls': self.config['max_calls'],
            'tokenBudget': self.config['token_budget'], 'connectionError': self.connection_error}
