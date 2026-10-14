"""Translate saved kagent A2A artifacts into the Pi hub's display contract."""
import datetime
import hashlib
import json

EXT = 'https://kagent.dev/extensions/hitl/v1'
ROLES = {'investigator': 1, 'reviewer': 2}
USAGE = {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0, 'totalTokens': 0,
         'cost': {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0, 'total': 0}}
PHASES = [('inspect', 'Investigate and review'), ('approve', 'Human decision'),
          ('publish', 'Synthetic effect'), ('verify', 'Independent readback')]


def number(value):
    return int(hashlib.sha256(str(value).encode()).hexdigest()[:12], 16)


def timestamp(value):
    try:
        return int(datetime.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp() * 1000)
    except (TypeError, ValueError, AttributeError):
        return 0


def approval(task):
    return task.get('status', {}).get('message', {}).get('metadata', {}).get(EXT)


def approval_binding(task):
    tools = (approval(task) or {}).get('tools', [])
    if len(tools) != 1 or tools[0].get('name') != 'publish_proposal':
        return None
    tool = tools[0]
    request = tool.get('args', {}).get('request', {})
    if set(request) != {'op_id', 'revision', 'proposal_hash', 'decision_id'}:
        return None
    return {'taskId': task['id'], 'approvalId': tool['id'], 'request': request}


def validate_decision(body, task):
    if not isinstance(body, dict) or set(body) != {'approved', 'binding'} or type(body['approved']) is not bool:
        raise ValueError('Explicit boolean decision and displayed approval binding required')
    current = approval_binding(task)
    if current is None or body['binding'] != current:
        raise ValueError('Displayed approval changed. Refresh the proposal before deciding')
    return {'task_id': current['taskId'], 'approval_id': current['approvalId'], 'request': current['request']}


def fixture_decision(body):
    revision = body.get('revision')
    if type(revision) not in (int, float) or revision != int(revision) or not 1 <= revision <= 1000:
        raise ValueError('Proposal revision must be an integer between 1 and 1000')
    return {**body, 'revision': int(revision)}


def assistant(content, model='scripted-native'):
    return {'role': 'assistant', 'content': content, 'provider': 'kagent',
            'model': model, 'usage': USAGE, 'stopReason': 'stop'}


def entries(state, role):
    data = state['roles'][role]
    agent = ROLES[role]
    result = [{'id': 1, 'conversationId': agent, 'kind': 'kagent.binding', 'data': {
        'text': 'Native kagent actor. '+state.get('model_label', 'Scripted model.')+' Agent '+data['agent']+'; context '+str(data['context'])+'; task '+str(data['task_id'])+'. Saved controller artifacts below.',
        'agent': data['agent'], 'contextId': data['context'], 'taskId': data['task_id']}}]
    task = data.get('task', {})
    history = task.get('history', [])
    for message in history:
        if message.get('role') == 'ROLE_USER':
            result.append({'id': len(result)+1, 'conversationId': agent, 'kind': 'pi.user',
                'model': [{'role': 'user', 'content': '\n'.join(p.get('text', '') for p in message.get('parts', []))}]})
    artifacts = sorted(task.get('artifacts', []), key=lambda a: a.get('metadata', {}).get('kagent.dev/a2a/timeline-position', ''))
    for artifact in artifacts:
        for part in artifact.get('parts', []):
            item = part.get('data')
            if item and item.get('name'):
                if 'response' in item:
                    response = item['response']
                    if 'requires confirmation' in str(response.get('error', '')):
                        # A rejected pre-approval call is not an executed effect.
                        continue
                    result.append({'id': len(result)+1, 'conversationId': agent, 'kind': 'pi.tool-result',
                        'data': {'nativeArtifactId': artifact.get('artifactId')},
                        'model': [{'role': 'toolResult', 'toolCallId': item['id'], 'toolName': item['name'],
                            'content': [{'type': 'text', 'text': json.dumps(response, indent=2)}],
                            'isError': bool(response.get('error')), 'details': response}]})
                else:
                    result.append({'id': len(result)+1, 'conversationId': agent, 'kind': 'pi.assistant',
                        'data': {'nativeArtifactId': artifact.get('artifactId')},
                        'model': [assistant([{'type': 'toolCall', 'id': item['id'], 'name': item['name'], 'arguments': item.get('args', {})}], state.get('model_id', 'scripted-native'))]})
            elif part.get('text'):
                result.append({'id': len(result)+1, 'conversationId': agent, 'kind': 'pi.assistant',
                    'model': [assistant([{'type': 'text', 'text': part['text']}], state.get('model_id', 'scripted-native'))]})
    if role == 'investigator' and (approval(task) or state.get('decision')):
        result.append({'id': len(result)+1, 'conversationId': agent, 'kind': 'demo.job',
                       'data': {'taskId': number(task['id'])}})
    return result


def jobs(state):
    task = state['roles']['investigator'].get('task', {})
    request = approval(task)
    if not request and not state.get('decision'):
        return {'counts': {}, 'items': {}}
    identity = number(task['id'])
    done = bool(state.get('verification'))
    decided = bool(state.get('decision'))
    ready = state['phase'] == 'awaiting_approval'
    denied = decided and state['decision']['fixture']['disposition'] != 'approve'
    statuses = ['done' if state.get('review') else 'running',
                'done' if decided else 'waiting' if ready else 'pending',
                'skipped' if denied else 'done' if done else 'running' if decided else 'pending',
                'done' if done else 'pending']
    phases = [{'id': name, 'label': label, 'status': status, 'steps': []}
              for (name, label), status in zip(PHASES, statuses)]
    if request:
        phases[1]['steps'] = [{'id': 'native-approval', 'kind': 'approval', 'label': 'Native kagent tool approval',
            'detail': json.dumps(request, indent=2), 'status': 'done' if decided else 'waiting',
            'iteration': 0, 'at': timestamp(task.get('status', {}).get('timestamp'))}]
    run = {'id': identity, 'job': 'native-kagent-approval', 'title': 'Native kagent proposal', 'run': 1,
        'input': {}, 'startedBy': 'agent', 'background': True,
        'status': 'completed' if done else 'waiting' if ready else 'running',
        'phase': 'verify' if done else 'publish' if decided else 'approve' if ready else 'inspect',
        'phases': phases, 'resumed': 0, 'startedAt': timestamp(task.get('status', {}).get('timestamp')),
        'updatedAt': timestamp(state.get('connection', {}).get('observed_at'))}
    decision = decision_summary(state, request)
    if decision:
        run['decisionSummary'] = decision
    binding = approval_binding(task)
    if binding:
        run['approvalBinding'] = binding
    if ready:
        run['approval'] = 'pending'
    elif decided:
        run['approval'] = 'declined' if denied else 'approved'
    return {'counts': {'native-kagent-approval': 1}, 'items': {str(identity): run}}


def decision_summary(state, request):
    """Describe only a recorded proposal whose receipt matches the pending publish call."""
    pending = [t for t in (request or {}).get('tools', []) if t.get('name') == 'publish_proposal']
    if len(pending) != 1:
        return None
    binding = pending[0].get('args', {}).get('request', {})
    parts = [p.get('data', {}) for a in state['roles']['investigator'].get('task', {}).get('artifacts', [])
             for p in a.get('parts', [])]
    for intent in parts:
        if intent.get('name') != 'record_proposal' or 'args' not in intent:
            continue
        record = intent['args'].get('request', {})
        receipt = next((p.get('response', {}).get('output', {}) for p in parts
            if p.get('name') == 'record_proposal' and p.get('id') == intent.get('id') and 'response' in p), {})
        if not all(binding.get(k) is not None and receipt.get(k) == binding[k] for k in ('op_id', 'revision', 'proposal_hash')):
            continue
        proposal = record.get('proposal', {})
        if not all(isinstance(proposal.get(k), str) for k in ('cause', 'change', 'verification')):
            continue
        return {'cause': proposal['cause'],
            'change': 'Disable the feature in the protected synthetic fixture' if proposal['change'] == 'disable_feature' else proposal['change'],
            'expectedResult': 'The synthetic caller succeeds without the required field' if proposal['verification'] == 'caller_without_field_succeeds' else proposal['verification'],
            'scope': 'Protected comparison fixture in namespace durable-fixture. The original checkout deployment and repository are outside this decision.',
            'approveEffect': 'Approve runs publish_proposal for this exact revision, commits one synthetic effect, then reads back its result.',
            'declineEffect': 'Reject ends this proposal without publishing a change.',
            'operation': binding['op_id'], 'revision': binding['revision'], 'proposalHash': binding['proposal_hash'],
            'review': state.get('review', {}).get('verdict', 'Not available')+' for the recorded proposal. Native reasoning in this trial is scripted.'}
    return None


def summary(state, role):
    data = state['roles'][role]
    native_state = data.get('task', {}).get('status', {}).get('state')
    return {'id': ROLES[role], 'name': 'Native investigator' if role == 'investigator' else 'Native read-only reviewer',
            'named': True, 'kind': 'root', 'busy': native_state in ('TASK_STATE_WORKING', 'TASK_STATE_SUBMITTED'),
            'background': int(native_state == 'TASK_STATE_INPUT_REQUIRED')}


def snapshot(state, role):
    task = state['roles'][role].get('task', {})
    request = approval(task)
    tools = [{'callId': t.get('call_id', t['id']), 'name': t['name'], 'status': 'pending', 'output': 'Waiting for native kagent approval'}
             for t in request.get('tools', [])] if request else []
    value = {'type': 'snapshot', 'entries': entries(state, role), 'tools': tools, 'compactions': [], 'inbox': [],
        'agent': {'model': {'provider': 'kagent', 'modelId': 'scripted-native'}, 'thinkingLevel': 'off'},
        'usage': {'models': {}, 'tools': {}}}
    if summary(state, role)['busy']:
        value['run'] = {'inputs': []}
    return value
