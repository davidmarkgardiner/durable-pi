"""Allocate a Git worktree and a Pi session for one queue job."""
import json
from pathlib import Path
import subprocess
import urllib.parse
import urllib.request

from handoff_transport import connection


def git(repo, *arguments):
    return subprocess.check_output(["git", "-C", str(repo), *arguments], text=True).strip()


def freeze(target):
    target = dict(target)
    if target.get("repo"):
        target["base_commit"] = git(target["repo"], "rev-parse", "--verify", str(target.get("base_ref", "HEAD")) + "^{commit}")
    return target


def prepare(target, job_id, directory):
    if not target.get("repo"):
        return target
    repo = Path(target["repo"]).resolve()
    worktree = Path(target["worktree_root"]).resolve() / job_id
    branch = "queue/" + job_id
    worktree.parent.mkdir(parents=True, exist_ok=True)
    if not worktree.exists():
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "-b", branch, str(worktree), target["base_commit"]], check=True, stdout=subprocess.DEVNULL)
    if git(worktree, "rev-parse", "--path-format=absolute", "--git-common-dir") != git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir") or git(worktree, "branch", "--show-current") != branch:
        raise ValueError("Existing worktree does not belong to this job")
    subprocess.run(["git", "-C", str(worktree), "merge-base", "--is-ancestor", target["base_commit"], "HEAD"], check=True)
    base, headers = connection(target["backend"], target["device"], target["backend_env"])

    def call(route, body=None, method=None):
        request = urllib.request.Request(base + route, data=None if body is None else json.dumps(body).encode(), headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    name = "Queue · " + job_id
    sessions = [session for session in call("/sessions") if session["name"] == name]
    if len(sessions) > 1:
        raise ValueError("Multiple sessions match this job; refusing to choose one")
    session = sessions[0] if sessions else call("/sessions", {"name": name, "cwd": str(worktree), "model": target["model"]})
    if session["cwd"] != str(worktree):
        raise ValueError("Job session has the wrong working directory")
    route = "/sessions/" + urllib.parse.quote(session["id"], safe="") + "/agents"
    reviewers = [agent for agent in call(route) if agent["name"] == "Read-only Reviewer"]
    if len(reviewers) > 1:
        raise ValueError("Multiple reviewers match this job")
    reviewer = reviewers[0] if reviewers else call(route, {"name": "Read-only Reviewer", "from": 1})
    call(route + "/1", {"name": "Investigator / Builder"}, "PATCH")
    call(route + "/1/config", {"instructions": "Work only in this job's working directory. Plan, implement and test bounded synthetic changes. Preserve original evidence. No credentials, external services, merge, deployment or spawning agents. Prepare a handoff for the named reviewer."}, "PATCH")
    call(route + "/" + str(reviewer["id"]) + "/config", {"readOnly": True, "instructions": "Independently review this job's plan, source, diff and recorded checks. Use only read-only tools. Do not execute shell commands, write, change App State, approve, deploy or spawn. Report evidence and limitations."}, "PATCH")
    result = {**target, "session": session["id"], "investigator": 1, "reviewer": reviewer["id"], "incident": "job-" + job_id, "worktree": str(worktree), "branch": branch}
    temporary = directory / "resources.tmp"
    temporary.write_text(json.dumps(result, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(directory / "resources.json")
    return result
