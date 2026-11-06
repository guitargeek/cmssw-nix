"""Rank what holds CMSSW packages back from a release build.

A package's library can be built when no package in its dependency closure
needs an external tool the build does not provide. This collects, for every
package in the source tree, the set of missing tools behind it (its
"blockers"), and reports:

  * packages that could build already but are not in the configuration
    (gains for free, modulo compile fixes),
  * the blocker sets, by how many packages each one alone holds back,
  * per missing tool, how many packages it blocks alone and in total.

Tools count as provided when gen/CMakeLists.txt defines them (unconditionally,
or under one of the CMSSW_WITH_* switches given with --with), or when a
package in the configuration uses them already. Package dependencies are read
as gen/buildfile_model.py models them. Only libraries are considered: a
package counts as gained with or without its plugins; missing tools that only
its plugins need are listed separately.

Usage:
  python3 gen/rank_blockers.py --src <cmssw source> --config gen/config.yml \\
      --with CMSSW_WITH_GEANT4 CMSSW_WITH_CORAL ... [--why Some/Package]

The switches a release is built with are in its configure phase, e.g.
  nix eval --raw .#packages.<system>.cmssw.configurePhase \\
      | grep -o 'CMSSW_WITH_[A-Z0-9_]*' | sort -u
"""
import argparse
import os
import re
from collections import Counter, defaultdict, deque

import yaml

import buildfile_model

parser = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--src", required=True, help="path to the CMSSW source tree")
parser.add_argument("--config", required=True, help="the release's build configuration")
parser.add_argument("--cmake", default=os.path.join(os.path.dirname(__file__), "CMakeLists.txt"),
                    help="top-level CMakeLists.txt that defines the tools")
parser.add_argument("--with", dest="switches", nargs="*", default=[],
                    help="CMSSW_WITH_* switches the release is configured with")
parser.add_argument("--why", nargs="*", default=[],
                    help="packages to explain: which dependency brings in which missing tool")
parser.add_argument("--top", type=int, default=25, help="number of blocker sets to list")
args = parser.parse_args()
SRC = args.src
CORE, PLUGINS = ("", "src"), ("plugins",)

# --- tools provided -------------------------------------------------------

def provided_tools(cmake, switches):
    """Tool names gen/CMakeLists.txt defines, given the enabled switches."""
    tools, stack, loops = set(), [], []
    name = r"([A-Za-z0-9_+-]+?|\$\{_\w+\})_(?:LIBRARIES|INCLUDE_DIRECTORIES)\b"
    lines, pending = [], ""
    for line in open(cmake):
        line = pending + " " + line.split("#", 1)[0].strip() if pending else line.split("#", 1)[0].strip()
        if line.startswith("foreach") and ")" not in line:
            pending = line  # a foreach list spanning several lines
            continue
        pending = ""
        lines.append(line)
    for line in lines:
        m = re.match(r"(if|elseif)\s*\((.*)\)", line)
        if m:
            if m.group(1) == "elseif" and stack: stack.pop()
            sw = re.findall(r"CMSSW_WITH_\w+", m.group(2))
            stack.append(all(s in switches for s in sw))
            continue
        if line.startswith("else"):
            continue
        if line.startswith("endif"):
            if stack: stack.pop()
            continue
        m = re.match(r"foreach\s*\((\w+)\s+(?:IN\s+ITEMS\s+)?(.*)", line)
        if m:
            loops.append((m.group(1), m.group(2).rstrip(")").split()))
            continue
        if line.startswith("endforeach"):
            if loops: loops.pop()
            continue
        if not all(stack):
            continue
        for t in re.findall(r"(?:set|find_library|find_path)\s*\(\s*" + name, line):
            m = re.fullmatch(r"\$\{(\w+)\}", t)
            if m:  # set(${_t}_LIBRARIES ...) inside a foreach
                for var, items in loops:
                    if var == m.group(1): tools.update(items)
            else:
                tools.add(t)
    return tools

def all_packages(src):
    out = []
    for s in sorted(os.listdir(src)):
        if s.startswith(".") or not os.path.isdir(os.path.join(src, s)): continue
        for p in sorted(os.listdir(os.path.join(src, s))):
            if os.path.isdir(os.path.join(src, s, p)): out.append(f"{s}/{p}")
    return out

cfg = yaml.safe_load(open(args.config))
in_config, with_plugins = set(), set()
for s, sp in cfg["subsystems"].items():
    np = sp.get("no_plugins") or []
    for p in sp.get("whitelist", []):
        in_config.add(f"{s}/{p}")
        if np is not True and p not in np: with_plugins.add(f"{s}/{p}")
packages = all_packages(SRC)
exists = set(packages)

deps = {}
for p in packages:
    cp, ct = buildfile_model.deps_of(SRC, p, CORE)
    pp, pt = buildfile_model.deps_of(SRC, p, PLUGINS)
    deps[p] = ({d for d in cp if d in exists and d != p}, ct,
               {d for d in pp if d in exists and d != p}, pt)

# Tools the generator leaves undefined expand to nothing, which is harmless for
# the header-only ones on the global include path (CLHEP, expat, ...): count
# whatever the configured packages already build with as provided.
provided = provided_tools(args.cmake, set(args.switches))
for p in in_config & exists:
    provided |= deps[p][1] | (deps[p][3] if p in with_plugins else set())
missing = {t for p in packages for t in deps[p][1] | deps[p][3]
           if not t.endswith("-flag")} - provided  # -flag: compiler flags, not externals

# --- blockers --------------------------------------------------------------

def closure_blockers(p):
    """Missing tools in the core dependency closure of p, and for each one a
    package that needs it directly (reached through `parent`)."""
    parent, seen, todo, found = {p: None}, {p}, deque([p]), {}
    while todo:
        q = todo.popleft()
        for t in deps[q][1] & missing:
            found.setdefault(t, q)
        for d in deps[q][0]:
            if d not in seen:
                seen.add(d); parent[d] = q; todo.append(d)
    return found, parent

blockers = {p: frozenset(closure_blockers(p)[0]) for p in packages}
plugin_only = {}
for p in packages:
    extra = set(deps[p][3] & missing)
    for d in deps[p][2]: extra |= blockers[d]
    plugin_only[p] = frozenset(extra - blockers[p])

buildable = {p for p in packages if not blockers[p]}
print(f"packages in the source tree: {len(packages)}, in the configuration: {len(in_config)}, "
      f"buildable as modelled: {len(buildable)}")
print(f"missing tools: {' '.join(sorted(missing))}\n")

odd = sorted(p for p in in_config & exists if blockers[p])
if odd:
    print("in the configuration although the model says blocked (pruned by")
    print("gen/prepare beyond what buildfile_model.py knows?):")
    for p in odd: print(f"   {p}: {' '.join(sorted(blockers[p]))}")
    print()

free = sorted(buildable - in_config)
bysub = defaultdict(list)
for p in free: bysub[p.split("/")[0]].append(p.split("/", 1)[1])
print(f"buildable but not in the configuration: {len(free)}")
for s in sorted(bysub, key=lambda s: -len(bysub[s])):
    print(f"   {s} ({len(bysub[s])}): {' '.join(bysub[s])}")
print()

sets = Counter(blockers[p] for p in packages if blockers[p])
print(f"blocker sets, by packages held back (of {len(packages) - len(buildable)} blocked):")
for s, n in sets.most_common(args.top):
    ex = [p for p in packages if blockers[p] == s]
    subs = Counter(p.split("/")[0] for p in ex).most_common(3)
    print(f"   {n:4d}  {{{', '.join(sorted(s))}}}   e.g. {', '.join(f'{k} ({v})' for k, v in subs)}")
print()

print("per missing tool: blocks alone / blocks in total / plugins only")
alone = Counter(next(iter(s)) for p, s in blockers.items() if len(s) == 1)
total = Counter(t for s in blockers.values() for t in s)
plug = Counter(t for p in buildable for t in plugin_only[p])
for t in sorted(missing, key=lambda t: (-alone[t], -total[t], t)):
    if total[t] or plug[t]:
        print(f"   {t:28s} {alone[t]:5d} {total[t]:5d} {plug[t]:5d}")

for p in args.why:
    found, parent = closure_blockers(p)
    print(f"\n{p}: {' '.join(sorted(found)) or 'buildable'}"
          + (f" (plugins also need: {' '.join(sorted(plugin_only[p]))})" if plugin_only[p] else ""))
    for t, q in sorted(found.items()):
        chain = [q]
        while parent[chain[-1]]: chain.append(parent[chain[-1]])
        print(f"   {t}: {' <- '.join(chain)}")
