// An HCAL electronics map with real VME readout addresses, for the packer.
//
// The electronics map says where each HCAL channel sits in the readout: which
// DCC (one FED each), which HTR card (crate, slot, top or bottom half), which
// spigot of the DCC, which of the card's eight fibers and which of the three
// channels on the fiber. The packer walks those addresses to lay the digis
// out in FED buffers, and the unpacker walks them back.
//
// The map the hardcoded conditions provide has none of that. Every channel
// gets a running number in the uTCA id space, which is all the
// reconstruction needs (it only maps channels to calibration constants) and
// nothing the packers can use. The real maps live in the conditions
// database, and the text file the release's fake-conditions configuration
// names is no longer distributed.
//
// So this builds one with the shape of the VME readout of Run 1 and 2: 32
// DCCs (FEDs 700-731) of 15 spigots, 8 fibers per spigot, 3 channels per
// fiber - 11520 addresses, which is exactly the number of HB, HE and HO
// channels. They are filled in the order the topology enumerates the
// channels, so this is not the detector's actual cabling; it is a valid one,
// which is what a round trip through the raw format needs. Each spigot is
// one half of one HTR card, the way the hardware is wired: the packer writes
// the card's crate and slot once per spigot, from any of its channels.
#include <memory>

#include "CondFormats/DataRecord/interface/HcalElectronicsMapRcd.h"
#include "CondFormats/HcalObjects/interface/HcalElectronicsMap.h"
#include "DataFormats/HcalDetId/interface/HcalDetId.h"
#include "DataFormats/HcalDetId/interface/HcalElectronicsId.h"
#include "FWCore/Framework/interface/ESProducer.h"
#include "FWCore/Framework/interface/ModuleFactory.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/Utilities/interface/ESGetToken.h"
#include "FWCore/Utilities/interface/Exception.h"
#include "Geometry/CaloTopology/interface/HcalTopology.h"
#include "Geometry/Records/interface/HcalRecNumberingRecord.h"

class HcalSyntheticVMEMap : public edm::ESProducer {
public:
  explicit HcalSyntheticVMEMap(const edm::ParameterSet&) {
    topology_ = setWhatProduced(this).consumes();
  }

  std::unique_ptr<HcalElectronicsMap> produce(const HcalElectronicsMapRcd& rcd) {
    const auto& topology = rcd.get(topology_);
    static constexpr int kDCCs = 32, kSpigots = 15, kFibers = 8, kChannels = 3;
    static constexpr int kPerSpigot = kFibers * kChannels;

    HcalElectronicsMapAddons::Helper helper;
    int n = 0;
    for (int det : {HcalBarrel, HcalEndcap, HcalOuter}) {
      for (int eta = -HcalDetId::kHcalEtaMask2; eta <= int(HcalDetId::kHcalEtaMask2); ++eta) {
        for (int phi = 0; phi <= int(HcalDetId::kHcalPhiMask2); ++phi) {
          for (int depth = 1; depth <= topology.maxDepth(); ++depth) {
            HcalDetId cell(HcalSubdetector(det), eta, phi, depth);
            if (!topology.valid(cell))
              continue;
            const int spigotIndex = n / kPerSpigot;  // over all DCCs
            const int dcc = spigotIndex / kSpigots, spigot = spigotIndex % kSpigots;
            const int fiber = (n % kPerSpigot) / kChannels + 1, fiberChannel = n % kChannels;
            if (dcc >= kDCCs)
              throw cms::Exception("HcalSyntheticVMEMap") << "more HB/HE/HO channels than VME readout addresses";
            HcalElectronicsId id(fiberChannel, fiber, spigot, dcc);
            // two spigots per HTR card (top and bottom), 8 cards per crate
            id.setHTR(spigotIndex / 16, 2 + (spigotIndex / 2) % 8, spigotIndex % 2);
            helper.mapEId2chId(id, cell);
            ++n;
          }
        }
      }
    }
    return std::make_unique<HcalElectronicsMap>(helper);
  }

private:
  edm::ESGetToken<HcalTopology, HcalRecNumberingRecord> topology_;
};

DEFINE_FWK_EVENTSETUP_MODULE(HcalSyntheticVMEMap);
