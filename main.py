import argparse
from harness.agent import run_agent
from harness.approval import CliApproval
from harness.contracts import ToolCall
from harness.models import DemoModel, OpenAICompatibleModel
from harness.registry import Registry
from harness.tools import example_tools


DEMO_CASES = {
    'files': ('Show me the project files.', 'list_files', {}),
    'email': ('Email lead@company.com saying the bug is fixed.', 'send_email',
              {'to': 'lead@company.com', 'subject': 'Bug fixed', 'body': 'The bug is fixed.'}),
    'delete': ('Delete the temporary repository test-backend.', 'delete_repo',
               {'repo': 'test-backend'}),
    'draft': ('Draft an email saying the bug is fixed.', 'draft_email',
              {'to': 'lead@company.com', 'subject': 'Bug fixed', 'body': 'The bug is fixed.'}),
}


def main() -> int:
    parser = argparse.ArgumentParser(description='Governed agent runtime; all tools are simulated.')
    parser.add_argument('--case', choices=DEMO_CASES, default='files')
    parser.add_argument('--model', help='Optional OpenAI-compatible model identifier')
    parser.add_argument('--task', help='Free-text task; requires --model')
    parser.add_argument('--unattended', action='store_true')
    args = parser.parse_args()
    if bool(args.model) != bool(args.task):
        parser.error('--model and --task must be supplied together')

    # Assemble the runtime here; the agent does not create its dependencies.
    registry = Registry()
    for tool in example_tools():
        registry.register(tool)

    if args.model:
        try:
            from openai import OpenAI
        except ImportError:
            parser.error("Install the optional model dependency: pip install -e '.[live]'")
        model = OpenAICompatibleModel(OpenAI(timeout=30.0, max_retries=0), args.model)
        task = args.task
    else:
        task, name, arguments = DEMO_CASES[args.case]
        model = DemoModel(ToolCall('call_1', name, arguments))

    print(f'Task: {task}')
    result = run_agent(model, registry, CliApproval(), task, unattended=args.unattended)
    print(f'Answer: {result.answer}')
    print(f'Status: {result.status} | Model calls: {result.model_calls} | Tool calls: {result.tool_calls}')
    print(f'Model time: {result.model_seconds:.4f}s | Total time: {result.elapsed_seconds:.4f}s')
    for entry in result.audit:
        print(f'Audit: {entry.tool} -> {entry.outcome}')

    return 0 if result.status == 'finished' else 1


if __name__ == '__main__':
    raise SystemExit(main())
