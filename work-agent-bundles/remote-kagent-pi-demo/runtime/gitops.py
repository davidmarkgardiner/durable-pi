"""Observe native SDLC tasks, hand off review, and deliver the human's bound decision."""
import json
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

from chat import NativeChat, Conflict
from wire import ROLES, approval, number

EXT = 'https://kagent.dev/extensions/hitl/v1'


def incident_handoff(config, rows, trigger):
    """Correlate the saved classifier trigger with the original native message."""
    initial = next((r for r in rows if r['request_id'] == 'classified-checkout-incident'), None)
    if not trigger or not initial:
        return None
    samples = []
    for item in trigger['incident_samples']:
        sample, result = item['sample'], item['result']
        verdict = result['answers']['verdict']
        body = sample['body']
        samples.append({'at': int(sample['at']*1000), 'status': sample['status'], 'route': body.get('route', '/checkout'),
            'image': body.get('version', ''), 'error': body.get('error', '')+': '+body.get('message', ''),
            'model': result['model'], 'decision': verdict['choice'], 'probability': verdict['probabilities']['incident']})
    task = initial['task']
    message = next((m for m in task.get('history', []) if m.get('messageId') == initial['message_id']), None)
    matched = bool(initial['task_id'] and task.get('id') == initial['task_id']
        and task.get('contextId') == config['contexts']['investigator'] and message
        and '\n'.join(p.get('text', '') for p in message.get('parts', [])) == initial['content'])
    delivery = {'kind': 'accepted', 'taskId': task['id'], 'taskState': task['status']['state']} if matched else {
        'kind': 'unconfirmed', 'reason': 'The saved native history does not confirm this exact message yet'}
    return {'source': trigger['source'], 'triggeredAt': int(trigger['at']*1000), 'samples': samples,
        'policy': {'minimumIncidents': 3, 'minimumProbability': .7, 'matched': len(samples) == 3 and all(
            s['decision'] == 'incident' and s['probability'] >= .7 for s in samples)},
        'transport': 'A2A SendMessage', 'dispatcher': 'Pi bridge', 'agent': config['agents']['investigator'],
        'contextId': config['contexts']['investigator'], 'requestId': initial['request_id'],
        'messageId': initial['message_id'], 'instruction': initial['content'], 'delivery': delivery}


def outputs(task, name):
    values = []
    for artifact in task.get('artifacts', []):
        for part in artifact.get('parts', []):
            item = part.get('data', {})
            if item.get('name') != name or 'response' not in item:
                continue
            output = item['response'].get('output', item['response'])
            if isinstance(output, str):
                try:
                    output = json.loads(output)
                except ValueError:
                    continue
            if isinstance(output, dict) and 'content' in output:
                for content in output['content']:
                    try:
                        values.append(json.loads(content.get('text', '')))
                    except (ValueError, TypeError):
                        pass
            elif isinstance(output, dict):
                values.append(output)
    return values


class GitOps(NativeChat):
    def __init__(self, config, rpc):
        super().__init__(config, rpc)
        self.db.execute('CREATE TABLE IF NOT EXISTS workflow(id INTEGER PRIMARY KEY,value TEXT)')
        self.db.execute('INSERT OR IGNORE INTO workflow VALUES(1,?)', (json.dumps({'phase': 'monitoring'}),))
        self.db.commit()
        self.observed = {}
        self.observed_at = 0

    def workflow(self):
        with self.lock:
            return json.loads(self.db.execute('SELECT value FROM workflow WHERE id=1').fetchone()[0])

    def save(self, **patch):
        with self.lock:
            state = self.workflow()
            state.update(patch)
            self.db.execute('UPDATE workflow SET value=? WHERE id=1', (json.dumps(state),))
            self.db.commit()

    def backend(self, body=None):
        token = Path('/gitops-config/control.token').read_text().strip()
        req = Request(self.config['backend']+('/control' if body else '/control/state'),
            data=json.dumps(body).encode() if body else None,
            headers={'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'})
        with urlopen(req, timeout=30) as response:
            return json.load(response)

    def admit(self, *_):
        raise Conflict('This proactive GitOps workflow accepts its displayed human merge decision. Start a separate workspace for new instructions')

    def binding(self):
        rows = self.rows('investigator')
        row = next((r for r in rows if r['status'] == 'waiting'), None)
        if not row:
            return None
        tools = (approval(row['task']) or {}).get('tools', [])
        if len(tools) != 1 or tools[0]['name'] != 'merge_mr':
            return None
        request = tools[0].get('args', {}).get('request')
        if request != self.observed.get('mr', {}).get('binding'):
            return None
        # Protobuf Struct exposes integral identifiers as floats. Preserve the
        # canonical GitLab integer binding after checking the native tool args.
        return {'taskId': row['task_id'], 'approvalId': tools[0]['id'], 'request': self.observed['mr']['binding']}

    def tick(self):
        super().tick()
        if time.time()-self.observed_at < 3:
            return
        self.observed = self.backend()
        self.observed_at = time.time()
        workflow = self.workflow()
        rows = self.rows()
        if self.observed.get('trigger') and not rows:
            source = self.observed['trigger']['source']
            super().admit('investigator', {'requestId': 'classified-checkout-incident', 'content':
                source+' classified three real synthetic guest-checkout HTTP 500 responses as incidents. '
                'Investigate this application with read_incident, read_deployment and read_gitops. '
                'Determine the cause and create_rollback_mr with your evidence-based reason. '
                'Use the exact returned binding to inspect_mr and request merge_mr. '
                'Do not claim a merge or fix before the human decision. After approved merge, call verify_application with that binding once. '
                'If Flux has not applied yet, report waiting rather than fixed.'})
            self.save(phase='investigating')
        binding = self.binding()
        info = self.observed.get('mr_info', {})
        if binding and info.get('ci_pass') and info.get('diff_valid') and not self.rows('reviewer'):
            super().admit('reviewer', {'requestId': 'review-rollback', 'content':
                'Independently review the rollback MR with inspect_mr using request '+json.dumps(binding['request'])+'. '
                'Confirm only deploy/deployment.json image v2 changes to v1 and the exact head has successful checkout-tests CI. '
                'Read the incident or deployment if needed. Do not create or merge anything. '
                'If all checks pass, finish with exactly PASS '+binding['request']['head_sha']+'. Otherwise report FAIL with evidence.'})
            self.save(phase='reviewing')
        reviews = self.rows('reviewer')
        if binding and reviews and reviews[-1]['status'] == 'completed' and not self.observed.get('review'):
            task = reviews[-1]['task']
            texts = [p['text'] for a in task.get('artifacts', []) for p in a.get('parts', []) if p.get('text')]
            checks = outputs(task, 'inspect_mr')
            expected = 'PASS '+binding['request']['head_sha']
            if any(expected in t for t in texts) and any(c.get('binding') == binding['request'] and c.get('ci_pass') is True and c.get('diff_valid') is True for c in checks):
                self.backend({'action': 'review', 'binding': binding['request'], 'verdict': 'PASS', 'task_id': task['id']})
                self.save(phase='awaiting_approval')
            else:
                self.save(phase='review_failed', error='Native reviewer did not return a verified PASS for this exact head')
        workflow = self.workflow()
        decision = workflow.get('decision')
        if decision and decision['delivery'] == 'not_sent':
            current = self.binding()
            if current != decision['binding']:
                raise Conflict('Native merge approval changed before delivery')
            self.save(decision={**decision, 'delivery': 'sending'})
            approved = decision['approved']
            self.call('investigator', 'SendMessage', {'message': {'messageId': decision['message_id'],
                'contextId': self.config['contexts']['investigator'], 'taskId': current['taskId'], 'role': 'ROLE_USER',
                'parts': [{'text': 'The human approved this exact MR head. Merge it, then call verify_application once.' if approved else 'The human declined. Do not merge.'}],
                'extensions': [EXT], 'metadata': {EXT: {'type': 'tool_approval_response', 'approvals': [
                    {'id': current['approvalId'], 'approved': approved, 'rejection_reason': '' if approved else 'Human declined this merge.'}]}}},
                'configuration': {'returnImmediately': True, 'historyLength': 100}})
            self.save(decision={**decision, 'delivery': 'sent'}, phase='reconciling' if approved else 'declined')
        if self.observed.get('verification', {}).get('fixed'):
            investigator = self.rows('investigator')
            if investigator[-1]['status'] == 'completed' and not any(r['request_id'] == 'post-flux-verification' for r in investigator):
                super().admit('investigator', {'requestId': 'post-flux-verification', 'content':
                    'Flux reconciliation is now observed. Call verify_application with request '+json.dumps(self.observed['mr']['binding'])+
                    '. Report the actual merged SHA, applied Flux revision, live image and three checkout status codes. Only say fixed if the tool returns fixed=true.'})
                self.save(phase='verifying')
            elif investigator[-1]['request_id'] == 'post-flux-verification' and investigator[-1]['status'] == 'completed':
                checks = outputs(investigator[-1]['task'], 'verify_application')
                if any(c.get('fixed') is True and c.get('merged_sha') == self.observed['verification']['merged_sha'] for c in checks):
                    self.save(phase='completed')

    def decide(self, run_id, body):
        with self.lock:
            if set(body) != {'approved', 'binding'} or type(body['approved']) is not bool:
                raise Conflict('Explicit human boolean and displayed MR binding required')
            previous = self.workflow().get('decision')
            if previous:
                if str(self.job_id()) == run_id and previous['approved'] == body['approved'] and previous['binding'] == body['binding']:
                    return {'ok': True}
                raise Conflict('A different human decision is already recorded')
            current = self.binding()
            if current is None or current != body['binding'] or str(self.job_id()) != run_id or self.workflow()['phase'] != 'awaiting_approval':
                raise Conflict('Displayed merge approval changed or review is incomplete')
            self.backend({'action': 'decision', 'binding': current['request'], 'approved': body['approved'],
                'task_id': current['taskId'], 'approval_id': current['approvalId']})
            self.save(decision={'binding': current, 'approved': body['approved'], 'delivery': 'not_sent', 'message_id': str(uuid.uuid4())})
            return {'ok': True}

    def summary(self, role):
        value = super().summary(role)
        value['name'] = 'Checkout specialist' if role == 'investigator' else 'Rollback reviewer'
        value['busy'] = any(r['status'] in ('queued', 'sending', 'working') for r in self.rows(role))
        value['background'] = int(any(r['status'] == 'waiting' for r in self.rows(role)))
        return value

    def session(self):
        return {**super().session(), 'name': 'Lumen GitLab rollback', 'dbPath': 'Native TaskStore + GitOps workflow PVC'}

    def interaction(self):
        return {'kind': 'approval-only', 'reason': 'Proactive checkout incident → GitLab MR → human merge → Flux → application verification'}

    def job_id(self):
        rows = self.rows('investigator')
        return number(rows[0]['task_id'] or rows[0]['message_id']) if rows else number(self.config['workspace_id'])

    def snapshot(self, role):
        value = super().snapshot(role)
        value['entries'][0]['data']['text'] = 'Configured work model on native kagent '+self.summary(role)['name']+'. Context '+self.config['contexts'][role]+'. Real GitLab and read-only Kubernetes tools.'
        if role == 'investigator':
            value['entries'].append({'id': len(value['entries'])+1, 'conversationId': 1, 'kind': 'demo.job', 'data': {'taskId': self.job_id()}})
        return value

    def jobs(self):
        state, observed = self.workflow(), self.observed
        phase = state['phase']
        names = [('monitoring', 'Detect checkout failure'), ('investigating', 'Investigate and open MR'),
            ('reviewing', 'Review exact diff and CI'), ('awaiting_approval', 'Human merge decision'),
            ('reconciling', 'Merge and Flux rollout'), ('verifying', 'Verify guest checkout')]
        position = next((i for i,(n,_) in enumerate(names) if n == phase), 5 if phase == 'completed' else 2)
        ready = phase == 'awaiting_approval'
        phases = [{'id': n, 'label': label, 'status': 'done' if phase == 'completed' or i < position else 'waiting' if ready and i == position else 'running' if i == position else 'pending', 'steps': []} for i,(n,label) in enumerate(names)]
        mr = observed.get('mr')
        if mr:
            phases[1]['summary'] = mr['url']
        if observed.get('mr_info', {}).get('pipeline'):
            phases[2]['summary'] = 'GitLab pipeline '+str(observed['mr_info']['pipeline']['id'])+' · '+observed['mr_info']['pipeline']['status']
        if observed.get('verification'):
            phases[-1]['steps'] = [{'id': 'http-probes', 'kind': 'checkpoint', 'label': 'Actual checkout and Flux readback', 'status': 'done' if observed['verification']['fixed'] else 'running', 'iteration': 0, 'at': int(time.time()*1000), 'detail': json.dumps(observed['verification'], indent=2)}]
        run = {'id': self.job_id(), 'job': 'native-kagent-gitlab-merge', 'title': 'Restore guest checkout via GitLab', 'run': 1,
            'input': {}, 'startedBy': 'agent', 'background': True, 'status': 'completed' if phase == 'completed' else 'declined' if phase == 'declined' else 'failed' if phase == 'review_failed' else 'waiting' if ready else 'running',
            'phase': phase, 'phases': phases, 'resumed': 0, 'startedAt': self.config['created_at'], 'updatedAt': int(time.time()*1000)}
        handoff = incident_handoff(self.config, self.rows('investigator'), observed.get('trigger'))
        if handoff:
            run['incidentHandoff'] = handoff
        binding = self.binding()
        if ready and binding:
            run['approval'] = 'pending'
            run['approvalBinding'] = binding
        elif state.get('decision'):
            run['approval'] = 'approved' if state['decision']['approved'] else 'declined'
        if mr:
            run['decisionSummary'] = {'cause': mr['reason'], 'change': self.config['manifest_file']+': '+self.config['regression_image']+' → '+self.config['healthy_image'],
                'expectedResult': 'Guest checkout returns HTTP 200 and total 20 after Flux reconciles main.', 'scope': 'Only the configured demo repository and namespace '+self.config['application_namespace']+' in '+self.config['cluster_label'],
                'approveEffect': 'Merge MR !'+str(mr['binding']['iid'])+' at the displayed head SHA. Flux then changes the live deployment; the agent checks checkout.',
                'declineEffect': 'Leave the MR open and the application unchanged.', 'operation': 'GitLab project '+str(mr['binding']['project'])+' MR !'+str(mr['binding']['iid']),
                'revision': 1, 'proposalHash': mr['binding']['head_sha'], 'review': 'Native read-only reviewer PASS for this exact head' if observed.get('review') else 'Review pending',
                'mergeRequestUrl': mr['url'], 'headSha': mr['binding']['head_sha'], 'pipelineUrl': (observed.get('mr_info', {}).get('pipeline') or {}).get('web_url')}
        if state.get('error'):
            run['error'] = state['error']
        return {'counts': {'native-kagent-gitlab-merge': 1}, 'items': {str(run['id']): run}}
