"""Safety-critical merge behavior: invalid approvals never send a GitLab mutation."""
import importlib.util
import json
import sqlite3
import threading
import time
import unittest
from pathlib import Path
from gitops import GitOps, outputs, incident_handoff, EXT

spec = importlib.util.spec_from_file_location('rollback_mcp', Path(__file__).parent/'gitops/mcp.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MergeGate(unittest.TestCase):
    def setUp(self):
        self.backend = module.Rollback.__new__(module.Rollback)
        self.backend.lock = threading.RLock()
        self.backend.db = sqlite3.connect(':memory:')
        self.backend.db.execute('CREATE TABLE state(id INTEGER PRIMARY KEY,value TEXT)')
        self.backend.db.execute('INSERT INTO state VALUES(1,?)', ('{}',))
        self.binding = {'project': 1, 'iid': 1, 'head_sha': 'head', 'base_sha': 'base'}
        self.info = {'state': 'opened', 'diff_valid': True, 'ci_pass': True}
        self.backend.inspect_mr = lambda request: self.info
        self.backend.manifest = lambda ref='main': ({'spec': {'template': {'spec': {'containers': [{'image': 'lumen-checkout:v2'}]}}}}, 'base')
        self.calls = []
        def api(path, method='GET', body=None):
            self.calls.append((path, method, body))
            return {'state': 'merged', 'merge_commit_sha': 'merge', 'merged_at': 'now', 'web_url': 'https://gitlab.example/mr/1'}
        self.backend.api = api
        self.backend.save(decision={'binding': self.binding, 'approved': True, 'expires': time.time()+60},
            review={'binding': self.binding, 'verdict': 'PASS'})

    def tearDown(self):
        self.backend.db.close()

    def assert_rejected_without_mutation(self):
        with self.assertRaises(module.Rejected):
            self.backend.merge_mr(self.binding)
        self.assertEqual(self.calls, [])

    def test_no_human_decision(self):
        self.backend.save(decision=None)
        # A missing ledger decision must reject, rather than bypass authorization.
        self.backend.save(decision={})
        self.assert_rejected_without_mutation()

    def test_expired_or_changed_head_decision(self):
        for patch in ({'expires': 0}, {'binding': {**self.binding, 'head_sha': 'other'}}, {'approved': False}):
            self.backend.save(decision={'binding': self.binding, 'approved': True, 'expires': time.time()+60, **patch})
            self.assert_rejected_without_mutation()

    def test_ci_diff_or_review_failure(self):
        for key in ('ci_pass', 'diff_valid'):
            self.info[key] = False
            self.assert_rejected_without_mutation()
            self.info[key] = True
        self.backend.save(review={'binding': {**self.binding, 'head_sha': 'other'}, 'verdict': 'PASS'})
        self.assert_rejected_without_mutation()

    def test_changed_target(self):
        self.backend.manifest = lambda ref='main': ({'spec': {'template': {'spec': {'containers': [{'image': 'lumen-checkout:v2'}]}}}}, 'changed')
        self.assert_rejected_without_mutation()

    def test_exact_authorization_merges_once(self):
        receipt = self.backend.merge_mr(self.binding)
        self.assertEqual(receipt['merge_commit_sha'], 'merge')
        self.assertEqual(self.calls[0][2]['sha'], 'head')
        with self.assertRaises(module.Rejected):
            self.backend.merge_mr(self.binding)
        self.assertEqual(len(self.calls), 1)


class NativeReceipts(unittest.TestCase):
    def test_classifier_handoff_requires_matching_native_message(self):
        config = {'agents': {'investigator': 'specialist'}, 'contexts': {'investigator': 'context'}}
        content = 'Three incident judgments. Investigate the application.'
        task = {'id': 'task', 'contextId': 'context', 'status': {'state': 'TASK_STATE_FAILED'},
            'history': [{'messageId': 'message', 'parts': [{'text': content}]}]}
        row = {'request_id': 'classified-checkout-incident', 'message_id': 'message', 'task_id': 'task',
            'content': content, 'task': task}
        sample = {'sample': {'at': 1, 'status': 500, 'body': {'route': '/checkout', 'version': 'v2', 'error': 'KeyError', 'message': 'loyalty'}},
            'result': {'model': 'jev', 'answers': {'verdict': {'choice': 'incident', 'probabilities': {'incident': 1}}}}}
        trigger = {'at': 2, 'source': 'TypeSafe Jev', 'incident_samples': [sample, sample, sample]}
        handoff = incident_handoff(config, [row], trigger)
        self.assertTrue(handoff['policy']['matched'])
        self.assertEqual(handoff['instruction'], content)
        self.assertEqual(handoff['delivery'], {'kind': 'accepted', 'taskId': 'task', 'taskState': 'TASK_STATE_FAILED'})
        # Provider failure does not erase the native admission receipt.
        task['history'][0]['parts'][0]['text'] = 'Different instruction'
        self.assertEqual(incident_handoff(config, [row], trigger)['delivery']['kind'], 'unconfirmed')
        self.assertIsNone(incident_handoff(config, [], trigger))

    def test_repeated_human_submission_does_not_resend(self):
        w = GitOps.__new__(GitOps)
        w.lock = threading.RLock()
        binding = {'taskId': 'task', 'approvalId': 'approval', 'request': {'head_sha': 'head'}}
        w.workflow = lambda: {'decision': {'binding': binding, 'approved': True, 'delivery': 'sending'}}
        w.job_id = lambda: 13
        w.binding = lambda: self.fail('A repeated decision must not request another native approval')
        w.backend = lambda body: self.fail('A repeated decision must not publish another authorization')
        self.assertEqual(w.decide('13', {'approved': True, 'binding': binding}), {'ok': True})
        with self.assertRaises(ValueError):
            w.decide('13', {'approved': False, 'binding': binding})

    def test_native_float_ids_keep_canonical_gitlab_binding(self):
        w = GitOps.__new__(GitOps)
        binding = {'project': 123, 'iid': 1, 'head_sha': 'head', 'base_sha': 'base'}
        w.observed = {'mr': {'binding': binding}}
        task = {'status': {'message': {'metadata': {EXT: {'tools': [{'name': 'merge_mr', 'id': 'approval',
            'args': {'request': {**binding, 'project': 123.0, 'iid': 1.0}}}]}}}}}
        w.rows = lambda role: [{'status': 'waiting', 'task_id': 'task', 'task': task}]
        actual = w.binding()['request']
        self.assertIs(type(actual['project']), int)
        self.assertIs(type(actual['iid']), int)
        self.assertEqual(actual, binding)

    def test_json_string_tool_result_is_read_as_evidence(self):
        receipt = {'binding': {'head_sha': 'head'}, 'ci_pass': True, 'diff_valid': True}
        task = {'artifacts': [{'parts': [{'data': {'name': 'inspect_mr', 'response': {'output': json.dumps(receipt)}}}]}]}
        self.assertEqual(outputs(task, 'inspect_mr'), [receipt])

    def test_tool_intent_and_invalid_text_are_not_receipts(self):
        task = {'artifacts': [{'parts': [{'data': {'name': 'inspect_mr', 'args': {'request': {}}}},
            {'data': {'name': 'inspect_mr', 'response': {'output': 'not a receipt'}}}]}]}
        self.assertEqual(outputs(task, 'inspect_mr'), [])


if __name__ == '__main__':
    unittest.main()
