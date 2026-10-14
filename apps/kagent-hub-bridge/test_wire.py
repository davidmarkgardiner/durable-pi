import copy
import unittest
from wire import EXT, approval_binding, decision_summary, entries, jobs, number, snapshot, validate_decision, fixture_decision

class WireTest(unittest.TestCase):
    def state(self):
        task={'id':'native-task','contextId':'native-context','status':{'state':'TASK_STATE_INPUT_REQUIRED',
            'message':{'metadata':{EXT:{'type':'tool_approval_request','tools':[{'id':'tool-1','name':'publish_proposal','args':{'request':{'proposal_hash':'hash'}}}]}}}},
            'artifacts':[{'artifactId':'intent','parts':[{'data':{'id':'tool-1','name':'publish_proposal','args':{'request':{'proposal_hash':'hash'}}}}]},
                         {'artifactId':'blocked','parts':[{'data':{'id':'tool-1','name':'publish_proposal','response':{'error':'requires confirmation'}}}]}]}
        return {'phase':'awaiting_approval','roles':{'investigator':{'agent':'native-agent','context':'native-context','task_id':'native-task','task':task}},'review':{'verdict':'PASS'},'decision':None,'verification':None}
    def test_blocked_tool_is_not_a_completed_effect(self):
        state=self.state()
        self.assertEqual(len([e for e in entries(state,'investigator') if e['kind']=='pi.tool-result']),0)
        self.assertEqual(snapshot(state,'investigator')['tools'][0]['status'],'pending')
    def test_native_confirmation_id_is_distinct_from_tool_call_id(self):
        state=self.state()
        state["roles"]["investigator"]["task"]["status"]["message"]["metadata"][EXT]["tools"][0]["call_id"]="original-intent"
        self.assertEqual(snapshot(state,"investigator")["tools"][0]["callId"],"original-intent")
    def test_native_identity_and_proposal_visible(self):
        state=self.state()
        binding=entries(state,'investigator')[0]['data']
        self.assertEqual(binding['contextId'],'native-context')
        job=jobs(state)['items'][str(number('native-task'))]
        self.assertEqual(job['approval'],'pending')
        self.assertEqual(job['phases'][2]['status'],'pending')
        self.assertIn('proposal_hash',job['phases'][1]['steps'][0]['detail'])
    def test_review_must_finish_before_approval_is_offered(self):
        state=self.state();state['phase']='reviewing';state['review']=None
        self.assertNotIn('approval',jobs(state)['items'][str(number('native-task'))])
    def test_readback_completion_requires_independent_verification(self):
        state=self.state();state['decision']={'fixture':{'disposition':'approve'}};state['phase']='verifying'
        job=jobs(state)['items'][str(number('native-task'))]
        self.assertEqual(job['status'],'running')
        self.assertEqual(job['phases'][3]['status'],'pending')
        state['verification']={'effects':1};state['phase']='completed'
        self.assertEqual(jobs(state)['items'][str(number('native-task'))]['status'],'completed')
    def test_denial_skips_effect(self):
        state=self.state();state['decision']={'fixture':{'disposition':'deny'}};state['verification']={'effects':0}
        self.assertEqual(jobs(state)['items'][str(number('native-task'))]['phases'][2]['status'],'skipped')
    def proposal(self):
        state=self.state()
        binding={'op_id':'operation','revision':1,'proposal_hash':'hash','decision_id':'decision'}
        task=state['roles']['investigator']['task']
        task['status']['message']['metadata'][EXT]['tools'][0]['args']['request']=binding
        task['artifacts'] += [
            {'parts':[{'data':{'id':'record','name':'record_proposal','args':{'request':{
                'op_id':'operation','revision':1,'proposal':{'cause':'Missing required field',
                'change':'disable_feature','verification':'caller_without_field_succeeds'}}}}}]},
            {'parts':[{'data':{'id':'record','name':'record_proposal','response':{'output':binding.copy()}}}]}]
        return state
    def test_human_summary_describes_the_bound_recorded_proposal(self):
        state=self.proposal()
        decision=jobs(state)['items'][str(number('native-task'))]['decisionSummary']
        self.assertEqual(decision['proposalHash'],'hash')
        self.assertEqual(decision['operation'],'operation')
        self.assertIn('Disable the feature',decision['change'])
        self.assertIn('one synthetic effect',decision['approveEffect'])
    def test_summary_rejects_a_different_pending_proposal_hash(self):
        state=self.proposal()
        request=state['roles']['investigator']['task']['status']['message']['metadata'][EXT]
        request['tools'][0]['args']['request']['proposal_hash']='different'
        self.assertIsNone(decision_summary(state,request))
    def test_decision_requires_the_exact_displayed_native_approval(self):
        task=self.proposal()['roles']['investigator']['task']
        binding=copy.deepcopy(approval_binding(task))
        self.assertEqual(validate_decision({'approved':True,'binding':binding},task)['task_id'],'native-task')
        binding['request']['proposal_hash']='changed'
        with self.assertRaisesRegex(ValueError,'Displayed approval changed'):
            validate_decision({'approved':True,'binding':binding},task)
    def test_unbound_boolean_cannot_approve_a_native_task(self):
        task=self.proposal()['roles']['investigator']['task']
        with self.assertRaises(ValueError):
            validate_decision({'approved':True},task)
    def test_protobuf_integer_revision_is_normalized_without_changing_binding(self):
        body={'revision':1.0,'proposal_hash':'exact','expires_at':100.0,'decision_id':'saved'}
        normalized=fixture_decision(body)
        self.assertIs(type(normalized['revision']),int)
        self.assertEqual(normalized,{**body,'revision':1})
        for bad in (True,1.5,'1',0):
            with self.assertRaises(ValueError):
                fixture_decision({**body,'revision':bad})

if __name__=='__main__':unittest.main()
