# SPEC: Dropsonde vs Satellite Comparison

## Purpose
This file is the persistent source of truth for the dropsonde-vs-satellite task so future Copilot sessions do not lose the detailed requirements.

## Primary Goal
Create a workflow that compares dropsonde-derived vertical velocity profiles with satellite precipitation for the same date, time, and location, using dropsonde information as the reference for time matching and spatial cropping.

## Priority Order
1. Clean and organize the project structure first.
2. Then implement the dropsonde vs IMERG and EarthCARE comparison workflow.

## Scope
The final comparison figure must contain three panels:
1. Left panel: dropsonde vertical velocity profile.
2. Top-right panel: IMERG precipitation.
3. Bottom-right panel: EarthCARE precipitation.

## Figure Requirements
### Title
- Use this format:
  - `Vertical Velocity Profile vs Satellite Precipitation <date and time>`
- If needed, a more explicit variant is acceptable:
  - `Vertical Velocity Profile vs IMERG and EarthCARE Precipitation <date and time>`

### Left Panel: Dropsonde Vertical Velocity
- Plot dropsonde-derived vertical velocity profile.
- X-axis label must use omega notation and units:
  - `Vertical Velocity $\omega$ (Pa s$^{-1}$)`
- Y-axis label must be:
  - `Pressure (Pa)`
- Do not use hPa on this figure.
- Color convention:
  - top-heavy = red
  - bottom-heavy = blue

### Satellite Panels
- Both right-side panels must use precipitation for comparison.
- Use the color palette:
  - `WhiteBlueGreenYellowRed`
- Place the satellite color bar horizontally at the bottom.
- Satellite crops must be based on dropsonde location/geometry so the map covers the full dropsonde circle or analysis area.

## IMERG Requirements
- Use [satellite_preprocessing.py](../satellite_preprocessing.py) to support downloading broader GPM/IMERG coverage.
- The current domain is too small and must be widened to ensure cropped products fully cover the dropsonde-based area.
- Required download domain:
  - Latitude: `0N to 30N`
  - Longitude: `70W to 0W`
- The goal is not just broader download coverage; the final plot must still crop to the dropsonde-based area for each case.

## EarthCARE Requirements
- Add EarthCARE download support.
- Use [GPortalUserManual_en.pdf](../GPortalUserManual_en.pdf) as the implementation reference.
- Assume the user already has a G-Portal account.
- Write the code so credentials or account-specific values can be edited later by the user.
- For comparison with IMERG, use precipitation for EarthCARE as well.

## Data Matching Rules
- Match all products using dropsonde data as the reference.
- Use the same event date and time for the dropsonde profile and both satellite products.
- Use the dropsonde location to determine the crop region for the satellite maps.

## Data Storage Requirements
- Project data should be placed under `/g/data/k10/zr7147/`.
- Do not treat the repository root as the main location for large datasets.
- Use the repository mainly for code, notebooks, lightweight metadata, and documentation.
- Keep raw downloads, intermediate processed datasets, and larger output products organized under `/g/data/k10/zr7147/`.
- When cleaning the project structure, reflect this separation clearly so storage paths are consistent.

## Code Organization Requirements
- Clean the repository structure before adding major new functionality.
- Group code and outputs into clear locations so the project is easier to navigate.
- Keep scripts, notebooks, raw data, processed data, and generated figures separated where practical.
- Avoid leaving outputs mixed with source files at the top level.

## Expected Deliverables
1. Cleaner project structure.
2. Updated IMERG download/preprocessing support in [satellite_preprocessing.py](../satellite_preprocessing.py).
3. New EarthCARE download support based on [GPortalUserManual_en.pdf](../GPortalUserManual_en.pdf).
4. A plotting workflow that generates the three-panel comparison figure.
5. Consistent labels, units, colors, and color bar placement matching this spec.

## Acceptance Checklist
- Repository structure is cleaner and more organized.
- Dropsonde panel is on the left.
- IMERG is on the top-right.
- EarthCARE is on the bottom-right.
- Title includes the event date and time.
- Dropsonde x-axis uses omega and `Pa s^-1` units.
- Dropsonde y-axis uses `Pressure (Pa)` and not hPa.
- Top-heavy profiles use red.
- Bottom-heavy profiles use blue.
- IMERG download domain covers `0N to 30N`, `70W to 0W`.
- Satellite plots are cropped using dropsonde-based spatial context.
- Satellite color map is `WhiteBlueGreenYellowRed`.
- Satellite color bar is horizontal and at the bottom.

## Short Prompt To Reuse
Paste this into Copilot Chat:

```text
Read notes/SPEC_sonde_vs_satellite.md first and follow it as the source of truth for this task. Start by cleaning the project structure and organizing code, data, and outputs, with project data stored under /g/data/k10/zr7147/. Then implement the dropsonde vs IMERG vs EarthCARE comparison workflow exactly as specified there.
```

## Expanded Prompt To Reuse
If more detail is needed, use this version:

```text
Read notes/SPEC_sonde_vs_satellite.md first and use it as the source of truth. Do not skip details from the spec. First clean and reorganize the project structure so code, notebooks, data, and outputs are separated clearly, with project data stored under /g/data/k10/zr7147/ instead of the repo root. Then implement the dropsonde-based comparison workflow: left panel is vertical velocity profile, top-right is IMERG precipitation, bottom-right is EarthCARE precipitation. Match by dropsonde date/time/location, crop the satellite data using the dropsonde-based area, update satellite_preprocessing.py to download wider IMERG coverage for 0N to 30N and 70W to 0W, and add EarthCARE download support using GPortalUserManual_en.pdf.
```