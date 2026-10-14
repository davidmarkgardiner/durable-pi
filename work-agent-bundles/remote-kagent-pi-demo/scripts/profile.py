"""Validate the deployment boundary before reading or writing connected systems."""
import json
import re
from pathlib import Path
from urllib.parse import urlparse


def load(path):
    profile = json.loads(Path(path).read_text())
    for key in ('kube_context', 'application_namespace', 'agent_namespace', 'seed_agent', 'model_config',
        'controller_service', 'runtime_image', 'healthy_image', 'regression_image', 'storage_class',
        'gitlab_api', 'url', 'gitlab_secret', 'gitlab_secret_key', 'run_id', 'git_read_secret'):
        value = profile.get(key)
        if not isinstance(value, str) or not value or 'REPLACE' in value or '.invalid' in value:
            raise ValueError('Provide a verified target value for '+key)
    if type(profile.get('project')) is not int or profile['project'] <= 0:
        raise ValueError('A verified exact GitLab project ID is required')
    for key in ('application_namespace', 'agent_namespace', 'seed_agent', 'controller_service', 'run_id', 'flux_namespace', 'flux_name', 'gitlab_secret', 'git_read_secret'):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,52}', profile[key]): raise ValueError('Invalid Kubernetes name: '+key)
    if len(profile['run_id']) > 35: raise ValueError('run_id must be at most 35 characters to leave room for resource suffixes')
    if type(profile.get('controller_port')) is not int or not 1 <= profile['controller_port'] <= 65535: raise ValueError('Invalid controller_port')
    if profile['target_branch'] != 'main': raise ValueError('This demonstration uses a dedicated main branch')
    if profile['application_namespace'] in ('default', 'kube-system', 'kagent', 'aks-istio-system'):
        raise ValueError('Use a dedicated synthetic application namespace')
    if profile.get('model_quota_verified') is not True:
        raise ValueError('Verify the approved model route and enforced usage allowance first; discovery alone is insufficient')
    for key in ('runtime_image', 'healthy_image', 'regression_image'):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/:@-]+', profile[key]): raise ValueError('Invalid image reference: '+key)
    if profile['healthy_image'] == profile['regression_image']:
        raise ValueError('Healthy and regression images must differ')
    for key in ('gitlab_api', 'url', 'bridge_url'):
        parsed = urlparse(profile[key])
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
            raise ValueError('Use a clean HTTP(S) URL for '+key)
    if not profile['gitlab_api'].rstrip('/').endswith('/api/v4'):
        raise ValueError('gitlab_api must address the GitLab v4 API')
    if profile['manifest_file'] != 'deploy/deployment.json':
        raise ValueError('This bundle limits rollback to deploy/deployment.json')
    return profile
