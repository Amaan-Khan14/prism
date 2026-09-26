"""Rebuild the synthetic Git branches, PR patches, and measured LCOV reports.

Requires only Python 3.9+ and Git. The local worktree is disposable; tracked
artifacts contain the exact base/head SHAs and can be regenerated at any time.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import trace
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WORK = ROOT / ".work"
REPO = WORK / "repo"
ARTIFACTS = ROOT / "artifacts"


def run(*args, cwd=REPO, env=None, check=True):
    result = subprocess.run(
        args, cwd=str(cwd), env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise RuntimeError("{} failed:\n{}".format(" ".join(args), result.stderr))
    return result


def git(*args, env=None):
    return run("git", "-c", "commit.gpgsign=false", *args, env=env).stdout.strip()


def commit(message, ordinal):
    stamp = "2026-09-27T{:02d}:00:00+00:00".format(ordinal)
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp,
        "GIT_AUTHOR_NAME": "PRism Corpus", "GIT_COMMITTER_NAME": "PRism Corpus",
        "GIT_AUTHOR_EMAIL": "corpus@example.invalid",
        "GIT_COMMITTER_EMAIL": "corpus@example.invalid",
    })
    git("add", "-A")
    git("commit", "-q", "-m", message, env=env)
    return git("rev-parse", "HEAD")


def copy_tree(source, target):
    for path in sorted(source.rglob("*")):
        if path.is_file():
            destination = target / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)


def coverage_for(case_id, head_sha, target):
    counts_file = WORK / (case_id + ".counts.json")
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = run(
        sys.executable, str(ROOT / "coverage_runner.py"), str(REPO), str(counts_file),
        env=env, check=False,
    )
    if not counts_file.exists():
        raise RuntimeError("Trace did not produce counts for " + case_id + ": " + result.stderr)
    measured = json.loads(counts_file.read_text(encoding="utf-8"))
    records = ["TN:" + case_id]
    for source in sorted((REPO / "src" / "shop").glob("*.py")):
        executable = trace._find_executable_linenos(str(source))
        if not executable:
            continue
        records.append("SF:" + source.relative_to(REPO).as_posix())
        for line in sorted(executable):
            path = source.relative_to(REPO).as_posix()
            records.append("DA:{},{}".format(line, measured.get(path, {}).get(str(line), 0)))
        records.append("end_of_record")
    raw = ("\n".join(records) + "\n").encode("utf-8")
    (target / "coverage.lcov").write_bytes(raw)
    metadata = {
        "format": "lcov",
        "source": "local_python_trace",
        "commit_sha": head_sha,
        "run_id": "local-" + case_id + "-" + head_sha[:12],
        "artifact_sha256": hashlib.sha256(raw).hexdigest(),
        "test_exit_code": result.returncode,
        "test_output": (result.stdout + result.stderr).strip(),
        "trust_note": "Local measured fixture. A hosted coverage upload requires a trusted GitHub Actions OIDC workflow for this exact head SHA.",
    }
    (target / "coverage.metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return metadata


def main():
    source = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    old_remote = None
    if (REPO / ".git").exists():
        current = run("git", "remote", "get-url", "origin", check=False)
        if current.returncode == 0:
            old_remote = current.stdout.strip()
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.rmtree(ARTIFACTS, ignore_errors=True)
    REPO.mkdir(parents=True)
    ARTIFACTS.mkdir()
    git("init", "-q", "--initial-branch=main", "--object-format=sha1")
    if old_remote:
        git("remote", "add", "origin", old_remote)
    copy_tree(ROOT / "base", REPO)
    base_sha = commit("Base synthetic shop", 1)
    output = {
        "repository": source["repository"],
        "disclosure": source["disclosure"],
        "base_branch": "main",
        "base_sha": base_sha,
        "cases": [],
    }
    for ordinal, case in enumerate(source["cases"], start=2):
        case_id = case["id"]
        branch = "case/" + case_id
        git("checkout", "-q", "main")
        git("checkout", "-q", "-b", branch)
        copy_tree(ROOT / "cases" / case_id, REPO)
        head_sha = commit(case["title"], ordinal)
        target = ARTIFACTS / case_id
        target.mkdir()
        (target / "pr.patch").write_text(
            git("diff", "--binary", "main...HEAD") + "\n", encoding="utf-8"
        )
        issue = dict(case["expected_issue"])
        lines = (REPO / issue["citation_file"]).read_text(encoding="utf-8").splitlines()
        anchor = issue.pop("citation_anchor")
        matches = [i for i, line in enumerate(lines, 1) if line.strip() == anchor]
        if len(matches) != 1:
            raise RuntimeError("Expected one unique citation anchor for " + case_id)
        issue["citation_line"] = matches[0]
        body = (
            "# " + case["title"] + "\n\n"
            "Synthetic PRism benchmark case.\n\n"
            "## Specification\n\n" + case["spec"] + "\n\n"
            "## Proposed change\n\n" + case["change"] + "\n"
        )
        (target / "pr_body.md").write_text(body, encoding="utf-8")
        coverage = coverage_for(case_id, head_sha, target)
        output["cases"].append({
            "id": case_id,
            "title": case["title"],
            "branch": branch,
            "github_pr_url": case.get("github_pr_url"),
            "base_sha": base_sha,
            "head_sha": head_sha,
            "patch": "artifacts/" + case_id + "/pr.patch",
            "pr_body": "artifacts/" + case_id + "/pr_body.md",
            "coverage": "artifacts/" + case_id + "/coverage.lcov",
            "coverage_metadata": "artifacts/" + case_id + "/coverage.metadata.json",
            "spec": case["spec"],
            "expected_issue": issue,
            "reproduction": case["reproduction"],
            "test_exit_code": coverage["test_exit_code"],
        })
    (ARTIFACTS / "manifest.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print("Built {} authored PR cases from base {}".format(len(output["cases"]), base_sha))
    for case in output["cases"]:
        print("{} {} tests={}".format(case["id"], case["head_sha"], case["test_exit_code"]))


if __name__ == "__main__":
    main()
