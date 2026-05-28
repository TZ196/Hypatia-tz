import argparse
import csv
import json
import math
import re
from pathlib import Path

import ephem


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a Cesium animation from a TLE file.")
    parser.add_argument("--tles", required=True, help="Path to tles.txt")
    parser.add_argument("--output", required=True, help="Path to output HTML")
    parser.add_argument("--ground-stations", help="Optional path to ground_stations.txt")
    parser.add_argument("--duration-s", type=int, default=600, help="Animation duration in seconds")
    parser.add_argument("--sample-step-s", type=int, default=10, help="Sampling step in seconds")
    parser.add_argument("--title", default="Satellite Animation", help="Page title")
    parser.add_argument("--gif-output", help="Optional path to offline GIF output")
    parser.add_argument("--fps", type=int, default=6, help="Frames per second for GIF output")
    return parser.parse_args()


def extract_cesium_token(top_html_path: Path) -> str:
    content = top_html_path.read_text(encoding="utf-8")
    match = re.search(r"Cesium\.Ion\.defaultAccessToken = '([^']+)'", content)
    if not match:
        raise RuntimeError("Cesium token not found in static_html/top.html")
    return match.group(1)


def read_tles(tles_path: Path):
    satellites = []
    with tles_path.open("r", encoding="utf-8") as f:
        first_line = f.readline().strip()
        num_orbits, sats_per_orbit = [int(v) for v in first_line.split()]
        while True:
            name = f.readline()
            if not name:
                break
            line1 = f.readline()
            line2 = f.readline()
            if not line1 or not line2:
                raise RuntimeError("Incomplete TLE entry in tles.txt")
            satellites.append(
                {
                    "name": name.strip(),
                    "sat": ephem.readtle(name, line1, line2),
                }
            )
    return num_orbits, sats_per_orbit, satellites


def read_ground_stations(ground_stations_path: Path):
    ground_stations = []
    with ground_stations_path.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            ground_stations.append(
                {
                    "gid": int(row[0]),
                    "name": row[1],
                    "lat_deg": float(row[2]),
                    "lon_deg": float(row[3]),
                    "alt_m": float(row[4]),
                }
            )
    return ground_stations


def generate_samples(satellites, duration_s: int, sample_step_s: int):
    samples_by_sat = []
    for sat_info in satellites:
        sat = sat_info["sat"]
        sat_samples = []
        for second in range(0, duration_s + 1, sample_step_s):
            timestamp = f"2000/01/01 00:00:{second:02d}.000000" if second < 60 else None
            if timestamp is None:
                minutes = second // 60
                seconds = second % 60
                timestamp = f"2000/01/01 00:{minutes:02d}:{seconds:02d}.000000"
            sat.compute(timestamp)
            sat_samples.append(
                {
                    "offset_s": second,
                    "lon_deg": round(float(sat.sublong) * 180.0 / ephem.pi, 6),
                    "lat_deg": round(float(sat.sublat) * 180.0 / ephem.pi, 6),
                    "alt_m": round(float(sat.elevation), 3),
                }
            )
        samples_by_sat.append(sat_samples)
    return samples_by_sat


def color_for_orbit(orbit_id: int):
    colors = [
        "Cesium.Color.CRIMSON",
        "Cesium.Color.DODGERBLUE",
        "Cesium.Color.FORESTGREEN",
        "Cesium.Color.DARKORANGE",
        "Cesium.Color.BLUEVIOLET",
        "Cesium.Color.DARKMAGENTA",
    ]
    return colors[orbit_id % len(colors)]


def build_html(token, title, satellites, samples_by_sat, ground_stations, num_orbits, sats_per_orbit, duration_s):
    sat_payload = []
    for idx, sat_info in enumerate(satellites):
        sat_payload.append(
            {
                "name": sat_info["name"],
                "orbit_id": idx // sats_per_orbit,
                "samples": samples_by_sat[idx],
            }
        )

    data_json = json.dumps(
        {
            "title": title,
            "duration_s": duration_s,
            "num_orbits": num_orbits,
            "sats_per_orbit": sats_per_orbit,
            "satellites": sat_payload,
            "ground_stations": ground_stations,
        },
        ensure_ascii=False,
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <script src="https://cesiumjs.org/releases/1.57/Build/Cesium/Cesium.js"></script>
  <link href="https://cesiumjs.org/releases/1.57/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
  <style>
    html, body, #cesiumContainer {{
      width: 100%;
      height: 100%;
      margin: 0;
      padding: 0;
      overflow: hidden;
      font-family: sans-serif;
    }}
    #legend {{
      position: absolute;
      top: 12px;
      left: 12px;
      z-index: 10;
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid #ccc;
      border-radius: 6px;
      padding: 10px 12px;
      line-height: 1.5;
      max-width: 360px;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <div id="legend">
    <div><strong>{title}</strong></div>
    <div>66 颗卫星，6 个轨道面，每面 11 颗卫星</div>
    <div>动画时长 600 秒，页面右下角时间轴可拖动播放</div>
    <div>彩色轨迹按轨道面区分，黄色点为地面站</div>
  </div>
  <div id="cesiumContainer"></div>
  <script>
    Cesium.Ion.defaultAccessToken = '{token}';
    const viewer = new Cesium.Viewer('cesiumContainer', {{
      shouldAnimate: true,
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      infoBox: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      selectionIndicator: true,
      animation: true,
      timeline: true
    }});

    const scene = viewer.scene;
    scene.backgroundColor = Cesium.Color.WHITE;
    viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString('#f7fbff');

    const DATA = {data_json};
    const start = Cesium.JulianDate.fromIso8601('2000-01-01T00:00:00Z');
    const stop = Cesium.JulianDate.addSeconds(start, DATA.duration_s, new Cesium.JulianDate());
    viewer.clock.startTime = start.clone();
    viewer.clock.stopTime = stop.clone();
    viewer.clock.currentTime = start.clone();
    viewer.clock.clockRange = Cesium.ClockRange.LOOP_STOP;
    viewer.clock.multiplier = 20;
    viewer.timeline.zoomTo(start, stop);

    function orbitColor(orbitId) {{
      const colors = [
        Cesium.Color.CRIMSON,
        Cesium.Color.DODGERBLUE,
        Cesium.Color.FORESTGREEN,
        Cesium.Color.DARKORANGE,
        Cesium.Color.BLUEVIOLET,
        Cesium.Color.DARKMAGENTA
      ];
      return colors[orbitId % colors.length];
    }}

    DATA.satellites.forEach((sat) => {{
      const position = new Cesium.SampledPositionProperty();
      sat.samples.forEach((sample) => {{
        const time = Cesium.JulianDate.addSeconds(start, sample.offset_s, new Cesium.JulianDate());
        const pos = Cesium.Cartesian3.fromDegrees(sample.lon_deg, sample.lat_deg, sample.alt_m);
        position.addSample(time, pos);
      }});
      position.setInterpolationOptions({{
        interpolationDegree: 1,
        interpolationAlgorithm: Cesium.LinearApproximation
      }});

      const color = orbitColor(sat.orbit_id);
      viewer.entities.add({{
        name: sat.name,
        availability: new Cesium.TimeIntervalCollection([
          new Cesium.TimeInterval({{ start: start, stop: stop }})
        ]),
        position: position,
        point: {{
          pixelSize: 7,
          color: color,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 1
        }},
        path: {{
          resolution: 10,
          material: color.withAlpha(0.35),
          width: 1.5,
          leadTime: 0,
          trailTime: DATA.duration_s
        }},
        label: {{
          text: sat.name,
          show: false
        }}
      }});
    }});

    DATA.ground_stations.forEach((gs) => {{
      viewer.entities.add({{
        name: gs.name,
        position: Cesium.Cartesian3.fromDegrees(gs.lon_deg, gs.lat_deg, gs.alt_m),
        point: {{
          pixelSize: 10,
          color: Cesium.Color.GOLD,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 1
        }},
        label: {{
          text: gs.name,
          font: '12px sans-serif',
          fillColor: Cesium.Color.BLACK,
          showBackground: true,
          backgroundColor: Cesium.Color.WHITE.withAlpha(0.8),
          pixelOffset: new Cesium.Cartesian2(0, -18)
        }}
      }});
    }});

    viewer.camera.flyTo({{
      destination: Cesium.Cartesian3.fromDegrees(0.0, 20.0, 23000000.0)
    }});
  </script>
</body>
</html>
"""


def spherical_to_cartesian(lon_deg, lat_deg, radius_m):
    lon = math.radians(lon_deg)
    lat = math.radians(lat_deg)
    x = radius_m * math.cos(lat) * math.cos(lon)
    y = radius_m * math.cos(lat) * math.sin(lon)
    z = radius_m * math.sin(lat)
    return x, y, z


def render_gif(gif_output_path: Path, title, samples_by_sat, ground_stations, sats_per_orbit, duration_s, fps):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import animation
    import numpy as np

    earth_radius_m = 6378135.0
    sat_cartesian = []
    for sat_samples in samples_by_sat:
        sat_frames = []
        for sample in sat_samples:
            sat_frames.append(
                spherical_to_cartesian(
                    sample["lon_deg"],
                    sample["lat_deg"],
                    earth_radius_m + sample["alt_m"],
                )
            )
        sat_cartesian.append(sat_frames)

    gs_cartesian = []
    for gs in ground_stations:
        gs_cartesian.append(
            spherical_to_cartesian(gs["lon_deg"], gs["lat_deg"], earth_radius_m + gs["alt_m"])
        )

    colors = ["crimson", "dodgerblue", "forestgreen", "darkorange", "blueviolet", "darkmagenta"]
    fig = plt.figure(figsize=(8, 8), dpi=120)
    ax = fig.add_subplot(111, projection="3d")

    u = np.linspace(0, 2 * np.pi, 60)
    v = np.linspace(0, np.pi, 30)
    earth_x = earth_radius_m * np.outer(np.cos(u), np.sin(v))
    earth_y = earth_radius_m * np.outer(np.sin(u), np.sin(v))
    earth_z = earth_radius_m * np.outer(np.ones(np.size(u)), np.cos(v))

    max_radius = earth_radius_m + 900000.0
    frame_count = len(samples_by_sat[0]) if samples_by_sat else 0

    def update(frame_idx):
        ax.clear()
        ax.plot_surface(earth_x, earth_y, earth_z, color="#9ecae1", alpha=0.35, linewidth=0)

        for sat_idx, sat_frames in enumerate(sat_cartesian):
            x, y, z = sat_frames[frame_idx]
            ax.scatter(
                [x], [y], [z],
                s=12,
                color=colors[(sat_idx // sats_per_orbit) % len(colors)],
                depthshade=False,
            )

        if gs_cartesian:
            ax.scatter(
                [p[0] for p in gs_cartesian],
                [p[1] for p in gs_cartesian],
                [p[2] for p in gs_cartesian],
                s=24,
                color="gold",
                edgecolors="black",
                depthshade=False,
            )

        ax.set_xlim(-max_radius, max_radius)
        ax.set_ylim(-max_radius, max_radius)
        ax.set_zlim(-max_radius, max_radius)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=22, azim=(frame_idx * 3) % 360)
        ax.set_axis_off()
        ax.set_title(f"{title}\\nT = {frame_idx * (duration_s // max(1, frame_count - 1))} s", pad=12)

    anim = animation.FuncAnimation(fig, update, frames=frame_count, interval=1000 / max(fps, 1))
    gif_output_path.parent.mkdir(parents=True, exist_ok=True)
    anim.save(gif_output_path, writer=animation.PillowWriter(fps=fps))
    plt.close(fig)


def main():
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    top_html_path = script_dir.parent / "static_html" / "top.html"
    token = extract_cesium_token(top_html_path)

    tles_path = Path(args.tles).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    num_orbits, sats_per_orbit, satellites = read_tles(tles_path)
    ground_stations = []
    if args.ground_stations:
        ground_stations = read_ground_stations(Path(args.ground_stations).resolve())

    samples_by_sat = generate_samples(
        satellites,
        duration_s=args.duration_s,
        sample_step_s=args.sample_step_s,
    )
    html = build_html(
        token,
        args.title,
        satellites,
        samples_by_sat,
        ground_stations,
        num_orbits,
        sats_per_orbit,
        args.duration_s,
    )
    output_path.write_text(html, encoding="utf-8")
    print(f"Wrote visualization to: {output_path}")

    if args.gif_output:
        gif_output_path = Path(args.gif_output).resolve()
        render_gif(
            gif_output_path,
            args.title,
            samples_by_sat,
            ground_stations,
            sats_per_orbit,
            args.duration_s,
            args.fps,
        )
        print(f"Wrote offline GIF to: {gif_output_path}")


if __name__ == "__main__":
    main()
