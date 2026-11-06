"""What the gen/prepare modules share: the release being prepared, and how
they edit it.

gen/prepare adjusts a CMSSW source tree before the CMake files are generated
from it. Run it from the directory that contains the cmssw/ source tree, with
the CMSSW version string as argument (e.g. CMSSW_10_6_30), --with-tensorflow
when the build has the TensorFlow C++ API (pkgs/tensorflow-cc.nix) and
--with-tauolapp when it has Tauola++ (pkgs/tauolapp.nix): their users are then
kept rather than pruned.

    python3 gen/prepare CMSSW_20_1_0_pre4 --with-tensorflow --with-tauolapp

It edits the sources in place and is not idempotent: run it on a fresh tree.
The edits, by kind, in the order they run (__main__.py):

  scope.py        what this build leaves out (packages, externals, the GPU
                  backends) and the dependency declarations that go with it
  toolchain.py    externals and compilers newer than the release was written
                  for: boost, ROOT, protobuf, tinyxml2, gcc 11, python 3
  portability.py  clang, libc++, macOS and non-glibc systems
  fixes.py        bugs in CMSSW itself, whatever the platform
"""
import glob
import os
import re
import shutil
import sys

version = sys.argv[1] if len(sys.argv) > 1 else "CMSSW_20_1_0"
release_cycle = tuple(int(x) for x in version.split("_")[1:3])
with_tensorflow = "--with-tensorflow" in sys.argv[2:]
with_tauolapp = "--with-tauolapp" in sys.argv[2:]


def edit(path, editor, required=True):
    """Replace the contents of path by editor(contents).

    An edit that changes nothing is an error: the code it was written for
    has moved or changed upstream, and an edit that silently stopped
    applying shows up hours later as a compile error or a crash, if at all.
    required=False is for editors applied to many files, or to a file whose
    other versions need no change (say which, at the call).
    """
    with open(path) as f:
        content = f.read()
    new = editor(content)
    if new == content and required:
        raise SystemExit(f"{path}: the edit at {_caller()} changed nothing; "
                         "the code it was written for has moved or changed")
    with open(path, "w") as f:
        f.write(new)


def _caller():
    """file:line of the edit in the module that asked for it"""
    import inspect
    here = os.path.dirname(os.path.abspath(__file__))
    for frame in inspect.stack():
        f = os.path.abspath(frame.filename)
        if os.path.dirname(f) == here and f != os.path.abspath(__file__):
            return f"{os.path.basename(f)}:{frame.lineno}"
    return "?"


def drop_tool_deps(path, deps):
    """Drop the <use name="..."/> of deps from a BuildFile, where present."""
    if not os.path.exists(path):
        return
    edit(path, required=False, editor=lambda xml: re.sub(
        r'<use\s+name="(?:' + "|".join(re.escape(d) for d in deps) + r')"\s*/>\n?',
        "", xml))


TRITON_DEPS = ["HeterogeneousCore/SonicTriton", "HeterogeneousCore/SonicCore",
               "triton-inference-client"]
TF_TRITON_DEPS = TRITON_DEPS + ["PhysicsTools/TensorFlow", "tensorflow-cc"]
# what is pruned along with the files below: the TensorFlow dependencies
# only when the build has no TensorFlow
PRUNED_DEPS = TRITON_DEPS if with_tensorflow else TF_TRITON_DEPS


def python_only(pkg):
    """Keep a package's python/ (and data/, and its headers, for code that
    includes them): no library, no plugins."""
    pkg = "cmssw/" + pkg
    if os.path.exists(pkg + "/BuildFile.xml"):
        for d in ("src", "plugins", "test", "bin"):
            shutil.rmtree(os.path.join(pkg, d), ignore_errors=True)
        os.remove(pkg + "/BuildFile.xml")
