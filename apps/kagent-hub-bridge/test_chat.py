import tempfile
import time
import unittest
from pathlib import Path
from chat import NativeChat, Conflict


class RPC:
    def __init__(self):
        self.calls = []
        self.tasks = []
        self.lose_response = False

    def call(self, service, method, body):
        self.calls.append((method, body))
        if method == 'SendMessage':
            task = {'id': 'task-'+str(len(self.tasks)+1), 'contextId': body['message']['contextId'],
                'status': {'state': 'TASK_STATE_WORKING'}, 'history': [body['message']], 'artifacts': []}
            self.tasks.append(task)
            if self.lose_response:
                raise TimeoutError('Response lost after admission')
            return {'task': task}
        if method == 'ListTasks':
            return {'tasks': self.tasks}
        if method == 'GetTask':
            task = next(t for t in self.tasks if t['id'] == body['id'])
            return {'task': {**task, 'status': {'state': 'TASK_STATE_COMPLETED'},
                'artifacts': [{'parts': [{'text': 'Native reply'}]}]}}
        raise AssertionError(method)


class ChatTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = {'data': self.temp.name, 'workspace_id': 'chat',
            'agents': {'investigator': 'native-specialist', 'reviewer': 'native-reviewer'},
            'contexts': {'investigator': 'specialist-context', 'reviewer': 'reviewer-context'},
            'created_at': 0, 'max_calls': 8, 'token_budget': 20000}
        self.rpc = RPC()
        self.chat = self.make_chat()
        self.addCleanup(self.chat.db.close)

    def make_chat(self):
        chat = NativeChat(self.config, self.rpc)
        chat.budget_at = time.time()+1000
        return chat

    def message(self, request='request', content='Investigate the incident'):
        return {'content': content, 'requestId': request, 'whenBusy': 'reject'}

    def test_repeated_send_is_admitted_once(self):
        first = self.chat.admit('investigator', self.message())
        self.assertEqual(self.chat.admit('investigator', self.message()), first)
        self.chat.tick()
        self.chat.admit('investigator', self.message())
        self.chat.tick()
        self.assertEqual(sum(m == 'SendMessage' for m,b in self.rpc.calls), 1)

    def test_a_reused_request_id_cannot_change_content(self):
        self.chat.admit('investigator', self.message())
        with self.assertRaises(Conflict):
            self.chat.admit('investigator', self.message(content='Different task'))

    def test_busy_agent_rejects_a_second_task(self):
        self.chat.admit('investigator', self.message())
        with self.assertRaises(Conflict):
            self.chat.admit('investigator', self.message(request='second'))
        self.chat.admit('reviewer', self.message(request='second'))

    def test_lost_reply_reconciles_after_restart_without_resending(self):
        self.rpc.lose_response = True
        self.chat.admit('investigator', self.message())
        self.chat.tick()
        self.assertEqual(self.chat.rows()[0]['status'], 'uncertain')
        restored = self.make_chat()
        self.addCleanup(restored.db.close)
        restored.tick()
        self.assertEqual(restored.rows()[0]['task_id'], 'task-1')
        restored.admit('investigator', self.message())
        restored.tick()
        self.assertEqual(sum(m == 'SendMessage' for m,b in self.rpc.calls), 1)

    def test_followup_keeps_context_and_both_turns_visible(self):
        self.chat.admit('investigator', self.message())
        self.chat.tick(); self.chat.tick()
        self.chat.admit('investigator', self.message(request='second', content='Explain your evidence'))
        self.chat.tick(); self.chat.tick()
        contexts = [b['message']['contextId'] for m,b in self.rpc.calls if m == 'SendMessage']
        self.assertEqual(contexts, ['specialist-context', 'specialist-context'])
        items = self.chat.snapshot('investigator')['entries']
        self.assertEqual(len([e for e in items if e['kind'] == 'pi.user']), 2)
        self.assertEqual([e['model'][0]['model'] for e in items if e['kind'] == 'pi.assistant'], ['kimi-for-coding']*2)

    def test_exhausted_budget_prevents_admission(self):
        self.chat.budget = {'calls': 8, 'max_calls': 8, 'halted': False}
        with self.assertRaises(Conflict):
            self.chat.admit('investigator', self.message())
        self.assertEqual(self.chat.rows(), [])

    def test_unsupported_queueing_is_not_silently_changed(self):
        with self.assertRaises(Conflict):
            self.chat.admit('investigator', {**self.message(), 'whenBusy': 'steer'})


if __name__ == '__main__':
    unittest.main()
