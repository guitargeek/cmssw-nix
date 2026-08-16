#!/usr/bin/env python3
"""dlopen every library in a CMSSW build and report the ones that fail.

The cmake build links each library and plugin, but a library that links
cleanly can still be unusable at runtime: a missing external, a symbol that
only a pruned source file defined, or a Fortran common block nobody
allocates all show up as an unresolved symbol the first time cmsRun tries to
load the plugin. Sweeping the whole lib/ directory catches those in one go,
instead of one cmsRun crash at a time.

    python3 gen/sweep_libs.py <build>/lib

Loading everything into one process is the fast path. Anything that fails
there is retried in a forked child that has loaded nothing else, so the
report distinguishes a genuinely broken library from one that merely lost a
race for a shared resource (static TLS, in particular).
"""

import ctypes
import glob
import os
import sys


def libraries(d):
    return sorted(glob.glob(os.path.join(d, "lib*.so")) + glob.glob(os.path.join(d, "plugin*.so")))


def try_load(path):
    """None if the library loads, else the first line of the error."""
    try:
        ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)
    except OSError as e:
        return str(e).split("\n")[0]
    return None


def try_load_isolated(path):
    """Same, in a fresh child, so nothing this process already loaded counts.

    Also survives a library whose static initialisers abort, which an
    in-process load would not.
    """
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(r)
        err = try_load(path) or ""
        os.write(w, err.encode()[:1000])
        os._exit(0)
    os.close(w)
    err = os.read(r, 4096).decode()
    os.close(r)
    _, status = os.waitpid(pid, 0)
    if err:
        return err
    if status != 0:
        return f"loading the library killed the process (wait status {status})"
    return None


def main():
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    libdir = sys.argv[1]
    libs = libraries(libdir)
    if not libs:
        print(f"no libraries under {libdir}", file=sys.stderr)
        return 2

    suspect = [l for l in libs if try_load(l) is not None]

    # Re-test only the suspects, each on its own, for an accurate message.
    broken = []
    for l in suspect:
        err = try_load_isolated(l)
        if err is not None:
            broken.append((os.path.basename(l), err))

    print(f"{len(broken)} of {len(libs)} libraries failed to dlopen")
    for name, err in broken:
        print(f"  {name}: {err}")
    if len(suspect) != len(broken):
        print(
            f"  ({len(suspect) - len(broken)} more failed only when everything "
            "was loaded at once, which no real job does)"
        )
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
