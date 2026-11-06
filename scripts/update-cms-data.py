#!/usr/bin/env python3
"""Move pkgs/cms-data.json, the cms-data of the standard sequences, to the
versions cmsdist builds another release with.

    scripts/update-cms-data.py <cmsdist ref> [<Subsystem>/<Package> ...]

The ref names the cmsdist branch or tag whose data/cmsswdata.txt gives the
versions: IB/CMSSW_20_1_X/master for the head of a release cycle, or
REL/CMSSW_20_1_0_pre4/el9_amd64_gcc14 for one release. Every repository in
the file is moved to the version listed there and its hash recomputed (nix
flake prefetch downloads it); repositories named on the command line are
added. The list itself is this flake's choice - what the jobs it supports
read - not cmsdist's, which has some 150.
"""
import json
import os
import subprocess
import sys
import urllib.request

JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pkgs", "cms-data.json")


def cmsdist_versions(ref):
    url = f"https://raw.githubusercontent.com/cms-sw/cmsdist/{ref}/data/cmsswdata.txt"
    with urllib.request.urlopen(url) as f:
        text = f.read().decode()
    versions = {}
    for line in text.splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            repo, tag = line.split("=", 1)
            versions[repo.strip()] = tag.strip()
    return versions


def prefetch(repo, tag):
    out = subprocess.run(["nix", "flake", "prefetch", "--json", f"github:cms-data/{repo}/{tag}"],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)["hash"]


def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith("-"):
        sys.exit(__doc__)
    ref, added = sys.argv[1], sys.argv[2:]
    with open(JSON) as f:
        data = json.load(f)
    versions = cmsdist_versions(ref)
    for path in sorted(set(data) | set(added)):
        repo = path.replace("/", "-")
        if repo not in versions:
            sys.exit(f"{path}: not in cmsdist's data/cmsswdata.txt at {ref}")
        tag = versions[repo]
        if data.get(path, {}).get("tag") == tag:
            continue
        print(f"{path}: {data.get(path, {}).get('tag', '(new)')} -> {tag}")
        data[path] = {"tag": tag, "hash": prefetch(repo, tag)}
    with open(JSON, "w") as f:
        json.dump(dict(sorted(data.items())), f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
