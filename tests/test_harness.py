import unittest
from types import SimpleNamespace as NS
from harness.agent import run_agent
from harness.approval import CliApproval
from harness.contracts import ModelResponse, Permission, Tool, ToolCall, ToolSpec
from harness.models import DemoModel, OpenAICompatibleModel, ScriptedModel
from harness.registry import Registry
from harness.tools import example_tools, schema


class Gate:
    def __init__(self, approved=False):
        self.approved = approved
        self.calls = []

    def ask(self, call, permission):
        self.calls.append((call, permission))
        return self.approved


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.reg = Registry()
        for tool in example_tools():
            self.reg.register(tool)
        self.email = {'to': 'lead@company.com', 'subject': 'Bug fixed', 'body': 'Fixed.'}

    def execute(self, name, args, gate=None, **kwargs):
        return run_agent(DemoModel(ToolCall('c1', name, args)), self.reg,
                         gate or Gate(), 'test', **kwargs)

    def test_read(self):
        gate = Gate()
        r = self.execute('list_files', {}, gate)
        self.assertIn('README.md', r.answer)
        self.assertEqual((r.model_calls, r.tool_calls), (2, 1))
        self.assertEqual(gate.calls, [])
        self.assertEqual(r.audit[0].outcome, 'ran')

    def test_approved_email(self):
        r = self.execute('send_email', self.email, Gate(True))
        self.assertIn('[SIMULATED SEND]', r.answer)
        self.assertEqual([a.outcome for a in r.audit], ['approved', 'ran'])

    def test_denied_delete(self):
        gate = Gate()
        r = self.execute('delete_repo', {'repo': 'test-backend'}, gate)
        self.assertEqual(r.answer, 'denied by human')
        self.assertEqual(gate.calls[0][1], Permission.DANGEROUS)
        self.assertEqual([a.outcome for a in r.audit], ['denied'])

    def test_draft_never_calls_commit(self):
        commits = []
        self.reg.register(Tool(ToolSpec('draft_test', 'draft', schema()), Permission.DRAFT_ONLY,
                               handler=lambda a: commits.append(a), draft_handler=lambda a: 'draft'))
        r = self.execute('draft_test', {})
        self.assertEqual(r.answer, 'draft')
        self.assertEqual(commits, [])
        self.assertEqual(r.audit[0].outcome, 'drafted')

    def test_missing(self):
        r = self.execute('send_email', {'to': 'x'})
        self.assertIn('missing required arg', r.answer)
        self.assertEqual(r.audit[0].outcome, 'invalid')

    def test_wrong_type(self):
        r = self.execute('send_email', dict(self.email, to=123))
        self.assertIn('must be a string', r.answer)

    def test_extra(self):
        self.assertIn('unexpected arg', self.execute('list_files', {'x': 'y'}).answer)

    def test_non_object(self):
        self.assertIn('JSON object', self.execute('list_files', None).answer)

    def test_empty(self):
        self.assertIn('must not be empty', self.execute('send_email', dict(self.email, body=' ')).answer)

    def test_unknown(self):
        self.assertIn('unknown tool', self.execute('made_up', {}).answer)

    def test_forbidden(self):
        self.reg.register(Tool(ToolSpec('secret', 'secret', schema()), Permission.FORBIDDEN))
        self.assertNotIn('secret', [s.name for s in self.reg.specs_for_model()])
        self.assertEqual(self.execute('secret', {}).audit[0].outcome, 'blocked')

    def test_unattended(self):
        self.assertNotIn('send_email', [s.name for s in self.reg.specs_for_model(True)])
        gate = Gate(True)
        r = self.execute('send_email', self.email, gate, unattended=True)
        self.assertEqual(r.audit[0].outcome, 'blocked')
        self.assertEqual(gate.calls, [])

    def test_step_budget(self):
        r = self.execute('list_files', {}, max_steps=1)
        self.assertEqual(r.status, 'step_limit')

    def test_tool_budget(self):
        model = ScriptedModel([ModelResponse(tool_calls=[ToolCall('a', 'list_files', {}), ToolCall('b', 'list_files', {})])])
        r = run_agent(model, self.reg, Gate(), 'test', max_tool_calls=1)
        self.assertEqual((r.status, r.tool_calls), ('tool_limit', 0))

    def test_duplicate_ids(self):
        call = ToolCall('a', 'list_files', {})
        r = run_agent(ScriptedModel([ModelResponse(tool_calls=[call, call])]), self.reg, Gate(), 'test')
        self.assertEqual((r.status, r.tool_calls), ('protocol_error', 0))

    def test_repeated_id_across_steps(self):
        call = ToolCall('a', 'list_files', {})
        r = run_agent(ScriptedModel([ModelResponse(tool_calls=[call]), ModelResponse(tool_calls=[call])]), self.reg, Gate(), 'test')
        self.assertEqual((r.status, r.tool_calls), ('protocol_error', 1))

    def test_handler_error(self):
        def fail(args):
            raise RuntimeError('secret')
        self.reg.register(Tool(ToolSpec('fail', 'fail', schema()), Permission.READ_ONLY, handler=fail))
        r = self.execute('fail', {})
        self.assertIn('tool failed', r.answer)
        self.assertNotIn('secret', r.answer)
        self.assertEqual(r.audit[0].outcome, 'handler_error')

    def test_model_error(self):
        r = run_agent(ScriptedModel([]), self.reg, Gate(), 'test')
        self.assertEqual(r.status, 'model_error')

    def test_audit_isolated(self):
        self.execute('list_files', {})
        self.assertEqual(len(self.execute('list_files', {}).audit), 1)

    def test_exact_confirmation(self):
        gate = CliApproval(lambda _: 'anything')
        self.assertFalse(gate.ask(ToolCall('a', 'send_email', self.email), Permission.APPROVAL_REQUIRED))
        self.assertFalse(gate.ask(ToolCall('b', 'delete_repo', {'repo': 'x'}), Permission.DANGEROUS))

    def test_duplicate_registration(self):
        with self.assertRaises(ValueError):
            self.reg.register(example_tools()[0])

    def test_adapter_round_trip(self):
        requests = []
        def create(**kwargs):
            requests.append(kwargs)
            if len(requests) == 1:
                msg = NS(content=None, tool_calls=[NS(id='c1', function=NS(name='list_files', arguments='{}'))])
            else:
                msg = NS(content='Three files.', tool_calls=None)
            return NS(choices=[NS(message=msg)])
        client = NS(chat=NS(completions=NS(create=create)))
        r = run_agent(OpenAICompatibleModel(client, 'fake'), self.reg, Gate(), 'list')
        self.assertEqual(r.answer, 'Three files.')
        self.assertIn('parameters', requests[0]['tools'][0]['function'])
        self.assertEqual(requests[1]['messages'][1]['tool_calls'][0]['id'], 'c1')
        self.assertEqual(requests[1]['messages'][2]['tool_call_id'], 'c1')

    def test_adapter_invalid_json(self):
        requests = []
        def create(**kwargs):
            requests.append(kwargs)
            if len(requests) == 1:
                msg = NS(content=None, tool_calls=[NS(id='c1', function=NS(name='list_files', arguments='{bad'))])
            else:
                msg = NS(content='Invalid arguments.', tool_calls=None)
            return NS(choices=[NS(message=msg)])
        client = NS(chat=NS(completions=NS(create=create)))
        r = run_agent(OpenAICompatibleModel(client, 'fake'), self.reg, Gate(), 'list')
        self.assertEqual(r.audit[0].outcome, 'invalid')
        self.assertEqual(requests[1]['messages'][1]['tool_calls'][0]['function']['arguments'], '{bad')


    def test_uncertain_failure_stops_batch(self):
        actions = []

        def fail(args):
            actions.append('attempted')
            raise RuntimeError('failure after possible commit')

        self.reg.register(Tool(
            ToolSpec('fail_write', 'write', schema()),
            Permission.APPROVAL_REQUIRED,
            handler=fail,
        ))
        model = ScriptedModel([
            ModelResponse(tool_calls=[
                ToolCall('a', 'fail_write', {}),
                ToolCall('b', 'list_files', {}),
            ]),
            ModelResponse(tool_calls=[ToolCall('c', 'fail_write', {})]),
        ])
        result = run_agent(model, self.reg, Gate(True), 'test')
        self.assertEqual(result.status, 'tool_error')
        self.assertEqual((result.model_calls, result.tool_calls), (1, 1))
        self.assertEqual(actions, ['attempted'])
        self.assertEqual([a.outcome for a in result.audit], [
            'approved', 'handler_error', 'skipped_after_error',
        ])

    def test_unserializable_output_stops_run(self):
        self.reg.register(Tool(
            ToolSpec('bad_output', 'bad output', schema()),
            Permission.READ_ONLY,
            handler=lambda args: object(),
        ))
        result = self.execute('bad_output', {})
        self.assertEqual(result.status, 'tool_error')
        self.assertEqual([a.outcome for a in result.audit], ['ran', 'output_error'])

    def test_unsupported_schema_rejected(self):
        bad_schema = dict(schema('x'), minProperties=2)
        with self.assertRaises(ValueError):
            self.reg.register(Tool(
                ToolSpec('bad_schema', 'bad', bad_schema),
                Permission.READ_ONLY,
                handler=lambda args: None,
            ))

    def test_draft_requires_handler(self):
        with self.assertRaises(ValueError):
            self.reg.register(Tool(
                ToolSpec('unsafe_draft', 'draft', schema()),
                Permission.DRAFT_ONLY,
                handler=lambda args: None,
            ))


if __name__ == '__main__':
    unittest.main()
