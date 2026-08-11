"""Small source-tree adjustments before generating the CMake files.

Run from the directory that contains the cmssw/ source tree.

* Reduce FWCore/Framework/bin/BuildFile.xml to just the plain cmsRun binary
  (upstream also defines cmsRunTC, cmsRunJE, ... linked against different
  allocators/profilers).
* Drop the CondorStatusService plugin: it is only useful on HTCondor grid
  nodes and is the sole reason FWStorage/Services depends on the xrootd-based
  XrdAdaptor, which we don't build.
"""
import os
import re

# --- only the plain cmsRun -------------------------------------------------

path = "cmssw/FWCore/Framework/bin/BuildFile.xml"
with open(path) as f:
    xml = f.read()

bins = re.findall(r'<bin name="[^"]*".*?</bin>', xml, flags=re.DOTALL)
keep = [b for b in bins if '<bin name="cmsRun"' in b]
if len(keep) == 1:  # already trimmed on a rerun -> keep as is
    with open(path, "w") as f:
        f.write(keep[0] + "\n")

# --- no CondorStatusService / XrdAdaptor dependency ------------------------

condor = "cmssw/FWStorage/Services/plugins/CondorStatusService.cc"
if os.path.exists(condor):
    os.remove(condor)

path = "cmssw/FWStorage/Services/plugins/BuildFile.xml"
with open(path) as f:
    xml = f.read()
xml = xml.replace('<use name="FWStorage/XrdAdaptor"/>\n', "")
with open(path, "w") as f:
    f.write(xml)

# ... and don't load the two pruned plugins as default cmsRun services
path = "cmssw/FWCore/Framework/src/defaultCmsRunServices.cc"
with open(path) as f:
    src = f.read()
for service in ["CondorStatusService", "XrdStatisticsService"]:
    src = src.replace(f'"{service}",\n', "")
    src = src.replace(f'"{service}",', "")
with open(path, "w") as f:
    f.write(src)

# --- ROOT 6.40 compatibility ------------------------------------------------

# With ROOT 6.40 (CMSSW_20_1_0_pre2 targets 6.36), TTree::SetCacheSizeAux
# emits a benign "Not setting up an automatically sized TTreeCache" error when
# PoolSource opens a file; keep InitRootHandlers from making it fatal.
path = "cmssw/FWCore/Services/plugins/InitRootHandlers.cc"
with open(path) as f:
    src = f.read()
assert 'const, 12> in_message{' in src
src = src.replace("const, 12> in_message{", "const, 13> in_message{")
src = src.replace(
    '{"no dictionary for class",',
    '{"Not setting up an automatically sized TTreeCache",\n       "no dictionary for class",',
)
with open(path, "w") as f:
    f.write(src)
