// Probes the CMS magnetic field at a handful of points and checks the values
// against the ones the real map is known to have. Used to validate the
// volume-based field engine: the field volumes come from the XML geometry and
// the field values themselves from the interpolation grid tables, so a wrong
// or missing table shows up here as an out-of-range value rather than as a
// subtly wrong track fit somewhere downstream.

#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/Utilities/interface/Exception.h"

#include "MagneticField/Engine/interface/MagneticField.h"
#include "MagneticField/Records/interface/IdealMagneticFieldRecord.h"

class MagneticFieldProbe : public edm::one::EDAnalyzer<> {
public:
  explicit MagneticFieldProbe(const edm::ParameterSet& conf)
      : fieldToken_(esConsumes<MagneticField, IdealMagneticFieldRecord>()),
        points_(conf.getParameter<std::vector<edm::ParameterSet>>("points")) {}

  void analyze(const edm::Event&, const edm::EventSetup& setup) override {
    const MagneticField& field = setup.getData(fieldToken_);

    for (const auto& p : points_) {
      const auto xyz = p.getParameter<std::vector<double>>("xyz");
      const GlobalPoint at(xyz[0], xyz[1], xyz[2]);
      const GlobalVector b = field.inTesla(at);

      edm::LogPrint("MagneticFieldProbe")
          << p.getParameter<std::string>("name") << " at (" << at.x() << ", " << at.y() << ", " << at.z()
          << ") cm: B = (" << b.x() << ", " << b.y() << ", " << b.z() << ") T, |B| = " << b.mag() << " T";

      const double bz = b.z();
      const double lo = p.getParameter<double>("bzMin");
      const double hi = p.getParameter<double>("bzMax");
      if (bz < lo || bz > hi)
        throw cms::Exception("MagneticFieldProbe")
            << "Bz = " << bz << " T at " << p.getParameter<std::string>("name") << " is outside the expected ["
            << lo << ", " << hi << "] T";
    }
  }

private:
  edm::ESGetToken<MagneticField, IdealMagneticFieldRecord> fieldToken_;
  std::vector<edm::ParameterSet> points_;
};

DEFINE_FWK_MODULE(MagneticFieldProbe);
