# 4. satgenpy API 速查

```python
import satgen

# === TLE 轨道生成 ===
satgen.generate_tles_from_scratch_manual(
    filename, num_orbits, num_sats_per_orbit, phase_diff,
    inclination_deg, eccentricity, arg_of_perigee_deg,
    mean_motion_rev_per_day)

# === 地面站 ===
satgen.extend_ground_stations(input_basic, output_extended)
stations = satgen.read_ground_stations_extended(filename)

# === 星间链路 ===
satgen.generate_plus_grid_isls(filename, num_orbits, num_sats_per_orbit,
                                isl_shift=0, idx_offset=0)
satgen.generate_empty_isls(filename)

# === GSL 接口 ===
satgen.generate_simple_gsl_interfaces_info(
    filename, num_sats, num_gs, gsl_if_per_sat, gsl_if_per_gs,
    sat_max_agg_bw, gs_max_agg_bw)

# === 描述文件 ===
satgen.generate_description(filename, max_gsl_length_m, max_isl_length_m)

# === 动态状态（转发表 + GSL 带宽） ===
satgen.help_dynamic_state(base_dir, num_threads, name,
    time_step_ms, duration_s, max_gsl_length_m, max_isl_length_m,
    dynamic_state_algorithm, regeneration_flag)

# === 后分析 ===
satgen.print_routes_and_rtt(...)
satgen.analyze_rtt(...)
satgen.analyze_time_step_path(...)
```
