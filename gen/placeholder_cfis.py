"""Write placeholders for the cfis of producers that are not built.

The release's configuration code imports some cfis at module level only to
swap their modules in under a process modifier: the Triton (SONIC) variants
of the b-tagging, DeepMET and DeepTau producers, the TensorFlow-based tau
identification, NanoAOD's TauSpinner table. Those producers need externals
this build does not have and gen/prepare_sources.py prunes them, so their
cfis - generated from the plugins - never exist, and the configuration that
imports them does not load at all, whether the modifier is on or not.

This runs after the cfi generation of the install phase. For every
`from Sub.Pkg.<...>_cfi import name` in the installed python code that
resolves neither to a handwritten file nor to a generated one, in a package
that is part of the build, it writes a placeholder cfi into the generated
tree: a module of the plugin's type without parameters, which accepts any
clone(). The configuration loads, and a job that actually runs the module
fails on the missing plugin.

Usage: python3 placeholder_cfis.py <release prefix>
"""
import ast
import os
import re
import sys

out = sys.argv[1]
src = os.path.join(out, "src")

# One class for all placeholders, in a module of its own: configuration code
# that swaps one placeholder for another (toReplaceWith, as the Phase-2
# pixel rechits do for the Phase-1 ones) requires both to be of one class.
SHARED = ("FWCore", "ParameterSet", "notBuiltPlaceholder")
SHARED_MODULE = """import FWCore.ParameterSet.Config as cms

# The module of the cfis whose plugin is not part of this build (it needs an
# external the build does not have; see gen/placeholder_cfis.py).
class _NotBuilt(cms.EDProducer):
    def clone(self, *args, **params):
        return _NotBuilt(self.type_())

    # configuration code sets the module's parameters as plain values
    # (module.InputLabel = "..."), which only declared parameters accept;
    # the module never runs, so drop them
    def __setattr__(self, name, value):
        try:
            super().__setattr__(name, value)
        except TypeError:
            pass

    # and reads its parameters to derive its own: the DRN correctors clone
    # their SONIC producer's client PSet (patPhotonDRNCorrectionProducer
    # .Client.clone(...)). Only that one: the framework probes modules with
    # hasattr (the alpaka accelerator asks for an "alpaka" PSet), which has
    # to stay false.
    def __getattr__(self, name):
        if name != "Client":
            raise AttributeError(name)
        return _Unknown()


class _Unknown:
    \"\"\"A parameter of a placeholder: anything read from it, or a clone of
    it, is another one.\"\"\"
    def clone(self, *args, **params):
        return _Unknown()

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return _Unknown()
"""

TEMPLATE = """# Placeholder: the plugin behind this cfi is not part of this build (it needs
# an external the build does not have; see gen/placeholder_cfis.py).
from FWCore.ParameterSet.notBuiltPlaceholder import _NotBuilt

{definitions}"""


# The plugin type behind a cfi, from the package's (installed) sources: the
# generated cfi is named after the plugin's default module label, and an
# alpaka module registers as "<class>@alpaka". Code that inspects the type
# (HeterogeneousCore/AlpakaCore's makeSerialClone) then sees the right one;
# without a match, the label stands in for it.
DEFINE = re.compile(r"\bDEFINE_FWK_(?:EVENTSETUP_)?(ALPAKA_)?MODULE\(\s*([\w:]+)\s*\)")
plugin_types = {}


def default_module_label(cls):
    """edm::defaultModuleLabel: HBHERecHitProducerPortable ->
    hbheRecHitProducerPortable, all of a leading run of capitals but the
    last one in lower case."""
    label = cls.replace(":", "")
    ups = len(label) - len(label.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    if 1 < ups < len(label):
        ups -= 1
    return label[:ups].lower() + label[ups:]


def plugin_type(sub, pkg, label):
    key = (sub, pkg)
    if key not in plugin_types:
        types = plugin_types[key] = {}
        for root, dirs, files in os.walk(os.path.join(src, sub, pkg)):
            for name in files:
                if name.endswith(".cc"):
                    text = open(os.path.join(root, name), encoding="utf-8", errors="replace").read()
                    for alpaka, cls in DEFINE.findall(text):
                        types[default_module_label(cls)] = cls + ("@alpaka" if alpaka else "")
    return plugin_types[key].get(label, label)


def exists(sub, pkg, rest):
    rel = os.path.join(*rest) + ".py"
    return (os.path.exists(os.path.join(src, sub, pkg, "python", rel))
            or os.path.exists(os.path.join(out, "cfipython", sub, pkg, rel)))


wanted = {}
for root, dirs, files in os.walk(src):
    if "/python" not in root:
        continue
    for name in files:
        if not name.endswith(".py"):
            continue
        try:
            tree = ast.parse(open(os.path.join(root, name), encoding="utf-8", errors="replace").read())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.ImportFrom) and node.level == 0 and node.module):
                continue
            parts = node.module.split(".")
            if len(parts) < 3 or not parts[-1].endswith("_cfi"):
                continue
            sub, pkg, rest = parts[0], parts[1], parts[2:]
            if not os.path.isdir(os.path.join(src, sub, pkg)) or exists(sub, pkg, rest):
                continue
            names = wanted.setdefault((sub, pkg, tuple(rest)), set())
            names.update(a.name for a in node.names if a.name != "*")

shared = os.path.join(out, "cfipython", *SHARED) + ".py"
os.makedirs(os.path.dirname(shared), exist_ok=True)
with open(shared, "w") as f:
    f.write(SHARED_MODULE)

for (sub, pkg, rest), names in sorted(wanted.items()):
    # a star import gets the label the cfi is named after
    names = names or {rest[-1][:-len("_cfi")]}
    path = os.path.join(out, "cfipython", sub, pkg, *rest) + ".py"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(TEMPLATE.format(definitions="".join(
            f'{n} = _NotBuilt("{plugin_type(sub, pkg, rest[-1][:-len("_cfi")])}")\n'
            for n in sorted(names))))
    print("placeholder:", ".".join((sub, pkg) + rest), " ".join(sorted(names)))
