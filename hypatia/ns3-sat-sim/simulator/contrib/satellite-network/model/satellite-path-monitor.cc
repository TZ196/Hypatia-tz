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

namespace ns3 {

NS_LOG_COMPONENT_DEFINE ("SatellitePathMonitor");
NS_OBJECT_ENSURE_REGISTERED (SatellitePathPacketTag);

bool SatellitePathMonitor::s_enabled = false;
uint32_t SatellitePathMonitor::s_numSatellites = 0;
int64_t SatellitePathMonitor::s_intervalNs = 0;
uint64_t SatellitePathMonitor::s_numTimeBins = 0;
std::string SatellitePathMonitor::s_logsDir = "";
uint64_t SatellitePathMonitor::s_nextPathId = 1;
std::unordered_map<uint64_t, std::vector<uint32_t> > SatellitePathMonitor::s_pathSatellites;
std::map<uint64_t, SatellitePathMonitor::Counter> SatellitePathMonitor::s_counters;

TypeId
SatellitePathPacketTag::GetTypeId (void)
{
  static TypeId tid = TypeId ("ns3::SatellitePathPacketTag")
    .SetParent<Tag> ()
    .SetGroupName ("SatelliteNetwork")
    .AddConstructor<SatellitePathPacketTag> ();
  return tid;
}

TypeId
SatellitePathPacketTag::GetInstanceTypeId (void) const
{
  return GetTypeId ();
}

uint32_t
SatellitePathPacketTag::GetSerializedSize (void) const
{
  return 8;
}

void
SatellitePathPacketTag::Serialize (TagBuffer i) const
{
  i.WriteU64 (m_pathId);
}

void
SatellitePathPacketTag::Deserialize (TagBuffer i)
{
  m_pathId = i.ReadU64 ();
}

void
SatellitePathPacketTag::Print (std::ostream &os) const
{
  os << "path_id=" << m_pathId;
}

void
SatellitePathPacketTag::SetPathId (uint64_t pathId)
{
  m_pathId = pathId;
}

uint64_t
SatellitePathPacketTag::GetPathId (void) const
{
  return m_pathId;
}

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
  s_pathSatellites.clear ();
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

  uint64_t pathId = EnsurePathId (packet);
  std::vector<uint32_t>& path = s_pathSatellites[pathId];

  for (uint32_t fromSat : path)
    {
      if (fromSat != satelliteId)
        {
          Increment (fromSat, satelliteId, bytes, false);
        }
    }

  if (std::find (path.begin (), path.end (), satelliteId) == path.end ())
    {
      path.push_back (satelliteId);
    }
}

void
SatellitePathMonitor::RecordSatelliteDrop (Ptr<Packet> packet, uint32_t satelliteId, uint64_t bytes)
{
  if (!IsSatelliteNode (satelliteId))
    {
      return;
    }

  uint64_t pathId;
  if (!GetPathId (packet, pathId))
    {
      return;
    }

  auto it = s_pathSatellites.find (pathId);
  if (it == s_pathSatellites.end ())
    {
      return;
    }

  for (uint32_t fromSat : it->second)
    {
      if (fromSat != satelliteId)
        {
          Increment (fromSat, satelliteId, bytes, true);
        }
    }

  s_pathSatellites.erase (it);
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

uint64_t
SatellitePathMonitor::EnsurePathId (Ptr<Packet> packet)
{
  uint64_t pathId;
  if (GetPathId (packet, pathId))
    {
      if (s_pathSatellites.find (pathId) == s_pathSatellites.end ())
        {
          s_pathSatellites[pathId] = std::vector<uint32_t> ();
        }
      return pathId;
    }

  pathId = s_nextPathId++;
  SatellitePathPacketTag tag;
  tag.SetPathId (pathId);
  packet->AddPacketTag (tag);
  s_pathSatellites[pathId] = std::vector<uint32_t> ();
  return pathId;
}

bool
SatellitePathMonitor::GetPathId (Ptr<Packet> packet, uint64_t& pathId)
{
  SatellitePathPacketTag tag;
  if (!packet->PeekPacketTag (tag))
    {
      return false;
    }
  pathId = tag.GetPathId ();
  return true;
}

void
SatellitePathMonitor::EndPathIfPresent (Ptr<Packet> packet)
{
  uint64_t pathId;
  if (!GetPathId (packet, pathId))
    {
      return;
    }
  s_pathSatellites.erase (pathId);
  SatellitePathPacketTag tag;
  packet->RemovePacketTag (tag);
}

void
SatellitePathMonitor::Increment (uint32_t fromSat, uint32_t toSat, uint64_t bytes, bool isDrop)
{
  if (fromSat >= s_numSatellites || toSat >= s_numSatellites || fromSat == toSat)
    {
      return;
    }

  uint64_t timeBin = CurrentTimeBin ();
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

} // namespace ns3
