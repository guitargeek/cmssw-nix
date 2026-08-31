// A nanoAOD flat-table producer for reco::Muon.
//
// PhysicsTools/NanoAOD ships SimpleFlatTableProducer as a template and
// instantiates it for the types the standard nano sequences need - all of
// which are pat:: objects made from miniAOD, plus reco::Candidate for the
// gen-level tables. Reconstruction here stops at reco::Muon: there is no
// PAT layer in this build, and pat::Muon is what the shipped muon table
// reads.
//
// The generic reco::Candidate instantiation would take a reco::Muon (it
// derives from Candidate) but the string-based variable expressions are
// parsed against the *declared* type, so through a View<reco::Candidate>
// only the four-momentum and the charge are reachable - isGlobalMuon() and
// the track references are not. Instantiating the same template for
// reco::Muon makes the whole interface visible to the expressions.
#include "PhysicsTools/NanoAOD/interface/SimpleFlatTableProducer.h"
#include "DataFormats/MuonReco/interface/Muon.h"

#include "FWCore/Framework/interface/MakerMacros.h"

typedef SimpleFlatTableProducer<reco::Muon> SimpleRecoMuonFlatTableProducer;

DEFINE_FWK_MODULE(SimpleRecoMuonFlatTableProducer);
