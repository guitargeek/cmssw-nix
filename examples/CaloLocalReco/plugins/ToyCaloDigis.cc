// Toy calorimeter digi producer + local-reco checker: place one pulse on the
// EB crystal (ieta 1, iphi 1) and one on the HB cell (ieta 1, iphi 1, depth 1)
// and let the standard Ecal/Hcal reconstruction and the calo-tower creator
// run on them. Both cells belong to calo tower (1, 1), so the chain is only
// complete if the tower creator merges the two rec hits into a single tower
// with both EM and HAD energy.

#include "FWCore/Framework/interface/stream/EDProducer.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/Utilities/interface/Exception.h"

#include "DataFormats/EcalDigi/interface/EcalDigiCollections.h"
#include "DataFormats/EcalDetId/interface/EBDetId.h"
#include "DataFormats/HcalDigi/interface/HcalDigiCollections.h"
#include "DataFormats/HcalDetId/interface/HcalDetId.h"
#include "DataFormats/EcalRecHit/interface/EcalRecHitCollections.h"
#include "DataFormats/HcalRecHit/interface/HcalRecHitCollections.h"
#include "DataFormats/CaloTowers/interface/CaloTowerCollection.h"
#include "FWCore/Framework/interface/ESHandle.h"
#include "Geometry/CaloGeometry/interface/CaloGeometry.h"
#include "Geometry/Records/interface/CaloGeometryRecord.h"
#include "DataFormats/EcalDetId/interface/EcalSubdetector.h"
#include "DataFormats/HcalDetId/interface/HcalSubdetector.h"
#include "DataFormats/CaloTowers/interface/CaloTowerDetId.h"

class ToyCaloDigiProducer : public edm::stream::EDProducer<> {
public:
  explicit ToyCaloDigiProducer(const edm::ParameterSet&) {
    produces<EBDigiCollection>();
    produces<EEDigiCollection>();
    produces<HBHEDigiCollection>();
    produces<QIE11DigiCollection>();
  }

  void produce(edm::Event& event, const edm::EventSetup&) override {
    // 2x2 block of EB crystals in tower (1, 1): 10 MGPA samples at gain 12
    // (gainId 1), pedestal ~200 ADC, pulse peaking at sample 5. A single
    // crystal would be flagged as a spike (kWeird) by the swiss-cross
    // topology check and excluded from the calo towers.
    // (crystal iphi 11-15 belongs to tower iphi 1: the barrel crystal
    // numbering is offset by 70 crystals with respect to the towers)
    auto ebDigis = std::make_unique<EBDigiCollection>();
    const int pulse[10] = {0, 0, 0, 0, 80, 400, 310, 180, 90, 40};
    unsigned nEb = 0;
    for (int ieta = 1; ieta <= 2; ++ieta)
      for (int iphi = 11; iphi <= 12; ++iphi) {
        ebDigis->push_back(EBDetId(ieta, iphi).rawId());
        EBDataFrame ebFrame((*ebDigis)[nEb++]);
        const int scale = (ieta == 1 && iphi == 11) ? 1 : 2;  // leading crystal + softer neighbors
        for (int i = 0; i < 10; ++i)
          ebFrame.setSample(i, EcalMGPASample(200 + pulse[i] / scale, 1));
      }
    const EBDetId ebId(1, 11);

    // HB cell in the same tower: 10 QIE8 samples, pedestal ~4 ADC with a
    // pulse in time slices 4/5
    auto hbheDigis = std::make_unique<HBHEDigiCollection>();
    const HcalDetId hbId(HcalBarrel, 1, 1, 1);
    hbheDigis->push_back(HBHEDataFrame(hbId));
    HBHEDataFrame& hbFrame = hbheDigis->back();
    hbFrame.setSize(10);
    hbFrame.setPresamples(4);
    const int adc[10] = {4, 4, 4, 4, 120, 80, 12, 6, 4, 4};
    for (int i = 0; i < 10; ++i)
      hbFrame.setSample(i, HcalQIESample(adc[i], i % 4, 1, 0));

    edm::LogPrint("ToyCaloDigiProducer")
        << "toy digis: 2x2 EB crystals around " << ebId.rawId() << " (ieta 1, iphi 11), "
        << "HB cell " << hbId.rawId() << " (ieta 1, iphi 1, depth 1)";

    event.put(std::move(ebDigis));
    event.put(std::move(hbheDigis));
    // the standard producers consume these collections even when empty
    event.put(std::make_unique<EEDigiCollection>());
    event.put(std::make_unique<QIE11DigiCollection>());
  }
};

// empty HO/HF rec-hit collections for the calo-tower creator, which reads
// all Hcal subdetectors
class EmptyHcalRecHitProducer : public edm::stream::EDProducer<> {
public:
  explicit EmptyHcalRecHitProducer(const edm::ParameterSet&) {
    produces<HORecHitCollection>();
    produces<HFRecHitCollection>();
  }
  void produce(edm::Event& event, const edm::EventSetup&) override {
    event.put(std::make_unique<HORecHitCollection>());
    event.put(std::make_unique<HFRecHitCollection>());
  }
};

class CaloLocalRecoChecker : public edm::one::EDAnalyzer<> {
public:
  explicit CaloLocalRecoChecker(const edm::ParameterSet& conf)
      : ebHitsToken_(consumes<EBRecHitCollection>(conf.getParameter<edm::InputTag>("ebRecHits"))),
        hbheHitsToken_(consumes<HBHERecHitCollection>(conf.getParameter<edm::InputTag>("hbheRecHits"))),
        towersToken_(consumes<CaloTowerCollection>(conf.getParameter<edm::InputTag>("towers"))),
        // the token form of EventSetup access: the legacy
        // setup.get<Record>().get(handle) is gone in 20_1, and this works in
        // both releases
        geomToken_(esConsumes<CaloGeometry, CaloGeometryRecord>()) {}

  void analyze(const edm::Event& event, const edm::EventSetup& setup) override {
    const CaloGeometry& geom = setup.getData(geomToken_);
    edm::LogPrint("CaloLocalRecoChecker")
        << "geometry: " << geom.getValidDetIds(DetId::Ecal, EcalBarrel).size()
        << " EB cells, " << geom.getValidDetIds(DetId::Hcal, HcalBarrel).size()
        << " HB cells, " << geom.getValidDetIds(DetId::Calo, CaloTowerDetId::SubdetId).size()
        << " tower cells";

    const auto& ebHits = event.get(ebHitsToken_);
    const auto& hbheHits = event.get(hbheHitsToken_);
    const auto& towers = event.get(towersToken_);

    edm::LogPrint("CaloLocalRecoChecker")
        << "EB rec hits: " << ebHits.size() << ", HBHE rec hits: " << hbheHits.size()
        << ", calo towers: " << towers.size();
    for (const auto& hit : ebHits)
      edm::LogPrint("CaloLocalRecoChecker")
          << "EB rec hit on " << hit.id().rawId() << ": energy = " << hit.energy()
          << " GeV, time = " << hit.time() << " ns, flags: good = "
          << hit.checkFlag(EcalRecHit::kGood) << " outOfTime = "
          << hit.checkFlag(EcalRecHit::kOutOfTime) << " weird = "
          << hit.checkFlag(EcalRecHit::kWeird);
    for (const auto& hit : hbheHits)
      edm::LogPrint("CaloLocalRecoChecker")
          << "HBHE rec hit on " << hit.id().rawId() << ": energy = " << hit.energy() << " GeV";
    for (const auto& tower : towers)
      edm::LogPrint("CaloLocalRecoChecker")
          << "calo tower (ieta " << tower.ieta() << ", iphi " << tower.iphi()
          << "): em = " << tower.emEnergy() << " GeV, had = " << tower.hadEnergy() << " GeV";

    if (ebHits.size() != 4 || hbheHits.size() != 1 || towers.size() != 1)
      throw cms::Exception("CaloLocalRecoChecker")
          << "expected four EB rec hits, one HBHE rec hit and one calo tower";
    if (!(ebHits.begin()->energy() > 0) || !(hbheHits.begin()->energy() > 0))
      throw cms::Exception("CaloLocalRecoChecker") << "expected positive rec-hit energies";
    if (!(towers.begin()->emEnergy() > 0) || !(towers.begin()->hadEnergy() > 0))
      throw cms::Exception("CaloLocalRecoChecker")
          << "expected the tower to have both EM and HAD energy";
  }

private:
  edm::EDGetTokenT<EBRecHitCollection> ebHitsToken_;
  edm::EDGetTokenT<HBHERecHitCollection> hbheHitsToken_;
  edm::EDGetTokenT<CaloTowerCollection> towersToken_;
  const edm::ESGetToken<CaloGeometry, CaloGeometryRecord> geomToken_;
};

#include "FWCore/Framework/interface/MakerMacros.h"
DEFINE_FWK_MODULE(ToyCaloDigiProducer);
DEFINE_FWK_MODULE(EmptyHcalRecHitProducer);
DEFINE_FWK_MODULE(CaloLocalRecoChecker);
