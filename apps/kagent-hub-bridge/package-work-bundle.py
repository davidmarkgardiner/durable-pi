"""Copy only source, locked dependencies and UI assets into the work handoff."""
import ast
import shutil
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
source = Path(__file__).resolve().parent
bundle = repo/'work-agent-bundles/remote-kagent-pi-demo'
runtime = bundle/'runtime'
runtime.mkdir(parents=True, exist_ok=True)
for name in ('wire.py', 'chat.py', 'gitops.py'):
    shutil.copy2(source/name, runtime/name)
for name in ('application.py',):
    shutil.copy2(source/'gitops'/name, runtime/name)
text = (source/'gitops/mcp.py').read_text()
tree = ast.parse(text)
monitor = next(n for c in tree.body if isinstance(c, ast.ClassDef) and c.name == 'Rollback' for n in c.body if isinstance(n, ast.FunctionDef) and n.name == 'monitor')
lines = text.splitlines(keepends=True)
del lines[monitor.lineno-1:monitor.end_lineno]
text = ''.join(lines)
replacements = {
    "'https://gitlab.com/api/v4/projects/'": "self.config['gitlab_api'].rstrip('/')+'/projects/'",
    "'lumen-checkout:v1'": "self.config['healthy_image']",
    "'lumen-checkout:v2'": "self.config['regression_image']",
    "'agent/lumen-rollback-v1'": "self.config['rollback_branch']",
    "'deploy/deployment.json'": "self.config['manifest_file']",
    "'repository/files/deploy%2Fdeployment.json?ref='": "'repository/files/'+quote(self.config['manifest_file'], safe='')+'?ref='",
    "ref='main'": "ref=None",
    "quote(ref, safe='')": "quote(ref or self.config['target_branch'], safe='')",
    "'branch': 'main'": "'branch': self.config['target_branch']",
    "'target_branch': 'main'": "'target_branch': self.config['target_branch']",
    "'target_branch': 'main',": "'target_branch': self.config['target_branch'],",
    "mr['target_branch'] != 'main'": "mr['target_branch'] != self.config['target_branch']",
    "'ref': 'main'": "'ref': self.config['target_branch']",
    "'namespace': 'lumen-gitops'": "'namespace': self.config['application_namespace']",
    "'cluster': 'kind-pi-durable-local'": "'cluster': self.config['cluster_label']",
    "'/config/gitlab.token'": "'/gitlab/gitlab.token'",
    "'http://checkout.lumen-gitops.svc:8080/checkout'": "self.config['application_url'].rstrip('/')+'/checkout'",
    "'api/v1/namespaces/lumen-gitops/pods?labelSelector=app%3Dlumen-checkout'": "'api/v1/namespaces/'+self.config['application_namespace']+'/pods?labelSelector=app%3Dlumen-checkout'",
    "'api/v1/namespaces/lumen-gitops/pods/'": "'api/v1/namespaces/'+self.config['application_namespace']+'/pods/'",
    "'apis/apps/v1/namespaces/lumen-gitops/deployments/checkout'": "'apis/apps/v1/namespaces/'+self.config['application_namespace']+'/deployments/checkout'",
    "'apis/source.toolkit.fluxcd.io/v1/namespaces/flux-lumen/gitrepositories/lumen'": "'apis/source.toolkit.fluxcd.io/v1/namespaces/'+self.config['flux_namespace']+'/gitrepositories/'+self.config['flux_name']",
    "'apis/kustomize.toolkit.fluxcd.io/v1/namespaces/flux-lumen/kustomizations/lumen'": "'apis/kustomize.toolkit.fluxcd.io/v1/namespaces/'+self.config['flux_namespace']+'/kustomizations/'+self.config['flux_name']",
    "'branch': branch": "'branch': branch",
}
for old,new in replacements.items():
    text = text.replace(old,new)
# The portable entrypoint is tools.py. There is no Jev loop or key in this source.
text = text[:text.index("if __name__ == '__main__':")]
text = text.replace("'synthetic guest'", "'synthetic guest'")
text = text.replace("and deployment['image'] == self.config['healthy_image']", "and source.get('status', {}).get('artifact', {}).get('revision') == applied\n            and deployment['status'].get('replicas') == deployment['status'].get('updatedReplicas') == 1\n            and deployment['image'] == self.config['healthy_image']")
ast.parse(text)
(runtime/'rollback.py').write_text(text.rstrip()+'\n')
fixture = Path('/Users/davidgardiner/Desktop/repo/kagent-public-worktrees/pi-durable-fixture/work-agent-bundles/pi-durable-comparison-fixture/showcase')
shutil.copytree(fixture/'proto', runtime/'proto', dirs_exist_ok=True)
for proto in (runtime/'proto').rglob('*.proto'):
    proto.write_text('\n'.join(line.rstrip() for line in proto.read_text().splitlines())+'\n')
(runtime/'requirements.lock').write_text((fixture/'requirements.txt').read_text()+'typing-extensions==4.16.0\nsetuptools==84.0.0\n')
# Keep the runtime labels and exact scope tied to its supplied work profile.
path = runtime/'gitops.py'
text = path.read_text().replace("'scope': 'Only the private Lumen demo repository and lumen-gitops namespace in kind-pi-durable-local.'",
    "'scope': 'Only the configured demo repository and namespace '+self.config['application_namespace']+' in '+self.config['cluster_label']")
text = text.replace("'change': 'deploy/deployment.json: lumen-checkout:v2 → lumen-checkout:v1'",
    "'change': self.config['manifest_file']+': '+self.config['regression_image']+' → '+self.config['healthy_image']")
text = text.replace("'url': self.config['url']", "'url': self.config['url']")
path.write_text(text)
path = runtime/'chat.py'
text = path.read_text().replace("'kimi-for-coding'", "self.config.get('model_id', 'work-model')")
text = text.replace('Live Kimi', 'Configured work model').replace('Read-only synthetic incident tools.', 'Scoped application and repository tools.')
path.write_text(text)
path = runtime/'gitops.py'
path.write_text(path.read_text().replace('Live Kimi native kagent', 'Configured work model on native kagent').replace('Use Live Kimi chat for new instructions', 'Start a separate workspace for new instructions'))
ui = bundle/'ui'
for folder in ('apps/dpi-sdk/src', 'apps/dpi-playground/apps/dpi-playground-fe/src',
    'apps/dpi-playground/apps/dpi-playground-fe/public', 'apps/dpi-playground/apps/dpi-playground-hub/src'):
    shutil.copytree(repo/folder, ui/folder, dirs_exist_ok=True)
for name in ('apps/dpi-sdk/package.json','apps/dpi-sdk/package-lock.json', 'apps/dpi-sdk/tsconfig.json',
    'apps/dpi-playground/package.json','apps/dpi-playground/package-lock.json',
    'apps/dpi-playground/apps/dpi-playground-fe/package.json','apps/dpi-playground/apps/dpi-playground-fe/tsconfig.json',
    'apps/dpi-playground/apps/dpi-playground-fe/vite.config.ts','apps/dpi-playground/apps/dpi-playground-fe/index.html',
    'apps/dpi-playground/apps/dpi-playground-hub/package.json','apps/dpi-playground/apps/dpi-playground-hub/tsconfig.json'):
    if (repo/name).exists():
        target = ui/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,target)
hub = ui/'apps/dpi-playground/apps/dpi-playground-hub/src/main.ts'
hub.write_text(hub.read_text().replace('new NetworkRegistry()', 'new NetworkRegistry(process.env.DPI_REGISTRY_PATH)'))
for name in ('LICENSE', 'LICENSE.md'):
    if (repo/name).exists(): shutil.copy2(repo/name,bundle/'DURABLE-PI-LICENSE')
(bundle/'PROVENANCE.md').write_text('''# Source provenance

Pi UI and SDK source are a snapshot of durable-pi, upstream https://github.com/disler/durable-pi at baseline aa8bf021c112eac2d498e5757d4315559df8ab80 plus the current native integration changes. File checksums describe the actual bundled overlay, not a published upstream commit.

Runtime chat, task/approval translation, GitOps workflow and rollback service come from the verified local adapter. The portable rollback service removes the Jev monitor and parameterizes repository, image, cluster and namespace scope. Synthetic classification is implemented separately in classifier.py.

Protobuf definitions come from the sanitized pi-durable-comparison-fixture showcase shim. They implement kagent.api.v1alpha1 and lf.a2a.v1, tested against native kagent 1.0.0-alpha11. The shim uses proto3-compatible syntax. Do not assume these APIs exist on kagent 0.x. Runtime packages are locked to grpcio/grpcio-tools 1.78.0 and protobuf 6.33.5.

No runtime configuration, kubeconfig, token, Secret manifest, home-lab database, native context or captured customer data is copied into this bundle.
''')
print(bundle)
