"""Run a loopback-only port-forward or the isolated Pi UI on this workstation."""
import argparse
import json
import os
import subprocess
from pathlib import Path
from profile import load

parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['port-forward', 'ui'])
parser.add_argument('--profile', required=True)
parser.add_argument('--state', type=Path, required=True)
parser.add_argument('--port', type=int)
args = parser.parse_args()
p = load(args.profile)
if args.action == 'port-forward':
    raise SystemExit(subprocess.call(['kubectl', '--context', p['kube_context'], '-n', p['agent_namespace'],
        'port-forward', 'svc/'+p['run_id']+'-bridge', str(args.port or 4798)+':8080', '--address=127.0.0.1']))
state = args.state.resolve()
if not (state/'bridge.token').is_file(): raise SystemExit('Missing private bridge token from render step')
network = state/'dpi-network.yaml'
network.write_text('devices:\n  work-kagent:\n    kind: url\n    name: Remote work kagent\n    url: '+json.dumps(p['bridge_url'])+'\n    token_env: PI_WORK_BRIDGE_TOKEN\n')
os.chmod(network, 0o600)
env = {**os.environ, 'PI_WORK_BRIDGE_TOKEN': (state/'bridge.token').read_text().strip(),
    'DPI_NETWORK_FILE': str(network), 'DPI_REGISTRY_PATH': str(state/'network.sqlite'),
    'DPI_HUB_HOST': '127.0.0.1', 'DPI_HUB_PORT': str(args.port or 4781)}
root = Path(__file__).resolve().parents[1]/'ui/apps/dpi-playground'
raise SystemExit(subprocess.call(['npm', 'start'], cwd=root, env=env))
