"""Exact-project rollback tools and an independent human decision ledger."""
import hmac
import json
import ssl
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


class Rejected(ValueError):
    pass


class Rollback:
    def __init__(self, config):
        self.config = config
        self.lock = threading.RLock()
        self.db = sqlite3.connect('/data/gitops.sqlite', check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY, value TEXT)')
        self.db.execute('INSERT OR IGNORE INTO state VALUES(1,?)', (json.dumps({'phase': 'monitoring', 'samples': [], 'classifications': [], 'calls': 0}),))
        self.db.commit()
        self.token = Path('/gitlab/gitlab.token').read_text().strip()
        self.ca = ssl.create_default_context(cafile='/var/run/secrets/kubernetes.io/serviceaccount/ca.crt')
        self.kube_token = Path('/var/run/secrets/kubernetes.io/serviceaccount/token').read_text().strip()

    def state(self):
        with self.lock:
            return json.loads(self.db.execute('SELECT value FROM state WHERE id=1').fetchone()[0])

    def save(self, **patch):
        with self.lock:
            state = self.state()
            state.update(patch)
            self.db.execute('UPDATE state SET value=? WHERE id=1', (json.dumps(state),))
            self.db.commit()
            return state

    def api(self, path, method='GET', body=None):
        req = Request(self.config['gitlab_api'].rstrip('/')+'/projects/'+str(self.config['project'])+'/'+path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization': 'Bearer '+self.token, 'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=25) as response:
                return json.load(response)
        except HTTPError as error:
            raise Rejected('GitLab '+method+' failed with HTTP '+str(error.code)) from None

    def kube(self, path, raw=False):
        with urlopen(Request('https://kubernetes.default.svc/'+path,
            headers={'Authorization': 'Bearer '+self.kube_token}), context=self.ca, timeout=10) as response:
            return response.read().decode() if raw else json.load(response)

    def probe(self):
        try:
            response = urlopen(self.config['application_url'].rstrip('/')+'/checkout', timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return {'at': time.time(), 'status': response.code, 'body': json.load(response)}

    def read_incident(self, request):
        state = self.state()
        pods = self.kube('api/v1/namespaces/'+self.config['application_namespace']+'/pods?labelSelector=app%3Dlumen-checkout')['items']
        logs = []
        for pod in pods:
            name = pod['metadata']['name']
            logs.append({'pod': name, 'text': self.kube('api/v1/namespaces/'+self.config['application_namespace']+'/pods/'+name+'/log?tailLines=3', raw=True)[-1500:]})
        trigger = state.get('trigger')
        trigger_summary = {'source': trigger['source'], 'incident_count': len(trigger['incident_samples']),
            'statuses': [c['sample']['status'] for c in trigger['incident_samples']]} if trigger else None
        return {'application': 'Lumen synthetic guest checkout', 'cluster': self.config['cluster_label'],
            'namespace': self.config['application_namespace'], 'probe': self.probe(), 'trigger': trigger_summary, 'logs': logs}

    def read_deployment(self, request):
        d = self.kube('apis/apps/v1/namespaces/'+self.config['application_namespace']+'/deployments/checkout')
        return {'name': 'checkout', 'namespace': self.config['application_namespace'], 'image': d['spec']['template']['spec']['containers'][0]['image'],
            'generation': d['metadata']['generation'], 'status': {key: d.get('status', {}).get(key) for key in ('observedGeneration', 'replicas', 'updatedReplicas', 'availableReplicas')},
            'known_healthy_image': self.config['healthy_image'], 'regression_image': self.config['regression_image']}

    def manifest(self, ref=None):
        f = self.api('repository/files/'+quote(self.config['manifest_file'], safe='')+'?ref='+quote(ref or self.config['target_branch'], safe=''))
        import base64
        return json.loads(base64.b64decode(f['content'])), f['last_commit_id']

    def read_gitops(self, request):
        d, sha = self.manifest()
        return {'project': self.config['project'], 'url': self.config['url'], 'file': self.config['manifest_file'],
            'target_branch': self.config['target_branch'], 'image': d['spec']['template']['spec']['containers'][0]['image'], 'last_commit': sha}

    def create_rollback_mr(self, request):
        if set(request) != {'reason'} or not isinstance(request['reason'], str) or not 10 <= len(request['reason']) <= 1000:
            raise Rejected('A concise evidence-based reason is required')
        with self.lock:
            state = self.state()
            if state.get('mr'):
                return self.inspect_mr(state['mr']['binding'])
            baseline, base_sha = self.manifest()
            if baseline['spec']['template']['spec']['containers'][0]['image'] != self.config['regression_image']:
                raise Rejected('Main no longer contains the configured regression')
            branch = self.config['rollback_branch']
            existing = self.api('merge_requests?state=opened&source_branch='+quote(branch, safe=''))
            if len(existing) > 1:
                raise Rejected('Ambiguous existing rollback merge requests')
            branches = self.api('repository/branches?search='+quote('^'+branch+'$', safe=''))
            if not branches:
                self.api('repository/branches', 'POST', {'branch': branch, 'ref': self.config['target_branch']})
            candidate, _ = self.manifest(branch)
            if candidate == baseline:
                candidate['spec']['template']['spec']['containers'][0]['image'] = self.config['healthy_image']
                self.api('repository/commits', 'POST', {'branch': branch, 'commit_message': 'Restore guest checkout: roll back to v1',
                    'actions': [{'action': 'update', 'file_path': self.config['manifest_file'], 'content': json.dumps(candidate, indent=2)+'\n'}]})
            mr = existing[0] if existing else self.api('merge_requests', 'POST', {'source_branch': branch, 'target_branch': self.config['target_branch'],
                'title': 'Restore guest checkout: roll back image v2 to v1', 'description': request['reason']+'\n\nHuman merge approval is required in the Pi pane. Flux reconciles main; the agent then probes the application.',
                'remove_source_branch': False, 'squash': False})
            binding = {'project': self.config['project'], 'iid': mr['iid'], 'head_sha': mr['sha'], 'base_sha': base_sha}
            self.save(mr={'binding': binding, 'url': mr['web_url'], 'reason': request['reason']}, phase='proposed')
            return self.inspect_mr(binding)

    def inspect_mr(self, request):
        state = self.state()
        if not state.get('mr') or request != state['mr']['binding']:
            raise Rejected('Use the recorded exact MR binding')
        request = state['mr']['binding']
        mr = self.api('merge_requests/'+str(request['iid']))
        if mr['sha'] != request['head_sha'] or mr['source_branch'] != self.config['rollback_branch'] or mr['target_branch'] != self.config['target_branch']:
            raise Rejected('MR head or branches changed; a fresh review and decision are required')
        candidate, _ = self.manifest(request['head_sha'])
        baseline, _ = self.manifest(request['base_sha'])
        expected = json.loads(json.dumps(baseline))
        expected['spec']['template']['spec']['containers'][0]['image'] = self.config['healthy_image']
        diffs = self.api('merge_requests/'+str(request['iid'])+'/diffs')
        valid = candidate == expected and len(diffs) == 1 and diffs[0]['old_path'] == diffs[0]['new_path'] == self.config['manifest_file']
        pipelines = self.api('pipelines?sha='+request['head_sha'])
        pipeline = next((p for p in pipelines if p['status'] == 'success'), None)
        jobs = self.api('pipelines/'+str(pipeline['id'])+'/jobs') if pipeline else []
        ci_pass = bool(pipeline and any(j['name'] == 'checkout-tests' and j['status'] == 'success' for j in jobs))
        return {'binding': request, 'url': mr['web_url'], 'state': mr['state'], 'draft': mr['draft'], 'diff_valid': valid,
            'diff': [d['diff'] for d in diffs], 'from_image': self.config['regression_image'], 'to_image': self.config['healthy_image'],
            'pipeline': pipeline, 'ci_pass': ci_pass, 'merge_status': mr['detailed_merge_status'],
            'review': state.get('review'), 'merge_commit_sha': mr.get('merge_commit_sha')}

    def merge_mr(self, request):
        with self.lock:
            state = self.state()
            info = self.inspect_mr(request)
            decision = state.get('decision', {})
            if decision.get('binding') != request or decision.get('approved') is not True or decision.get('expires', 0) <= time.time():
                raise Rejected('This exact MR has no live human merge decision')
            if info['state'] == 'merged':
                return info
            if state.get('merge_attempted'):
                raise Rejected('Merge outcome is uncertain. Inspect GitLab before any new human decision')
            if not info['diff_valid'] or not info['ci_pass'] or state.get('review', {}).get('binding') != request or state['review'].get('verdict') != 'PASS':
                raise Rejected('Exact rollback diff, successful CI and independent native review are required')
            current, current_sha = self.manifest()
            if current_sha != request['base_sha'] or current['spec']['template']['spec']['containers'][0]['image'] != self.config['regression_image']:
                raise Rejected('Target changed after proposal; stop for a fresh review')
            self.save(merge_attempted=True, phase='merging')
            mr = self.api('merge_requests/'+str(request['iid'])+'/merge', 'PUT', {'sha': request['head_sha'], 'should_remove_source_branch': False})
            if mr['state'] != 'merged':
                raise Rejected('GitLab did not return a merged receipt')
            self.save(merged={'sha': mr['merge_commit_sha'], 'at': mr['merged_at'], 'url': mr['web_url']}, phase='reconciling')
            return {'state': mr['state'], 'merge_commit_sha': mr['merge_commit_sha'], 'url': mr['web_url']}

    def verify_application(self, request):
        state = self.state()
        info = self.inspect_mr(request)
        source = self.kube('apis/source.toolkit.fluxcd.io/v1/namespaces/'+self.config['flux_namespace']+'/gitrepositories/'+self.config['flux_name'])
        rollout = self.kube('apis/kustomize.toolkit.fluxcd.io/v1/namespaces/'+self.config['flux_namespace']+'/kustomizations/'+self.config['flux_name'])
        probes = [self.probe() for _ in range(3)]
        deployment = self.read_deployment({})
        merge_sha = info['merge_commit_sha']
        applied = rollout.get('status', {}).get('lastAppliedRevision', '')
        success = bool(info['state'] == 'merged' and merge_sha and applied.endswith(merge_sha)
            and source.get('status', {}).get('artifact', {}).get('revision') == applied
            and deployment['status'].get('replicas') == deployment['status'].get('updatedReplicas') == 1
            and deployment['image'] == self.config['healthy_image']
            and deployment['status'].get('observedGeneration') == deployment['generation']
            and deployment['status'].get('availableReplicas') == 1
            and all(p['status'] == 200 and p['body'].get('version') == 'v1' and p['body'].get('total') == 20 for p in probes))
        result = {'fixed': success, 'merged_sha': merge_sha, 'flux_applied_revision': applied,
            'source_revision': source.get('status', {}).get('artifact', {}).get('revision'), 'deployment': deployment, 'probes': probes}
        self.save(verification=result, phase='completed' if success else 'reconciling')
        return result

    def control(self, body):
        with self.lock:
            action = body.get('action')
            state = self.state()
            if action == 'review':
                info = self.inspect_mr(body['binding'])
                if not info['diff_valid'] or not info['ci_pass'] or body.get('verdict') != 'PASS' or not body.get('task_id'):
                    raise Rejected('Read-only review must pass for this exact diff and CI head')
                return self.save(review={k: body[k] for k in ('binding', 'verdict', 'task_id')})
            if action == 'decision':
                if type(body.get('approved')) is not bool or body['binding'] != state.get('mr', {}).get('binding') or not body.get('task_id') or not body.get('approval_id'):
                    raise Rejected('Exact human boolean decision and native approval IDs required')
                if state.get('decision'):
                    previous = state['decision']
                    if all(previous[k] == body[k] for k in ('binding', 'approved', 'task_id', 'approval_id')):
                        return state
                    raise Rejected('A human decision is already recorded')
                if state.get('review', {}).get('verdict') != 'PASS':
                    raise Rejected('Independent review must finish first')
                self.inspect_mr(body['binding'])
                return self.save(decision={**body, 'at': time.time(), 'expires': time.time()+900}, phase='approved' if body['approved'] else 'declined')
            raise Rejected('Unknown control action')



READS = {'read_incident': 'Probe actual guest checkout and read the current pod logs.',
    'read_deployment': 'Read the live deployment image and rollout state.', 'read_gitops': 'Read main deployment manifest from the exact GitLab project.',
    'inspect_mr': 'Read the recorded rollback MR, exact diff, head pipeline and review.',
    'verify_application': 'Correlate merged SHA, Flux applied revision, live image and three checkout probes.'}
WRITES = {'create_rollback_mr': 'Create one real MR changing only image v2 to v1; never merge it.',
    'merge_mr': 'Merge the exact recorded MR only after native approval and independently recorded human authorization.'}


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

    def role(self):
        auth = self.headers.get('Authorization', '')
        return next((r for r,t in self.server.config['tokens'].items() if hmac.compare_digest(auth, 'Bearer '+t)), None)

    def do_GET(self):
        if self.path == '/healthz':
            return self.reply(200, {'ok': True})
        if self.role() != 'control' or self.path != '/control/state':
            return self.reply(401, {'error': 'Unauthorized'})
        backend = self.server.backend
        state = backend.state()
        try:
            if state.get('mr'):
                state['mr_info'] = backend.inspect_mr(state['mr']['binding'])
            if state.get('merged') and not state.get('verification', {}).get('fixed'):
                backend.verify_application(state['mr']['binding'])
                state.update(backend.state())
        except Exception as error:
            state['observation_error'] = type(error).__name__+': '+str(error)[:150]
        return self.reply(200, state)

    def do_POST(self):
        role = self.role()
        if not role:
            return self.reply(401, {'error': 'Unauthorized'})
        length = int(self.headers.get('Content-Length', 0))
        if not 0 < length <= 20000:
            return self.reply(400, {'error': 'Invalid body length'})
        body = json.loads(self.rfile.read(length))
        if self.path == '/control' and role == 'control':
            try:
                return self.reply(200, self.server.backend.control(body))
            except Rejected as error:
                return self.reply(409, {'error': str(error)})
        if self.path != '/mcp' or role not in ('investigator', 'reviewer'):
            return self.reply(403, {'error': 'Forbidden'})
        method, identity = body.get('method'), body.get('id')
        offered = {**READS, **(WRITES if role == 'investigator' else {})}
        if method == 'initialize':
            result = {'protocolVersion': body['params']['protocolVersion'], 'capabilities': {'tools': {}},
                'serverInfo': {'name': 'Lumen GitOps rollback', 'version': '1.0'}}
        elif method == 'tools/list':
            result = {'tools': [{'name': n, 'description': d, 'inputSchema': {'type': 'object', 'properties': {
                'request': {'type': 'object', 'description': 'For create_rollback_mr: {reason: string}. For inspect_mr, merge_mr and verify_application: exact binding {project:number,iid:number,head_sha:string,base_sha:string}. Other reads use {}.'}},
                'required': ['request'], 'additionalProperties': False}} for n,d in offered.items()]}
        elif method == 'tools/call':
            name = body['params']['name']
            try:
                if name not in offered:
                    raise Rejected('Tool is not allowed for this agent')
                result = {'content': [{'type': 'text', 'text': json.dumps(getattr(self.server.backend, name)(body['params'].get('arguments', {}).get('request', {})))}], 'isError': False}
            except Exception as error:
                result = {'content': [{'type': 'text', 'text': type(error).__name__+': '+str(error)[:200]}], 'isError': True}
        elif identity is None:
            self.send_response(202)
            self.end_headers()
            return
        else:
            return self.reply(200, {'jsonrpc': '2.0', 'id': identity, 'error': {'code': -32601, 'message': 'Method not found'}})
        self.reply(200, {'jsonrpc': '2.0', 'id': identity, 'result': result})
