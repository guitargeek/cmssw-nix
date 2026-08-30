// Where did the muons come from, and does the reconstruction agree?
//
// The gun fires its two muons from a single point, smeared over the 2018 beam
// spot, and Geant4 records that point as the primary SimVertex. The vertex
// producer fits the reconstructed tracks back to a common origin. Comparing
// the two tests something none of the earlier measurements do: not where a
// hit is, nor how fast the particle was going, but whether the trajectories
// extrapolate back to a consistent point.
//
// That makes it sensitive to things a momentum residual is not. Tracks with
// correct momenta can still be built from hits with a systematically wrong
// position along the beam, or be extrapolated with a wrong material budget,
// and the vertex is where those show up - z especially, since the tracker
// measures z far less precisely than r-phi.
//
// Two tracks is a thin vertex. The resolution here is therefore much worse
// than the tens of microns a real collision vertex achieves with dozens of
// tracks, and the assertion is set accordingly - it is checking that the
// vertex is reconstructed and lands on the right spot, not that it is precise.
#include <algorithm>
#include <cmath>
#include <vector>

#include "DataFormats/VertexReco/interface/Vertex.h"
#include "DataFormats/VertexReco/interface/VertexFwd.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/Utilities/interface/EDGetToken.h"
#include "FWCore/Utilities/interface/Exception.h"
#include "FWCore/Utilities/interface/InputTag.h"
#include "SimDataFormats/Vertex/interface/SimVertexContainer.h"

class VertexResolution : public edm::one::EDAnalyzer<> {
public:
  explicit VertexResolution(const edm::ParameterSet&);
  void analyze(const edm::Event&, const edm::EventSetup&) override;
  void endJob() override;

private:
  const edm::EDGetTokenT<reco::VertexCollection> vertices_;
  const edm::EDGetTokenT<edm::SimVertexContainer> simVertices_;
  const double maxMedianTransverse_;
  const double maxMedianLongitudinal_;
  const double minEfficiency_;

  std::vector<double> dxy_, dz_;
  unsigned long events_ = 0;
  unsigned long found_ = 0;
  unsigned long totalVertices_ = 0;
  unsigned long fakeVertices_ = 0;

  static double median(std::vector<double> v) {
    if (v.empty())
      return 0.0;
    std::sort(v.begin(), v.end());
    return v[v.size() / 2];
  }
};

VertexResolution::VertexResolution(const edm::ParameterSet& ps)
    : vertices_(consumes<reco::VertexCollection>(ps.getParameter<edm::InputTag>("vertices"))),
      simVertices_(consumes<edm::SimVertexContainer>(ps.getParameter<edm::InputTag>("simVertices"))),
      maxMedianTransverse_(ps.getParameter<double>("maxMedianTransverse")),
      maxMedianLongitudinal_(ps.getParameter<double>("maxMedianLongitudinal")),
      minEfficiency_(ps.getParameter<double>("minEfficiency")) {}

void VertexResolution::analyze(const edm::Event& ev, const edm::EventSetup&) {
  ++events_;

  edm::Handle<edm::SimVertexContainer> sims;
  ev.getByToken(simVertices_, sims);
  if (!sims.isValid() || sims->empty())
    throw cms::Exception("NoSimVertices") << "no SimVertex collection - the simulation "
                                          << "half of this chain did not run";
  // the production vertex of the gun: the one no track produced
  const SimVertex* primary = nullptr;
  for (const auto& sv : *sims) {
    if (sv.parentIndex() < 0) {
      primary = &sv;
      break;
    }
  }
  if (!primary)
    throw cms::Exception("NoPrimarySimVertex") << "every SimVertex has a parent track";

  edm::Handle<reco::VertexCollection> vertices;
  ev.getByToken(vertices_, vertices);
  if (!vertices.isValid())
    throw cms::Exception("NoVertices") << "the vertex collection is not in the event";

  totalVertices_ += vertices->size();
  for (const auto& v : *vertices)
    if (v.isFake())
      ++fakeVertices_;

  // the first valid vertex is the one the producer ranks highest
  for (const auto& v : *vertices) {
    if (v.isFake() || !v.isValid())
      continue;
    ++found_;
    dxy_.push_back(std::hypot(v.x() - primary->position().x(), v.y() - primary->position().y()));
    dz_.push_back(std::abs(v.z() - primary->position().z()));
    break;
  }
}

void VertexResolution::endJob() {
  const double eff = events_ ? double(found_) / double(events_) : 0.0;
  const double mxy = median(dxy_);
  const double mz = median(dz_);

  edm::LogWarning("VertexResolution")
      << "found a primary vertex in " << found_ << "/" << events_ << " events (" << 100.0 * eff
      << "%), median transverse offset " << 1e4 * mxy << " um, median |dz| " << 1e4 * mz
      << " um  [" << totalVertices_ << " vertices in the collection, " << fakeVertices_
      << " of them fake]";

  if (events_ == 0)
    throw cms::Exception("NoEvents") << "no events were processed";
  if (found_ == 0)
    throw cms::Exception("NoVertexReconstructed")
        << "not one event yielded a valid primary vertex, though the tracks were "
        << "reconstructed. The vertex producer's track selection is the place to look - "
        << "in particular the impact-parameter cut, which is taken with respect to the "
        << "beam spot and so depends on the beam spot matching the one used in simulation.";
  if (eff < minEfficiency_)
    throw cms::Exception("LowEfficiency")
        << "a primary vertex was found in only " << 100.0 * eff << "% of events, required "
        << 100.0 * minEfficiency_ << "%";
  if (mxy > maxMedianTransverse_)
    throw cms::Exception("BadTransversePosition")
        << "median transverse offset is " << 1e4 * mxy << " um, required below "
        << 1e4 * maxMedianTransverse_ << " um";
  if (mz > maxMedianLongitudinal_)
    throw cms::Exception("BadLongitudinalPosition")
        << "median |dz| is " << 1e4 * mz << " um, required below " << 1e4 * maxMedianLongitudinal_
        << " um. The tracks extrapolate back to the wrong place along the beam, which "
        << "positions and momenta alone would not have shown.";

  edm::LogWarning("VertexResolution") << "primary vertex OK";
}

DEFINE_FWK_MODULE(VertexResolution);
