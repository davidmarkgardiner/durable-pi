"""Package original demo sources and the small container seed adjustments."""
import shutil
import tarfile
from pathlib import Path

root=Path(__file__).resolve().parent
source=root.parent/'proactive-dpi-demo'
build=root/'.data/build'
build.mkdir(parents=True,exist_ok=True)
for name in ['Dockerfile','bridge.py','wire.py','chat.py','gitops.py','deploy.py']:
    shutil.copy2(root/name,build/name)
for name in ['shared','scripts','mock-repo-template','apps/proactive-dpi-logs']:
    shutil.copytree(source/name,build/'demo'/name,dirs_exist_ok=True)
seed=build/'demo/scripts/reset.ts'
text=seed.read_text().replace('cpSync, existsSync, mkdirSync, readFileSync, rmSync',
                            'cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync')
text=text.replace('execFileSync("npm", ["test", "--silent"]','execFileSync("node", ["--test"]')
for folder in ['dataDir','workspaceDir']:
    text=text.replace('rmSync('+folder+', { recursive: true, force: true });',
                      'for (const name of readdirSync('+folder+')) rmSync(join('+folder+', name), { recursive: true, force: true });')
seed.write_text(text)
with tarfile.open(root/'.data/build.tar.gz','w:gz') as archive:
    for path in sorted(build.rglob('*')):
        if path.is_file():archive.add(path,arcname=str(path.relative_to(build)))
print(root/'.data/build.tar.gz')
