# The High-Level Trigger: of the events the L1 trigger keeps, which does CMS
# record?
#
# The L1 trigger (python/muon_gun_l1_cfg.py) keeps about 100 000 bunch
# crossings a second, from coarse data in 4 us. The HLT is software - this
# same framework, on a farm of a few hundred nodes - that reconstructs each
# of those events in a few hundred milliseconds and keeps about one in a
# hundred. A trigger "path" is a sequence of reconstruction steps and
# filters, ordered so that the cheap ones reject first; the event is
# recorded if any path accepts it.
#
# This job runs the first half of a real one, HLT_Mu20 of the release's
# menu (HLTrigger/Configuration's HLT_GRun), with the menu's own modules:
#
#   L1TGlobalProducer      the L1 Global Trigger: evaluates the L1 menu's
#                          algorithms (L1_SingleMu18, ...) on the uGMT muons
#   HLTL1TSeed             the path's L1 seed: did L1_SingleMu18 fire?
#   HLTMuonL1TFilter       ... and which L1 muons fired it
#   MuonSeedGenerator      seeds from the DT segments, as offline
#   L2MuonSeedGenerator-   of those, the ones an accepted L1 muon points at
#     FromL1T
#   L2MuonProducer         the standalone ("L2") muon fit through the chambers
#   HLTMuonL2FromL1TPre-   an L2 muon from an accepted L1 muon (the menu's
#     Filter               pt cut here is 0: the cut is on the L3 muon)
#
# The L1 menu is the 2022 collisions menu, the newest in cms-data (later ones
# live in the conditions database); its L1_SingleMu18 is what the path seeds
# on.
#
# The second half - the L3 muon, which adds the tracker, and the 20 GeV cut
# - needs the pixel tracking in its heterogeneous (alpaka) form, which is
# not built here, and a DNN seeder whose TensorFlow inference is pruned.
#
# plugins/HLTMuonMatch.cc then reads the filters' trigger objects back and
# matches them to the simulated muons.
#
# 20_1 only: the 10_6 configuration does not build the emulators and the HLT.
#
# Reads muon_gun_digi.root, so run python/muon_gun_digi_cfg.py first.
import os
import sys

import FWCore.ParameterSet.Config as cms

sys.path.insert(0, globals().get("__file__") and os.path.dirname(os.path.abspath(__file__))
                or os.path.join(os.getcwd(), "python"))
from muon_gun_stages import add_detinfo_fixups, add_l1_muon_emulation, add_muon_reco, add_tracking_reco

process = cms.Process("HLTX")

add_tracking_reco(process, False)
add_muon_reco(process, False)
add_detinfo_fixups(process, False)

# --- L1: the muon trigger, then the Global Trigger -----------------------------
process.l1Emulation = add_l1_muon_emulation(process)

# The L1 menu: the algorithms, their conditions, and the prescale and mask
# tables, from the cms-data package L1Trigger-L1TGlobal.
process.load("L1Trigger.L1TGlobal.GlobalParameters_cff")
process.load("L1Trigger.L1TGlobal.TriggerMenu_cff")
process.TriggerMenu.L1TriggerMenuFile = "L1Menu_Collisions2022_v1_1_0.xml"
process.load("L1Trigger.L1TGlobal.PrescalesVetosFract_cff")

from L1Trigger.L1TGlobal.simGtStage2Digis_cfi import simGtStage2Digis

process.simGtStage2Digis = simGtStage2Digis.clone(
    MuonInputTag="simGmtStage2Digis",
    # the object map: which objects fired which algorithm, which the HLT
    # seed needs to hand the right muons on
    ProduceL1GtObjectMapRecord=cms.bool(True),
    # no muon showers are simulated
    useMuonShowers=cms.bool(False),
)


# --- HLT: modules taken from the menu -------------------------------------------
def take_from_menu(process, menu, labels):
    """Copy the named modules of the menu into the process, with the
    EventSetup components they name - propagators, fitters, hit builders -
    and the ones those name, and so on. The menu itself is not loaded: it
    defines several hundred EventSetup components, many for packages or
    conditions this job does not have."""
    es = {}
    for name, comp in list(menu.es_producers_().items()) + list(menu.es_sources_().items()):
        es[name] = comp
        for key in ("ComponentName", "appendToDataLabel"):
            if hasattr(comp, key) and getattr(comp, key).value():
                es[getattr(comp, key).value()] = comp

    def strings(pset):
        for name in pset.parameterNames_():
            value = getattr(pset, name)
            if isinstance(value, cms.PSet):
                yield from strings(value)
            elif isinstance(value, cms.VPSet):
                for p in value:
                    yield from strings(p)
            elif isinstance(value, cms.string):
                yield value.value()
            elif isinstance(value, cms.vstring):
                yield from value

    todo = []
    for label in labels:
        module = getattr(menu, label).clone()
        setattr(process, label, module)
        todo.append(module)
    taken = set()
    while todo:
        for s in strings(todo.pop()):
            comp = es.get(s)
            if comp is not None and comp.label_() not in taken and not hasattr(process, comp.label_()):
                taken.add(comp.label_())
                setattr(process, comp.label_(), comp.clone())
                todo.append(comp)


from HLTrigger.Configuration.HLT_GRun_cff import fragment

hltModules = [
    "hltL1sSingleMu18",
    "hltL1fL1sMu18L1Filtered0",
    "hltL2OfflineMuonSeeds",
    "hltL2MuonSeeds",
    "hltL2Muons",
    "hltL2MuonCandidates",
    "hltL2fL1sMu18L1f0L2Filtered10Q",
]
take_from_menu(process, fragment, hltModules)

# DT only, as in the offline muon reconstruction: the gun fires into the
# barrel, and neither the CSC nor the RPC or GEM hits are reconstructed.
process.hltL2OfflineMuonSeeds.EnableCSCMeasurement = False
for _pset in (
    process.hltL2Muons.L2TrajBuilderParameters.FilterParameters,
    process.hltL2Muons.L2TrajBuilderParameters.BWFilterParameters,
):
    _pset.EnableCSCMeasurement = False
    _pset.EnableRPCMeasurement = False
    _pset.EnableGEMMeasurement = False

# --- the measurement ------------------------------------------------------------
# In an EndPath, so that it sees the events the path rejects as well.
process.hltMuons = cms.EDAnalyzer(
    "HLTMuonMatch",
    simTracks=cms.InputTag("g4SimHits"),
    l1Filter=cms.InputTag("hltL1fL1sMu18L1Filtered0"),
    l2Filter=cms.InputTag("hltL2fL1sMu18L1f0L2Filtered10Q"),
    maxDeltaR=cms.double(0.3),
    # Well above the L1 seed's 18 GeV, so that the L1 pt resolution does not
    # decide. Measured: 14/15 such muons at L1, 13/15 at L2. The one L1 misses
    # is the muon the L1 job misses, at eta -0.25 in the gap between wheels 0
    # and -1. The one L2 misses fired L1, but the local reconstruction found
    # a DT segment for it in one station only (MB4 of wheel 2): the
    # segment-based seeding makes no seed from that, and the menu does not
    # seed from an L1 muon alone (UseUnassociatedL1 = False).
    plateauPt=cms.double(25.0),
    minEfficiency=cms.double(0.8),
    # Measured: 1.008, from the muon chambers alone.
    minMedianPtRatio=cms.double(0.8),
    maxMedianPtRatio=cms.double(1.25),
)
process.measurement = cms.EndPath(process.hltMuons)

process.p = cms.Path(
    process.l1Emulation
    * process.simGtStage2Digis
    * process.offlineBeamSpot
    * process.hltL1sSingleMu18
    * process.hltL1fL1sMu18L1Filtered0
    * process.dt1DRecHits
    * process.dt4DSegments
    * process.hltL2OfflineMuonSeeds
    * process.hltL2MuonSeeds
    * process.hltL2Muons
    * process.hltL2MuonCandidates
    * process.hltL2fL1sMu18L1f0L2Filtered10Q
)

# Online, the HLT unpacks everything from the raw data; here the inputs are
# the emulated L1 and the offline local reconstruction of the simulated
# digis, so its input tags are renamed (on the path: that is where the
# replacement looks).
from FWCore.ParameterSet.MassReplace import massReplaceInputTag

for old, new in [
    ("hltGtStage2Digis:Muon", "simGmtStage2Digis"),
    ("hltGtStage2Digis", "simGtStage2Digis"),
    ("hltGtStage2ObjectMap", "simGtStage2Digis"),
    ("hltDt4DSegments", "dt4DSegments"),
    ("hltOnlineBeamSpot", "offlineBeamSpot"),
]:
    massReplaceInputTag(process, old, new)
