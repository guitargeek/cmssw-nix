"""Bugs in CMSSW itself, independent of the platform: an uninitialised flag or
pointer, an iterator stepped past begin(), a payload dereferenced when it is
not there. Each says whether upstream is still affected.
"""
from common import *  # noqa: F401,F403

# SiPixelQualityESProducer dereferences the DetVOff payload even when the
# SiPixelDetVOffRcd is not in its merge list (running without a conditions
# DB there is nothing to provide it from).
path = "cmssw/CalibTracker/SiPixelESProducers/plugins/SiPixelQualityESProducer.cc"
if os.path.exists(path):
    # (fixed upstream by 20_1)
    edit(path, required=release_cycle < (11, 0), editor=lambda src: src.replace(
        "dbptr->add(Voff.product());",
        "if (Voff.isValid())\n    dbptr->add(Voff.product());"))


# --- ECAL component shapes only when component digis are asked for (20_1) -
if release_cycle >= (20, 0):
    # EcalDigiProducer builds its ComponentShapeCollection through the
    # ComponentShapeCollection(iC) delegate, which hard-codes useDBShape=true,
    # and accumulate() calls setEventSetup on it for every event in which the
    # barrel is digitised. Both happen regardless of componentSeparateDigi -
    # the parameter that decides whether the component shapes are used at all.
    #
    # They are not used otherwise. EBHitResponseImpl reaches shapes() only in
    # the else of `if (!m_isComponentShapeBased)` (EBHitResponse.icc:139), and
    # of the three responses EcalDigiProducer builds, only m_ComponentResponse
    # passes doComponent=true - and it is a nullptr unless componentSeparateDigi
    # is set, which nothing but the ecal_component era modifiers do.
    #
    # So in the default configuration the collection is filled from
    # EcalSimComponentShapeRcd and then never read. That is fatal here: the
    # only producer of that record in this build is
    # EcalTrivialConditionRetriever (producedEcalSimComponentShape defaults to
    # true), and its EBSimComponentShapeFiles list is empty, because the 23
    # per-depth shape files are in no cms-data package and the conditions
    # database is not reachable from here. It therefore delivers a payload
    # with no shapes in it and ComponentShape::fillShape dies on
    # barrel_shapes.at(0), which is what keeps examples/MuonGunDigi's
    # calorimeter job 10_6-only.
    #
    # Tie the DB lookup to the switch that decides whether its result is read.
    # With componentSeparateDigi off, ComponentShape takes its useDB=false
    # branch - which upstream provides for exactly this case ("fill with dummy
    # values, since this code is only reached before the actual digi
    # simulation") and which no response object ever looks at. With it on,
    # nothing changes.
    def component_shapes_follow_switch(src):
        assert src.count("      m_ComponentShapes(iC),\n") == 1
        return src.replace(
            "      m_ComponentShapes(iC),\n",
            '      m_ComponentShapes(params.getParameter<bool>("componentSeparateDigi"), iC),\n',
        )

    edit("cmssw/SimCalorimetry/EcalSimProducers/src/EcalDigiProducer.cc",
         component_shapes_follow_switch)

# CastorSD deletes a pointer it never initialised.
#
# CastorShowerLibrary* showerLibrary is a raw member that the constructor
# assigns only inside `if (useShowerLibrary)`, and that the initialiser list -
# which does cover numberingScheme, lvC3EF, lvC3HF, lvC4EF, lvC4HF and lvCAST -
# leaves out. ~CastorSD then runs `delete showerLibrary` unconditionally, so a
# job that switches the library off deletes an indeterminate pointer and
# segfaults on the way out, after every event has been written.
#
# Production never sees it because production always has the Castor shower
# library. We cannot: the file is distributed separately and the download stub
# points at a host that is now behind CERN SSO (see examples/MuonGunSim). So
# switching it off is the only option here, and that path has to work.
#
# Both releases have it - 10_6_30 on one line, 20_1_0_pre2 clang-formatted
# onto several - so the anchor is the last initialiser rather than the run
# of them, and a miss is a hard failure: the fix silently not applying
# would only show up as a segfault at the end of a job that otherwise
# looks perfect.
path = "cmssw/SimG4CMS/Forward/src/CastorSD.cc"
if os.path.exists(path):
    def fix_castor_shower_library(src):
        if "lvCAST(nullptr), showerLibrary(nullptr)" in src:
            return src
        anchor = "lvCAST(nullptr) {"
        if anchor not in src:
            raise SystemExit(
                "CastorSD.cc: initialiser list not where expected - the"
                " uninitialised showerLibrary fix needs rechecking")
        return src.replace(
            "lvCAST(nullptr) {",
            "lvCAST(nullptr), showerLibrary(nullptr) {")
    edit(path, fix_castor_shower_library)

# --- a map iterator decremented past begin() (all versions) ---------------
# HcalPulseContainmentCorrection::getCorrection decrements the result of
# upper_bound() before checking whether it is begin(), which it is for every
# amplitude below the first tabulated point (1 fC) - and decrementing begin()
# is undefined. libstdc++'s tree lands on its header node and the value is
# never read in that branch; libc++'s walks off the tree and dereferences
# null, killing every HBHE reconstruction that sees a small pulse. Only step
# back when there is somewhere to step to.
path = "cmssw/CalibCalorimetry/HcalAlgos/src/HcalPulseContainmentCorrection.cc"
if os.path.exists(path):
    def no_decrement_past_begin(src):
        if "if (fclower != mCorFactors_.begin())" in src:
            return src
        new, n = re.subn(r"(\n(\s*)fclower = fcupper;\n)\s*fclower--;\n",
                         r"\1\2if (fclower != mCorFactors_.begin())\n\2  fclower--;\n", src)
        if n != 1:
            raise SystemExit("HcalPulseContainmentCorrection.cc: getCorrection not where expected")
        return new
    edit(path, no_decrement_past_begin)

# --- the DT trigger primitive configuration from python, marked valid (20_1)
# DTConfigManager carries a flag saying whether the chamber (CCB)
# configuration is valid for the run; the DT trigger primitive emulator
# produces empty collections when it is not. The database producer sets it,
# the trivial (from-python) producer never does, and the constructor leaves
# it uninitialised - so whether the emulator runs at all depends on what was
# in the heap memory (on macOS: it did not). A configuration given in python
# is valid by construction.
path = "cmssw/L1TriggerConfig/DTTPGConfigProducers/src/DTConfigTrivialProducer.cc"
if os.path.exists(path):
    edit(path, required=release_cycle >= (11, 0), editor=lambda src: src.replace(
        "  m_manager->setUseAcceptParam(useBtiAcceptParam);  // CB Are these needed here???\n",
        "  m_manager->setUseAcceptParam(useBtiAcceptParam);  // CB Are these needed here???\n"
        "  m_manager->setCCBConfigValidity(true);\n", 1))

# --- FastSim's SimTracks marked as primaries (20_1) -------------------------
# SimTrack::genpartIndex() returns the generator particle's index only when
# the track is flagged primary (SimTrack::setIsPrimary), which the Geant4
# simulation sets on the particles it took from the generator. FastSim's
# ParticleManager stores the index but never sets the flag, so every FastSim
# SimTrack reads as having no generator particle, and the TrackingParticles
# built from them lose their link to it. Set it where the index is set.
path = "cmssw/FastSimulation/SimplifiedGeometryPropagator/src/ParticleManager.cc"
if os.path.exists(path) and "setIsPrimary" not in open(path).read():
    edit(path, lambda src: src.replace(
        "  simTracks_->back().setTrackId(simTrackIndex);\n",
        "  simTracks_->back().setTrackId(simTrackIndex);\n"
        "  if (particle->genParticleIndex() >= 0)\n"
        "    simTracks_->back().setIsPrimary();\n", 1))
