/*
 * Track path-level satellite traffic matrices.
 */

#include "satellite-path-monitor.h"

#include <algorithm>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>

#include "ns3/exp-util.h"
#include "ns3/log.h"
#include "ns3/simulator.h"
#include "ns3/tag.h"
#include "ns3/type-id.h"

namespace ns3 {

NS_LOG_COMPONENT_DEFINE ("SatellitePathMonitor");

class SatellitePathTag : public Tag
{
public:
  SatellitePathTag ()
    : m_pathId (0)
  {
  }

  static TypeId GetTypeId (void)
  {
    static TypeId tid = TypeId ("ns3::SatellitePathTag")
      .SetParent<Tag> ()
      .SetGroupName ("SatelliteNetwork")
      .AddConstructor<SatellitePathTag> ();
    return tid;
  }

  TypeId GetInstanceTypeId (void) const override
  {
    return GetTypeId ();
  }

  uint32_t GetSerializedSize (void) const override
  {
    return 8;
  }

  void Serialize (TagBuffer i) const override
  {
    i.WriteU64 (m_pathId);
  }

  void Deserialize (TagBuffer i) override
  {
    m_pathId = i.ReadU64 ();
  }

  void Print (std::ostream& os) const override
  {
    os << "path_id=" << m_pathId;
  }

  void SetPathId (uint64_t pathId)
  {
    m_pathId = pathId;
  }

  uint64_t GetPathId (void) const
  {
    return m_pathId;
  }

private:
  uint64_t m_pathId;
};

bool SatellitePathMonitor::s_enabled = false;
uint32_t SatellitePathMonitor::s_numSatellites = 0;
int64_t SatellitePathMonitor::s_intervalNs = 0;
uint64_t SatellitePathMonitor::s_numTimeBins = 0;
std::string SatellitePathMonitor::s_logsDir = "";
uint64_t SatellitePathMonitor::s_nextPathId = 1;
uint64_t SatellitePathMonitor::s_maxPathLengthSeen = 0;
uint64_t SatellitePathMonitor::s_satelliteReceiveEvents = 0;
uint64_t SatellitePathMonitor::s_pathTagCreations = 0;
uint64_t SatellitePathMonitor::s_singleSatellitePathObservations = 0;
uint64_t SatellitePathMonitor::s_transitPairObservations = 0;
uint64_t SatellitePathMonitor::s_nonAdjacentPairObservations = 0;
uint64_t SatellitePathMonitor::s_nonAdjacentBytes = 0;
std::unordered_map<uint64_t, std::vector<uint32_t> > SatellitePathMonitor::s_pathSatellites;
std::unordered_map<uint64_t, uint64_t> SatellitePathMonitor::s_pathFirstSeenBins;
std::vector<uint64_t> SatellitePathMonitor::s_pathLengthHistogram;
std::map<uint64_t, SatellitePathMonitor::Counter> SatellitePathMonitor::s_counters;

void
SatellitePathMonitor::Initialize (
    bool enabled,
    uint32_t numSatellites,
    int64_t intervalNs,
    int64_t simulationEndTimeNs,
    const std::string& logsDir)
{
  s_enabled = enabled;
  s_numSatellites = numSatellites;
  s_intervalNs = intervalNs;
  s_logsDir = logsDir;
  s_nextPathId = 1;
  s_maxPathLengthSeen = 0;
  s_satelliteReceiveEvents = 0;
  s_pathTagCreations = 0;
  s_singleSatellitePathObservations = 0;
  s_transitPairObservations = 0;
  s_nonAdjacentPairObservations = 0;
  s_nonAdjacentBytes = 0;
  s_pathSatellites.clear ();
  s_pathFirstSeenBins.clear ();
  s_pathLengthHistogram.clear ();
  s_counters.clear ();

  if (!s_enabled)
    {
      s_numTimeBins = 0;
      return;
    }

  NS_ABORT_MSG_IF (s_numSatellites == 0, "Satellite path monitor needs at least one satellite");
  NS_ABORT_MSG_IF (s_intervalNs <= 0, "satellite_path_tracking_interval_ns must be positive");
  NS_ABORT_MSG_IF (simulationEndTimeNs <= 0, "simulation_end_time_ns must be positive");

  s_numTimeBins = (simulationEndTimeNs + s_intervalNs - 1) / s_intervalNs;
  s_pathLengthHistogram = std::vector<uint64_t> (s_numSatellites + 1, 0);
  std::cout << "  > Satellite path tracking.. enabled, interval " << s_intervalNs
            << " ns, bins " << s_numTimeBins << std::endl;
}

bool
SatellitePathMonitor::IsEnabled (void)
{
  return s_enabled;
}

bool
SatellitePathMonitor::IsSatelliteNode (uint32_t nodeId)
{
  return s_enabled && nodeId < s_numSatellites;
}

void
SatellitePathMonitor::RecordSatelliteReceive (Ptr<Packet> packet, uint32_t satelliteId, uint64_t bytes)
{
  if (!IsSatelliteNode (satelliteId))
    {
      return;
    }

  uint64_t pathId = GetOrCreatePathId (packet);
  std::vector<uint32_t>& path = s_pathSatellites[pathId];
  s_satelliteReceiveEvents += 1;

  if (!path.empty () && path.back () == satelliteId)
    {
      return;
    }

  if (path.empty ())
    {
      s_pathFirstSeenBins[pathId] = CurrentTimeBin ();
    }

  uint32_t previousSatelliteId = path.empty () ? satelliteId : path.back ();
  for (uint32_t pathIndex = 0; pathIndex < path.size (); pathIndex++)
    {
      uint32_t fromSat = path[pathIndex];
      if (fromSat == satelliteId)
        {
          continue;
        }
      Increment (fromSat, satelliteId, bytes, false);
      s_transitPairObservations += 1;
      if (fromSat != previousSatelliteId)
        {
          s_nonAdjacentPairObservations += 1;
          s_nonAdjacentBytes += bytes;
        }
    }

  path.push_back (satelliteId);
  ObservePathLength (path.size ());
}

void
SatellitePathMonitor::RecordSatelliteToGroundSend (Ptr<Packet> packet, uint32_t satelliteId, uint64_t bytes)
{
  if (!IsSatelliteNode (satelliteId))
    {
      return;
    }

  uint64_t pathId = 0;
  if (!GetExistingPathId (packet, pathId))
    {
      return;
    }

  auto it = s_pathSatellites.find (pathId);
  if (it == s_pathSatellites.end ())
    {
      return;
    }

  if (it->second.size () == 1 && it->second[0] == satelliteId)
    {
      auto firstBinIt = s_pathFirstSeenBins.find (pathId);
      uint64_t timeBin = firstBinIt == s_pathFirstSeenBins.end () ? CurrentTimeBin () : firstBinIt->second;
      IncrementAtTimeBin (timeBin, satelliteId, satelliteId, bytes, false);
      s_singleSatellitePathObservations += 1;
    }

  s_pathSatellites.erase (it);
  s_pathFirstSeenBins.erase (pathId);
}

void
SatellitePathMonitor::RecordSatelliteDrop (Ptr<Packet> packet, uint32_t satelliteId, uint64_t bytes)
{
  if (!IsSatelliteNode (satelliteId))
    {
      return;
    }

  uint64_t pathId = 0;
  if (!GetExistingPathId (packet, pathId))
    {
      return;
    }

  auto it = s_pathSatellites.find (pathId);
  if (it == s_pathSatellites.end ())
    {
      return;
    }

  if (it->second.size () == 1 && it->second[0] == satelliteId)
    {
      auto firstBinIt = s_pathFirstSeenBins.find (pathId);
      uint64_t timeBin = firstBinIt == s_pathFirstSeenBins.end () ? CurrentTimeBin () : firstBinIt->second;
      IncrementAtTimeBin (timeBin, satelliteId, satelliteId, bytes, true);
    }
  else
    {
      for (uint32_t fromSat : it->second)
        {
          if (fromSat != satelliteId)
            {
              Increment (fromSat, satelliteId, bytes, true);
            }
        }
    }

  s_pathSatellites.erase (it);
  s_pathFirstSeenBins.erase (pathId);
}

void
SatellitePathMonitor::RecordGroundStationReceive (Ptr<Packet> packet)
{
  if (!s_enabled)
    {
      return;
    }
  EndPathIfPresent (packet);
}

bool
SatellitePathMonitor::GetExistingPathId (Ptr<const Packet> packet, uint64_t& pathId)
{
  SatellitePathTag tag;
  if (!packet->PeekPacketTag (tag))
    {
      return false;
    }
  pathId = tag.GetPathId ();
  return pathId != 0;
}

uint64_t
SatellitePathMonitor::GetOrCreatePathId (Ptr<Packet> packet)
{
  uint64_t pathId = 0;
  if (GetExistingPathId (packet, pathId))
    {
      return pathId;
    }

  pathId = s_nextPathId++;
  SatellitePathTag tag;
  tag.SetPathId (pathId);
  packet->AddPacketTag (tag);
  s_pathTagCreations += 1;
  return pathId;
}

void
SatellitePathMonitor::EndPathIfPresent (Ptr<Packet> packet)
{
  uint64_t pathId = 0;
  if (GetExistingPathId (packet, pathId))
    {
      s_pathSatellites.erase (pathId);
      s_pathFirstSeenBins.erase (pathId);
    }
}

void
SatellitePathMonitor::ObservePathLength (uint64_t pathLength)
{
  if (pathLength > s_maxPathLengthSeen)
    {
      s_maxPathLengthSeen = pathLength;
    }
  if (pathLength < s_pathLengthHistogram.size ())
    {
      s_pathLengthHistogram[pathLength] += 1;
    }
}

void
SatellitePathMonitor::Increment (uint32_t fromSat, uint32_t toSat, uint64_t bytes, bool isDrop)
{
  IncrementAtTimeBin (CurrentTimeBin (), fromSat, toSat, bytes, isDrop);
}

void
SatellitePathMonitor::IncrementAtTimeBin (
    uint64_t timeBin,
    uint32_t fromSat,
    uint32_t toSat,
    uint64_t bytes,
    bool isDrop)
{
  if (fromSat >= s_numSatellites || toSat >= s_numSatellites)
    {
      return;
    }

  if (timeBin >= s_numTimeBins)
    {
      return;
    }

  Counter& counter = s_counters[MatrixKey (timeBin, fromSat, toSat)];
  if (isDrop)
    {
      counter.dropBytes += bytes;
      counter.dropPackets += 1;
    }
  else
    {
      counter.bytes += bytes;
      counter.packets += 1;
    }
}

uint64_t
SatellitePathMonitor::CurrentTimeBin (void)
{
  int64_t nowNs = Simulator::Now ().GetNanoSeconds ();
  if (nowNs <= 0)
    {
      return 0;
    }
  return nowNs / s_intervalNs;
}

uint64_t
SatellitePathMonitor::MatrixKey (uint64_t timeBin, uint32_t fromSat, uint32_t toSat)
{
  return (timeBin * s_numSatellites + fromSat) * s_numSatellites + toSat;
}

void
SatellitePathMonitor::WriteCsvMatrices (void)
{
  if (!s_enabled)
    {
      return;
    }

  std::string baseDir = s_logsDir + "/sat_path_flow";
  std::string bytesDir = baseDir + "/bytes";
  std::string packetsDir = baseDir + "/packets";
  std::string dropBytesDir = baseDir + "/drop_bytes";
  std::string dropPacketsDir = baseDir + "/drop_packets";

  mkdir_if_not_exists (baseDir);
  mkdir_if_not_exists (bytesDir);
  mkdir_if_not_exists (packetsDir);
  mkdir_if_not_exists (dropBytesDir);
  mkdir_if_not_exists (dropPacketsDir);

  std::ofstream metadata (baseDir + "/metadata.txt");
  NS_ABORT_MSG_IF (!metadata.is_open (), "Could not open satellite path monitor metadata file");
  metadata << "num_satellites=" << s_numSatellites << std::endl;
  metadata << "num_time_bins=" << s_numTimeBins << std::endl;
  metadata << "interval_ns=" << s_intervalNs << std::endl;
  metadata << "layout=matrix[from_sat][to_sat]" << std::endl;
  metadata << "tracking_key=packet_tag_path_id" << std::endl;
  metadata << "tracking_point=satellite_receive" << std::endl;
  metadata << "semantics=receiver_monitor_expanded_to_all_earlier_current_satellite_pairs_single_satellite_paths_on_diagonal" << std::endl;
  metadata << "max_path_length_seen=" << s_maxPathLengthSeen << std::endl;
  metadata << "satellite_receive_events=" << s_satelliteReceiveEvents << std::endl;
  metadata << "path_tag_creations=" << s_pathTagCreations << std::endl;
  metadata << "single_satellite_path_observations=" << s_singleSatellitePathObservations << std::endl;
  metadata << "transit_pair_observations=" << s_transitPairObservations << std::endl;
  metadata << "non_adjacent_pair_observations=" << s_nonAdjacentPairObservations << std::endl;
  metadata << "non_adjacent_bytes=" << s_nonAdjacentBytes << std::endl;
  metadata << "open_packet_paths_at_finish=" << s_pathSatellites.size () << std::endl;
  WritePathLengthHistogram (metadata);
  metadata.close ();

  uint64_t matrixSize = static_cast<uint64_t> (s_numSatellites) * s_numSatellites;
  for (uint64_t t = 0; t < s_numTimeBins; t++)
    {
      std::vector<uint64_t> bytes (matrixSize, 0);
      std::vector<uint64_t> packets (matrixSize, 0);
      std::vector<uint64_t> dropBytes (matrixSize, 0);
      std::vector<uint64_t> dropPackets (matrixSize, 0);

      uint64_t firstKey = MatrixKey (t, 0, 0);
      uint64_t endKey = firstKey + matrixSize;
      for (auto it = s_counters.lower_bound (firstKey);
           it != s_counters.end () && it->first < endKey;
           ++it)
        {
          uint64_t matrixIndex = it->first - firstKey;
          bytes[matrixIndex] = it->second.bytes;
          packets[matrixIndex] = it->second.packets;
          dropBytes[matrixIndex] = it->second.dropBytes;
          dropPackets[matrixIndex] = it->second.dropPackets;
        }

      std::ostringstream filename;
      filename << "t_" << std::setw (6) << std::setfill ('0') << t << ".csv";
      WriteMetricMatrix (bytesDir, filename.str (), bytes);
      WriteMetricMatrix (packetsDir, filename.str (), packets);
      WriteMetricMatrix (dropBytesDir, filename.str (), dropBytes);
      WriteMetricMatrix (dropPacketsDir, filename.str (), dropPackets);
    }
}

void
SatellitePathMonitor::WriteMetricMatrix (
    const std::string& dir,
    const std::string& filename,
    const std::vector<uint64_t>& values)
{
  std::ofstream fs (dir + "/" + filename);
  NS_ABORT_MSG_IF (!fs.is_open (), "Could not open satellite path monitor matrix file");
  for (uint32_t row = 0; row < s_numSatellites; row++)
    {
      for (uint32_t col = 0; col < s_numSatellites; col++)
        {
          if (col > 0)
            {
              fs << ",";
            }
          fs << values[static_cast<uint64_t> (row) * s_numSatellites + col];
        }
      fs << std::endl;
    }
  fs.close ();
}

void
SatellitePathMonitor::WritePathLengthHistogram (std::ostream& metadata)
{
  metadata << "path_length_histogram=";
  bool first = true;
  for (uint32_t pathLength = 1; pathLength < s_pathLengthHistogram.size (); pathLength++)
    {
      uint64_t count = s_pathLengthHistogram[pathLength];
      if (count == 0)
        {
          continue;
        }
      if (!first)
        {
          metadata << ",";
        }
      metadata << pathLength << ":" << count;
      first = false;
    }
  metadata << std::endl;
}

} // namespace ns3
