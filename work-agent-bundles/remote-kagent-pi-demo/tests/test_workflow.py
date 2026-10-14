"""Exercise real portable gate and fault functions. No connected writes or model calls."""
import copy
import json
import sqlite3
import threading
import time
import unittest
from classifier import classify
from gitops import incident_handoff
from rollback import Rejected
from tools import WorkTools


class Workflow(unittest.TestCase):
    def setUp(self):
        self.tools = WorkTools.__new__(WorkTools)
        self.tools.lock = threading.RLock()
        self.tools.db = sqlite3.connect(':memory:')
        self.tools.db.execute('CREATE TABLE state(id INTEGER PRIMARY KEY,value TEXT)')
        self.tools.db.execute('INSERT INTO state VALUES(1,?)', ('{}',))
        self.tools.config = {'healthy_image': 'registry.example/checkout:v1', 'regression_image': 'registry.example/checkout:v2',
            'workspace_id': 'test', 'target_branch': 'main', 'manifest_file': 'deploy/deployment.json'}
        self.good = {'spec': {'template': {'spec': {'containers': [{'image': self.tools.config['healthy_image']}]}}}}
        self.tools.probe = lambda: {'status': 200, 'body': {'version': 'v1', 'total': 20}}
        self.tools.read_deployment = lambda _: {'image': self.tools.config['healthy_image']}
        self.tools.manifest = lambda ref=None: (copy.deepcopy(self.good), 'base')
        self.calls = []
        def api(path, method='GET', body=None):
            self.calls.append((path, method, body))
            return {'id': 'fault', 'state': 'merged', 'merge_commit_sha': 'merge', 'merged_at': 'now', 'web_url': 'https://gitlab.example/mr/1'}
        self.tools.api = api
        self.binding = {'project': 1, 'iid': 1, 'head_sha': 'head', 'base_sha': 'base'}

    def tearDown(self): self.tools.db.close()

    def test_fault_commits_once_with_precondition(self):
        self.assertEqual(self.tools.start_demo()['regression_commit'], 'fault')
        self.tools.start_demo()
        self.assertEqual(len(self.calls), 1)
        action = self.calls[0][2]['actions'][0]
        self.assertEqual(action['last_commit_id'], 'base')
        self.assertEqual(json.loads(action['content'])['spec']['template']['spec']['containers'][0]['image'], self.tools.config['regression_image'])

    def test_fault_rejects_unhealthy_or_uncertain_baseline(self):
        self.tools.probe = lambda: {'status': 500, 'body': {'version': 'v2'}}
        with self.assertRaises(Rejected): self.tools.start_demo()
        self.assertEqual(self.calls, [])
        self.tools.save(starting=True)
        with self.assertRaises(Rejected): self.tools.start_demo()
        self.assertEqual(self.calls, [])

    def test_ambiguous_fault_response_stops_retry(self):
        def fail(*_): raise TimeoutError('write outcome unknown')
        self.tools.api = fail
        with self.assertRaises(TimeoutError): self.tools.start_demo()
        self.assertTrue(self.tools.state()['starting'])
        with self.assertRaises(Rejected): self.tools.start_demo()

    def prepare_merge(self):
        bad = copy.deepcopy(self.good)
        bad['spec']['template']['spec']['containers'][0]['image'] = self.tools.config['regression_image']
        self.tools.manifest = lambda ref=None: (copy.deepcopy(bad), 'base')
        self.info = {'state': 'opened', 'diff_valid': True, 'ci_pass': True}
        self.tools.inspect_mr = lambda _: self.info
        self.tools.save(decision={'binding': self.binding, 'approved': True, 'expires': time.time()+60},
            review={'binding': self.binding, 'verdict': 'PASS'})

    def test_no_merge_without_exact_live_human_decision(self):
        self.prepare_merge()
        for decision in ({}, {'binding': self.binding, 'approved': False, 'expires': time.time()+60},
            {'binding': {**self.binding, 'head_sha': 'other'}, 'approved': True, 'expires': time.time()+60},
            {'binding': self.binding, 'approved': True, 'expires': 0}):
            self.tools.save(decision=decision)
            with self.assertRaises(Rejected): self.tools.merge_mr(self.binding)
        self.assertEqual(self.calls, [])

    def test_failed_diff_ci_review_and_target_block_merge(self):
        self.prepare_merge()
        for key in ('ci_pass', 'diff_valid'):
            self.info[key] = False
            with self.assertRaises(Rejected): self.tools.merge_mr(self.binding)
            self.info[key] = True
        self.tools.save(review={'binding': {**self.binding, 'head_sha': 'other'}, 'verdict': 'PASS'})
        with self.assertRaises(Rejected): self.tools.merge_mr(self.binding)
        self.tools.save(review={'binding': self.binding, 'verdict': 'PASS'})
        self.tools.manifest = lambda ref=None: (copy.deepcopy(self.good), 'changed')
        with self.assertRaises(Rejected): self.tools.merge_mr(self.binding)
        self.assertEqual(self.calls, [])

    def test_exact_approved_head_merges_only_once(self):
        self.prepare_merge()
        self.assertEqual(self.tools.merge_mr(self.binding)['merge_commit_sha'], 'merge')
        self.assertEqual(self.calls[0][2]['sha'], 'head')
        with self.assertRaises(Rejected): self.tools.merge_mr(self.binding)
        self.assertEqual(len(self.calls), 1)

    def test_synthetic_decision_and_native_dispatch_receipt(self):
        sample = {'at': 1, 'status': 500, 'body': {'version': 'v2', 'error': 'KeyError', 'message': 'loyalty'}}
        result = classify(sample)
        self.assertTrue(result['synthetic'])
        self.assertEqual(result['answers']['verdict']['choice'], 'incident')
        self.assertEqual(classify({'status': 200})['answers']['verdict']['choice'], 'normal')
        task = {'id': 'task', 'contextId': 'context', 'status': {'state': 'TASK_STATE_COMPLETED'},
            'history': [{'messageId': 'message', 'parts': [{'text': 'Investigate'}]}]}
        row = {'request_id': 'classified-checkout-incident', 'message_id': 'message', 'task_id': 'task', 'content': 'Investigate', 'task': task}
        config = {'agents': {'investigator': 'specialist'}, 'contexts': {'investigator': 'context'}}
        trigger = {'at': 2, 'source': 'Synthetic decision', 'incident_samples': [{'sample': sample, 'result': result}]*3}
        handoff = incident_handoff(config, [row], trigger)
        self.assertTrue(handoff['policy']['matched'])
        self.assertEqual(handoff['delivery']['kind'], 'accepted')
        task['history'][0]['parts'][0]['text'] = 'Different message'
        self.assertEqual(incident_handoff(config, [row], trigger)['delivery']['kind'], 'unconfirmed')
