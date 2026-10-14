"""Portable, scoped real tools with a clearly synthetic classifier."""
import json
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

from classifier import LABEL, classify
from rollback import Rollback, Handler, Rejected


class WorkTools(Rollback):
    def start_demo(self):
        with self.lock:
            state = self.state()
            if state.get('regression_commit'):
                return state
            if state.get('starting'):
                raise Rejected('Fault commit outcome needs independent reconciliation; no automatic retry')
            probes = [self.probe() for _ in range(3)]
            deployment = self.read_deployment({})
            manifest, base_sha = self.manifest()
            if not all(p['status'] == 200 and p['body'].get('version') == 'v1' for p in probes):
                raise Rejected('Three healthy checkout probes are required before fault injection')
            if deployment['image'] != self.config['healthy_image'] or manifest['spec']['template']['spec']['containers'][0]['image'] != self.config['healthy_image']:
                raise Rejected('Cluster and main are not at the configured healthy image')
            self.save(starting=True, baseline={'probes': probes, 'deployment': deployment, 'sha': base_sha})
            manifest['spec']['template']['spec']['containers'][0]['image'] = self.config['regression_image']
            commit = self.api('repository/commits', 'POST', {'branch': self.config['target_branch'],
                'commit_message': 'Synthetic demo fault '+self.config['workspace_id'], 'actions': [{'action': 'update',
                    'file_path': self.config['manifest_file'], 'last_commit_id': base_sha, 'content': json.dumps(manifest, indent=2)+'\n'}]})
            return self.save(starting=False, armed=True, armed_at=time.time(), regression_commit=commit['id'], phase='monitoring')

    def control(self, body):
        if body.get('action') == 'start_demo':
            if set(body) != {'action'}:
                raise Rejected('No arbitrary parameters are allowed for the demo fault')
            return self.start_demo()
        return super().control(body)

    def monitor(self):
        while True:
            try:
                state = self.state()
                if state.get('armed') and not state.get('trigger') and time.time()-state.get('armed_at', 0) > 600:
                    self.save(armed=False, monitor_error='Ten-minute regression observation deadline exceeded. Inspect Flux and application; no autonomous reset.')
                elif state.get('armed') and not state.get('trigger') and state['calls'] < 12:
                    sample = self.probe()
                    if sample['body'].get('version') != 'v2':
                        self.save(waiting_for_regression=True, last_probe=sample)
                        time.sleep(5)
                        continue
                    result = classify(sample)
                    classified = state['classifications']+[{'sample': sample, 'result': result}]
                    patch = {'classifications': classified, 'samples': (state['samples']+[sample])[-20:],
                        'calls': state['calls']+1, 'waiting_for_regression': False, 'monitor_error': None, 'classifier_mode': 'synthetic'}
                    last = classified[-3:]
                    if len(last) == 3 and all(c['result']['answers']['verdict']['choice'] == 'incident' for c in last):
                        patch.update(trigger={'at': time.time(), 'source': LABEL, 'incident_samples': last}, phase='incident')
                    self.save(**patch)
            except Exception as error:
                self.save(monitor_error=type(error).__name__+': '+str(error)[:150])
            time.sleep(5)


if __name__ == '__main__':
    config = json.loads(Path('/config/config.json').read_text())
    server = ThreadingHTTPServer(('0.0.0.0', 8080), Handler)
    server.config, server.backend = config, WorkTools(config)
    threading.Thread(target=server.backend.monitor, daemon=True).start()
    server.serve_forever()
