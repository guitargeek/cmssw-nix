// Does the calorimeter give back the energy the simulation put in?
//
// The tracker analyzers in this example all measure a *position*: a rec hit
// is right if it lands where the particle crossed. A calorimeter rec hit is
// an amplitude, so the question changes. Geant4 deposited a known energy in a
// known cell; the digitiser turned it into photoelectrons, a preamplifier
// pulse and ten digitised samples; the reconstruction fits an amplitude back
// out of those samples and multiplies it by the calibration constants. The
// number that comes out should be the number that went in.
//
// That comparison is only fair because the digitiser and the reconstruction
// read their pedestals, gains and ADC-to-GeV constant from the same ES source
// here (EcalTrivialConditionRetriever, HcalHardcodeCalibrations). A response
// of one is then a statement about the chain, not about how well two
// independent sets of constants agree.
//
// ECAL and HCAL are not the same measurement. ECAL is homogeneous - the
// crystal is the absorber and the detector - so the reconstructed energy is
// the deposited energy and the response should be one. HCAL is a sampling
// calorimeter: the scintillator sees a small and known fraction of what the
// brass absorbs, and the reconstruction multiplies by a sampling factor of
// order a hundred to recover the incident energy. Its response is therefore
// that sampling factor, and is reported rather than asserted.
//
// Muons make this the sharpest version of the test. A minimum-ionising
// particle does not shower: it crosses one crystal and leaves a couple of
// hundred MeV, a few times the noise, which is the smallest signal ECAL is
// ever asked to reconstruct. And the ratio of that to the muon's momentum is
// the statement that the calorimeter is measuring a muon at all - an electron
// of the same momentum would deposit essentially all of it.
#include <algorithm>
#include <cmath>
#include <map>
#include <string>
#include <vector>

#include "DataFormats/EcalRecHit/interface/EcalRecHit.h"
#include "DataFormats/EcalRecHit/interface/EcalRecHitCollections.h"
#include "DataFormats/HcalDetId/interface/HcalDetId.h"
#include "DataFormats/HcalRecHit/interface/HcalRecHitCollections.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/Utilities/interface/EDGetToken.h"
#include "FWCore/Utilities/interface/Exception.h"
#include "FWCore/Utilities/interface/InputTag.h"
#include "SimDataFormats/CaloHit/interface/PCaloHitContainer.h"
#include "SimDataFormats/Track/interface/SimTrackContainer.h"

namespace {
  struct Tally {
    std::vector<double> response;  // E_reco / E_sim, per cell
    std::vector<double> perEvent;  // reconstructed energy per event, GeV
    unsigned long cellsWithDeposit = 0;
    unsigned long cellsReconstructed = 0;
    double totalReco = 0.0;
  };

  double median(std::vector<double> v) {
    if (v.empty())
      return 0.0;
    std::sort(v.begin(), v.end());
    return v[v.size() / 2];
  }
}  // namespace

class CaloEnergyResponse : public edm::one::EDAnalyzer<> {
public:
  explicit CaloEnergyResponse(const edm::ParameterSet&);
  void analyze(const edm::Event&, const edm::EventSetup&) override;
  void endJob() override;

private:
  const edm::EDGetTokenT<EcalRecHitCollection> ebRecHits_;
  const edm::EDGetTokenT<HBHERecHitCollection> hbheRecHits_;
  const edm::EDGetTokenT<edm::PCaloHitContainer> ebSimHits_;
  const edm::EDGetTokenT<edm::PCaloHitContainer> hcalSimHits_;
  const edm::EDGetTokenT<edm::SimTrackContainer> simTracks_;

  const double minEbSimEnergy_;
  const double minHbSimEnergy_;
  const double minEbEfficiency_;
  const double minEbResponse_;
  const double maxEbResponse_;
  const double minEbMip_;
  const double maxEbMip_;
  const double maxEOverP_;
  const double minHbResponse_;
  const double maxHbResponse_;

  Tally eb_, hb_;
  unsigned long muons_ = 0;
  double totalMuonMomentum_ = 0.0;

  // Sum the simulated energy per cell, then look each cell up among the rec
  // hits. Never the other way round: the digitiser puts electronics noise on
  // every channel in the calorimeter, so there are rec hits in thousands of
  // cells no particle ever entered, and they say nothing about whether the
  // reconstruction works.
  static void compare(const std::map<uint32_t, double>& sim,
                      const std::map<uint32_t, double>& reco,
                      double minSimEnergy,
                      Tally& tally);
};

CaloEnergyResponse::CaloEnergyResponse(const edm::ParameterSet& ps)
    : ebRecHits_(consumes<EcalRecHitCollection>(ps.getParameter<edm::InputTag>("ebRecHits"))),
      hbheRecHits_(consumes<HBHERecHitCollection>(ps.getParameter<edm::InputTag>("hbheRecHits"))),
      ebSimHits_(consumes<edm::PCaloHitContainer>(ps.getParameter<edm::InputTag>("ebSimHits"))),
      hcalSimHits_(consumes<edm::PCaloHitContainer>(ps.getParameter<edm::InputTag>("hcalSimHits"))),
      simTracks_(consumes<edm::SimTrackContainer>(ps.getParameter<edm::InputTag>("simTracks"))),
      minEbSimEnergy_(ps.getParameter<double>("minEbSimEnergy")),
      minHbSimEnergy_(ps.getParameter<double>("minHbSimEnergy")),
      minEbEfficiency_(ps.getParameter<double>("minEbEfficiency")),
      minEbResponse_(ps.getParameter<double>("minEbResponse")),
      maxEbResponse_(ps.getParameter<double>("maxEbResponse")),
      minEbMip_(ps.getParameter<double>("minEbMip")),
      maxEbMip_(ps.getParameter<double>("maxEbMip")),
      maxEOverP_(ps.getParameter<double>("maxEOverP")),
      minHbResponse_(ps.getParameter<double>("minHbResponse")),
      maxHbResponse_(ps.getParameter<double>("maxHbResponse")) {}

void CaloEnergyResponse::compare(const std::map<uint32_t, double>& sim,
                                 const std::map<uint32_t, double>& reco,
                                 double minSimEnergy,
                                 Tally& tally) {
  double perEvent = 0.0;
  for (const auto& cell : sim) {
    if (cell.second < minSimEnergy)
      continue;
    ++tally.cellsWithDeposit;
    const auto found = reco.find(cell.first);
    if (found == reco.end())
      continue;
    ++tally.cellsReconstructed;
    tally.response.push_back(found->second / cell.second);
    perEvent += found->second;
  }
  tally.perEvent.push_back(perEvent);
  tally.totalReco += perEvent;
}

void CaloEnergyResponse::analyze(const edm::Event& ev, const edm::EventSetup&) {
  edm::Handle<EcalRecHitCollection> ebReco;
  ev.getByToken(ebRecHits_, ebReco);
  if (!ebReco.isValid())
    throw cms::Exception("NoRecHits") << "no ECAL barrel rec hit collection is in the event";
  std::map<uint32_t, double> ebRecoById;
  for (const auto& hit : *ebReco)
    ebRecoById[hit.detid().rawId()] += hit.energy();

  edm::Handle<HBHERecHitCollection> hbheReco;
  ev.getByToken(hbheRecHits_, hbheReco);
  if (!hbheReco.isValid())
    throw cms::Exception("NoRecHits") << "no HBHE rec hit collection is in the event";
  std::map<uint32_t, double> hbRecoById;
  for (const auto& hit : *hbheReco)
    if (hit.id().subdet() == HcalBarrel)
      hbRecoById[hit.id().rawId()] += hit.energy();

  edm::Handle<edm::PCaloHitContainer> ebSim;
  ev.getByToken(ebSimHits_, ebSim);
  std::map<uint32_t, double> ebSimById;
  if (ebSim.isValid())
    for (const auto& hit : *ebSim)
      ebSimById[hit.id()] += hit.energy();

  edm::Handle<edm::PCaloHitContainer> hcalSim;
  ev.getByToken(hcalSimHits_, hcalSim);
  std::map<uint32_t, double> hbSimById;
  if (hcalSim.isValid())
    for (const auto& hit : *hcalSim)
      if (HcalDetId(hit.id()).subdet() == HcalBarrel)
        hbSimById[hit.id()] += hit.energy();

  compare(ebSimById, ebRecoById, minEbSimEnergy_, eb_);
  // a much lower threshold for HCAL: the PCaloHit energy there is what the
  // scintillator absorbed, a hundred-odd times smaller than the energy the
  // reconstruction reports for it
  compare(hbSimById, hbRecoById, minHbSimEnergy_, hb_);

  edm::Handle<edm::SimTrackContainer> tracks;
  ev.getByToken(simTracks_, tracks);
  if (tracks.isValid())
    for (const auto& track : *tracks)
      if (track.genpartIndex() >= 0 && std::abs(track.type()) == 13) {
        ++muons_;
        totalMuonMomentum_ += track.momentum().P();
      }
}

void CaloEnergyResponse::endJob() {
  const double ebEfficiency =
      eb_.cellsWithDeposit ? double(eb_.cellsReconstructed) / double(eb_.cellsWithDeposit) : 0.0;
  const double hbEfficiency =
      hb_.cellsWithDeposit ? double(hb_.cellsReconstructed) / double(hb_.cellsWithDeposit) : 0.0;
  const double ebResponse = median(eb_.response);
  const double hbResponse = median(hb_.response);
  const double ebPerMuon = muons_ ? eb_.totalReco / double(muons_) : 0.0;
  const double hbPerMuon = muons_ ? hb_.totalReco / double(muons_) : 0.0;
  const double eOverP = totalMuonMomentum_ > 0.0 ? eb_.totalReco / totalMuonMomentum_ : 0.0;

  edm::LogWarning("CaloEnergyResponse")
      << "  ECAL barrel: " << eb_.cellsReconstructed << "/" << eb_.cellsWithDeposit
      << " cells with a deposit reconstructed (" << 100.0 * ebEfficiency
      << "%), median E_reco/E_sim = " << ebResponse;
  edm::LogWarning("CaloEnergyResponse")
      << "  HCAL barrel: " << hb_.cellsReconstructed << "/" << hb_.cellsWithDeposit << " cells ("
      << 100.0 * hbEfficiency << "%), median E_reco/E_sim = " << hbResponse
      << " (the sampling factor)";
  edm::LogWarning("CaloEnergyResponse")
      << "  per muon: " << ebPerMuon << " GeV in ECAL, " << hbPerMuon << " GeV in HCAL, over "
      << muons_ << " muons";
  edm::LogWarning("CaloEnergyResponse") << "  E(ECAL)/p = " << eOverP;

  if (eb_.cellsWithDeposit == 0)
    throw cms::Exception("NoDeposit")
        << "no ECAL barrel cell received a simulated energy deposit - the muons did not reach "
           "the calorimeter, or the SimHits are not being read";
  if (ebEfficiency < minEbEfficiency_)
    throw cms::Exception("LowEfficiency")
        << eb_.cellsReconstructed << " of " << eb_.cellsWithDeposit
        << " ECAL cells with a simulated deposit have a rec hit (" << 100.0 * ebEfficiency
        << "%), below the required " << 100.0 * minEbEfficiency_ << "%.";
  if (ebResponse < minEbResponse_ || ebResponse > maxEbResponse_)
    throw cms::Exception("WrongEnergy")
        << "the ECAL response is " << ebResponse << ", outside [" << minEbResponse_ << ", "
        << maxEbResponse_
        << "]. The crystal is the absorber and the detector, so the reconstructed energy should "
           "be the deposited one: a response away from unity is a calibration constant, a pulse "
           "shape or an amplitude fit that disagrees with the digitisation.";
  if (ebPerMuon < minEbMip_ || ebPerMuon > maxEbMip_)
    throw cms::Exception("WrongMipScale")
        << "a muon leaves " << ebPerMuon << " GeV in the ECAL barrel, outside [" << minEbMip_
        << ", " << maxEbMip_ << "] GeV.";
  if (eOverP > maxEOverP_)
    throw cms::Exception("NotAMip")
        << "E/p = " << eOverP << " exceeds " << maxEOverP_
        << ": the calorimeter is seeing something that showers, not a minimum-ionising particle.";
  if (hbResponse < minHbResponse_ || hbResponse > maxHbResponse_)
    throw cms::Exception("WrongEnergy")
        << "the HCAL response is " << hbResponse << ", outside [" << minHbResponse_ << ", "
        << maxHbResponse_
        << "]. It should be the sampling factor - the ratio of the energy the shower deposits in "
           "the brass to the fraction the scintillator sees - which the geometry fixes at around "
           "a hundred in the barrel.";

  edm::LogWarning("CaloEnergyResponse") << "calorimeter energy OK";
}

DEFINE_FWK_MODULE(CaloEnergyResponse);
