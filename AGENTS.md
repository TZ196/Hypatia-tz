# Project Rules

## ISL generation rules

- Never use `int(NUM_SATS_PER_ORB / 2)` as the default cross-plane ISL shift.
- Default `ISL_SHIFT` must be 0 unless explicitly configured.
- For each constellation, validate cross-plane ISLs by checking:
  - candidate cross-plane ISLs in `isls.txt`
  - active cross-plane ISLs after dynamic_state distance filtering
  - connected components of the satellite-only graph
  - cross-plane next-hops in fstate/path tracking
  - cross-plane bytes in `isl_utilization.csv`
- Different constellations may need different shift values. Use shift enumeration or nearest-neighbor geometry instead of guessing.
- Do not fix cross-plane traffic by changing post-processing statistics. Fix ISL candidate generation and dynamic routing.
