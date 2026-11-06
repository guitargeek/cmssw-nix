"""A standard Run 3 MC production, as cmsDriver.py writes it.

Four steps, in the shape of the release validation's 2024 workflows, for a
single-muon sample (SingleMuPt10):

  1. GEN,SIM                                   -> step1.root
  2. DIGI,L1,DIGI2RAW,HLT (the 2024 menu)      -> step2.root
  3. RAW2DIGI,L1Reco,RECO,RECOSIM,PAT          -> step3.root, step3_inMINIAODSIM.root
  4. NANO                                      -> step4.root

`python3 chain.py <step>` writes step<step>_cfg.py for the full job, which
reads its conditions from the global tag over Frontier (see README.md).
offline() turns such a configuration into the job the flake check runs.
"""
import subprocess
import sys

import FWCore.ParameterSet.Config as cms

COMMON = ["--conditions", "auto:phase1_2024_realistic", "--era", "Run3_2024",
          "--geometry", "DB:Extended", "--no_exec"]

# The HF and Castor shower libraries are not on cms-data (and not in the
# release): switch them off and point their file names, which must resolve
# even so, at a file that ships. HF (|eta| > 3) and Castor (|eta| > 5) fall
# back to the full simulation and the parameterised showers; a 10 GeV muon
# never gets there. See examples/MuonGunSim/README.md. (cmsDriver splits the
# commands at a backslash-n.)
NO_SHOWER_LIBRARIES = "\\n".join([
    "process.g4SimHits.HCalSD.UseShowerLibrary = False",
    "process.g4SimHits.CastorSD.useShowerLibrary = False",
    "process.g4SimHits.CastorShowerLibrary.FileName = cms.FileInPath('SimG4CMS/Calo/data/responsTBpim50.dat')",
    "process.HFLibraryFileBlock.FileName = cms.FileInPath('SimG4CMS/Calo/data/responsTBpim50.dat')",
])

STEPS = {
    1: ["SingleMuPt10_pythia8_cfi", "-s", "GEN,SIM", "-n", "10",
        "--beamspot", "DBrealistic", "--datatier", "GEN-SIM", "--eventcontent", "FEVTDEBUG",
        "--fileout", "file:step1.root", "--customise_commands", NO_SHOWER_LIBRARIES],
    2: ["step2", "-s", "DIGI:pdigi_valid,L1,DIGI2RAW,HLT:@relval2024", "-n", "-1",
        "--filein", "file:step1.root", "--datatier", "GEN-SIM-DIGI-RAW", "--eventcontent", "FEVTDEBUGHLT",
        "--fileout", "file:step2.root"],
    3: ["step3", "-s", "RAW2DIGI,L1Reco,RECO,RECOSIM,PAT", "-n", "-1",
        "--filein", "file:step2.root", "--datatier", "GEN-SIM-RECO,MINIAODSIM",
        "--eventcontent", "RECOSIM,MINIAODSIM", "--fileout", "file:step3.root"],
    4: ["step4", "-s", "NANO", "-n", "-1",
        "--filein", "file:step3_inMINIAODSIM.root", "--datatier", "NANOAODSIM", "--eventcontent", "NANOAODSIM",
        "--fileout", "file:step4.root"],
}


def generate(step):
    """Run cmsDriver.py for one step; returns the configuration file name."""
    cfg = f"step{step}_cfg.py"
    subprocess.run(["cmsDriver.py", *STEPS[step], *COMMON, "--python_filename", cfg], check=True)
    return cfg


def offline(process):
    """The job without events and without the conditions database.

    Constructing the EventProcessor translates every parameter into its
    C++ ParameterSet (and resolves every FileInPath), constructs every
    scheduled module and every ES module, and runs beginJob: the missing
    plugins, data files and wrong parameters of the whole configuration.
    The global tag is the one thing left out (no network in the build
    sandbox); with no event, no run begins and nothing asks for conditions.
    """
    process.source = cms.Source("EmptySource")
    process.maxEvents.input = 0
    del process.GlobalTag
    return process


if __name__ == "__main__":
    for step in sys.argv[1:]:
        generate(int(step))
