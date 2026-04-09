# Calculating MSE and GMS from the ORCESTRA Dropsonde Circle Dataset

## 1. Dataset Overview

The **BEACH Level-4** dropsonde dataset (`ORCESTRA_dropsondes_categorized.zarr`)
contains circle-averaged products derived from HALO dropsonde circles flown
during PERCUSION / ORCESTRA (Aug–Sep 2024) over the tropical Atlantic.

```
Path : /g/data/k10/zr7147/ORCESTRA_dropsondes_categorized.zarr
Circles : 89
Sondes : 1 058
Altitude levels : 1 460 (0–14 590 m, Δz = 10 m)
```

### 1.1 Dimensions

| Dimension  | Size  | Meaning |
|------------|-------|---------|
| `circle`   | 89    | One dropsonde circle flight |
| `altitude` | 1 460 | Evenly spaced height coordinate (m) |
| `sonde`    | 1 058 | Individual dropsonde profiles |

### 1.2 Variables Directly Relevant to MSE / GMS

The dataset already provides **circle-mean** and **gradient** fields computed
via the Gauss divergence theorem applied to the dropsonde ring. Below is the
complete inventory of variables needed for MSE and GMS calculations.

#### Circle-level Fields (circle × altitude)

| Variable | Units | Description |
|----------|-------|-------------|
| `ta_mean` | K | Circle-mean air temperature |
| `q_mean` | kg kg⁻¹ | Circle-mean specific humidity |
| `p_mean` | Pa | Circle-mean atmospheric pressure |
| `u_mean` | m s⁻¹ | Circle-mean zonal wind |
| `v_mean` | m s⁻¹ | Circle-mean meridional wind |
| `omega` | Pa s⁻¹ | **Area-averaged vertical pressure velocity** |
| `wvel` | m s⁻¹ | Area-averaged vertical velocity (w in m/s) |
| `div` | s⁻¹ | Area-averaged horizontal mass divergence |
| `vor` | s⁻¹ | Area-averaged relative vorticity |

#### Horizontal Gradient Fields (circle × altitude)

| Variable | Units | Description |
|----------|-------|-------------|
| `ta_dtadx` | K m⁻¹ | Zonal gradient of temperature |
| `ta_dtady` | K m⁻¹ | Meridional gradient of temperature |
| `q_dqdx` | kg kg⁻¹ m⁻¹ | Zonal gradient of specific humidity |
| `q_dqdy` | kg kg⁻¹ m⁻¹ | Meridional gradient of specific humidity |
| `p_dpdx` | Pa m⁻¹ | Zonal gradient of pressure |
| `p_dpdy` | Pa m⁻¹ | Meridional gradient of pressure |
| `u_dudx` | s⁻¹ | Zonal gradient of u-wind |
| `u_dudy` | s⁻¹ | Meridional gradient of u-wind |
| `v_dvdx` | s⁻¹ | Zonal gradient of v-wind |
| `v_dvdy` | s⁻¹ | Meridional gradient of v-wind |
| `theta_dthetadx` | K m⁻¹ | Zonal gradient of potential temperature |
| `theta_dthetady` | K m⁻¹ | Meridional gradient of potential temperature |

> All gradient fields also have `_std_error` companion variables.

#### Circle Metadata (per circle)

| Variable | Units | Description |
|----------|-------|-------------|
| `circle_lat` | °N | Circle centre latitude (3–18°N) |
| `circle_lon` | °E | Circle centre longitude (−59 to −21°E) |
| `circle_time` | datetime | UTC time of circle |
| `circle_radius` | m | Circle radius (59–134 km) |
| `sondes_per_circle` | — | Number of sondes (3–18) |
| `circle_altitude` | m | Aircraft altitude |
| `circle_id` | — | Circle identifier string |
| `category_evolutionary` | — | Profile shape category |
| `top_heaviness_angle` | ° | Top-heaviness metric (Singh & Li 2025) |

#### Individual Sonde Fields (sonde × altitude)

| Variable | Units | Description |
|----------|-------|-------------|
| `ta` | K | Air temperature |
| `q` | kg kg⁻¹ | Specific humidity |
| `p` | Pa | Atmospheric pressure |
| `u` | m s⁻¹ | Zonal wind |
| `v` | m s⁻¹ | Meridional wind |
| `theta` | K | Dry potential temperature |
| `rh` | 1 | Relative humidity |

---

## 2. How omega and div Are Already Computed in This Dataset

Understanding how `omega` and `div` were derived is critical before building
any MSE budget on top of them.

### 2.1 The Gauss Divergence Theorem (NOT Stokes' Theorem)

The Level-4 processing applies the **Gauss divergence theorem** to the
dropsonde ring at each altitude level:

$$\bar{D}(z) = \frac{1}{A} \oint_C \mathbf{v}_H \cdot \hat{n} \, dl$$

where $A = \pi R^2$ is the circle area and $\hat{n}$ is the outward unit
normal. This gives the **area-averaged horizontal divergence** $\bar{D}(z)$,
stored as `div`.

> **Important distinction:**
> - **Gauss' divergence theorem** relates the *normal* (radial) wind component
>   to *area-averaged divergence*. This is what gives us `div` and `omega`.
> - **Stokes' theorem** relates the *tangential* wind component to
>   *area-averaged vorticity*. This is what gives us `vor`.
>
> The old guide incorrectly labelled the whole procedure as "Stokes' theorem."

### 2.2 Recovering omega from div

The continuity equation in height coordinates is:

$$\frac{\partial w}{\partial z} = -D(z)$$

Integrating upward from the surface ($w(0) = 0$):

$$w(z) = -\int_0^z D(z') \, dz'$$

This gives `wvel` (m s⁻¹). Then `omega` is obtained via the hydrostatic
relation:

$$\omega \approx -\rho g \, w$$

or equivalently, using the mass continuity in pressure coordinates:

$$\frac{\partial \omega}{\partial p} = -D$$

Integrating downward from the tropopause ($\omega(p_t) = 0$):

$$\omega(p) = \int_{p}^{p_t} D(p') \, dp'$$

> **No factor of $g$** enters this equation — $D$ has units s⁻¹ and $dp'$
> has units Pa, producing $\omega$ in Pa s⁻¹ directly.

### 2.3 What You Cannot Do with a Single Circle

A single dropsonde ring gives you **area-averaged** fields. You **cannot**:

- Compute the radial gradient $\partial v_r / \partial r$ (requires data at
  multiple radii).
- Compute the radial MSE gradient $\partial h / \partial r$ (same reason).
- Compute pointwise divergence at individual locations within the circle.

You **can** compute:

- Area-averaged divergence $\bar{D}(z)$ → already provided as `div`.
- Area-averaged vertical velocity $\bar{\omega}(p)$ → already provided as `omega`.
- Horizontal gradients across the circle → provided as `_dqdx`, `_dtadx`, etc.
- Area-averaged vorticity → provided as `vor`.

---

## 3. Moist Static Energy (MSE) Calculation

### 3.1 Definition

$$h = C_p T + L_v q + g z$$

| Constant | Value | Unit |
|----------|-------|------|
| $C_p$ | 1005 | J kg⁻¹ K⁻¹ |
| $L_v$ | 2.501 × 10⁶ | J kg⁻¹ |
| $g$ | 9.81 | m s⁻² |

### 3.2 From the Dataset Variables

The dataset provides `ta_mean`, `q_mean`, and the `altitude` coordinate
directly on the (circle, altitude) grid. The circle-mean MSE profile is:

```python
Cp  = 1005.0          # J/kg/K
Lv  = 2.501e6         # J/kg
g   = 9.81            # m/s^2

h = Cp * ds.ta_mean + Lv * ds.q_mean + g * ds.altitude
```

This gives $h$ in J kg⁻¹ on the (circle, altitude) grid — 89 circles ×
1460 altitude levels.

### 3.3 Dry Static Energy (DSE)

$$s = C_p T + g z$$

```python
s = Cp * ds.ta_mean + g * ds.altitude
```

### 3.4 Column Integration

The mass-weighted column integral in pressure coordinates is:

$$\langle h \rangle = \frac{1}{g} \int_{p_t}^{p_s} h \, dp$$

Since the data is on a uniform **altitude** grid ($\Delta z = 10$ m), we
can equivalently use the hydrostatic approximation:

$$\langle h \rangle \approx \frac{1}{g} \sum_k h_k \, \Delta p_k$$

where $\Delta p_k = p_{mean,k} - p_{mean,k-1}$ (positive downward).

**Alternatively**, integrate in height coordinates using density:

$$\langle h \rangle = \int_0^{z_{top}} \rho(z) \, h(z) \, dz$$

where $\rho \approx p / (R_d T)$ with $R_d = 287$ J kg⁻¹ K⁻¹.

In practice, with the altitude grid at 10 m resolution:

```python
# Pressure-coordinate integration (using p_mean)
dp = ds.p_mean.diff('altitude')               # Pa (negative upward)
h_mid = h.rolling(altitude=2).mean().dropna('altitude')
column_h = (1.0 / g) * (h_mid * (-dp)).sum('altitude')  # J/m^2
```

### 3.5 Integration Bounds

Following Inoue & Back (2015) and Bui et al. (2016):

- **Standard bounds**: 1000 hPa (surface) to 100 hPa (tropopause)
- The dataset's `p_mean` typically covers ~167–1012 hPa
- Mask to altitudes where `p_mean` is between 10000 Pa and 100000 Pa

> **Sensitivity warning** (Bui et al. 2016): the sign and magnitude of
> vertical MSE advection is **highly sensitive** to the upper integration
> bound, especially for top-heavy profiles. Document your choice explicitly
> and consider testing 200, 150, and 100 hPa.

---

## 4. Vertical MSE Advection: $\langle \omega \, \partial h / \partial p \rangle$

This is the most important term for GMS and for understanding whether a
convective system is importing or exporting MSE.

### 4.1 Formula

$$\langle \omega \frac{\partial h}{\partial p} \rangle = \frac{1}{g} \int_{p_t}^{p_s} \omega(p) \frac{\partial h}{\partial p} dp$$

### 4.2 From Dataset Variables

`omega` (Pa s⁻¹) is already provided on (circle, altitude). We need
$\partial h / \partial p$, but $h$ and $\omega$ are on an altitude grid,
not a pressure grid. Two approaches:

#### Approach A: Work in altitude coordinates

Convert the integral to altitude coordinates using the hydrostatic relation
$dp = -\rho g \, dz$:

$$\langle \omega \frac{\partial h}{\partial p} \rangle = \frac{1}{g} \int_0^{z_{top}} \omega \frac{\partial h}{\partial p} (-\rho g) \, dz = -\int_0^{z_{top}} \rho \, \omega \frac{\partial h}{\partial p} \, dz$$

Since $\frac{\partial h}{\partial p} = \frac{\partial h}{\partial z} / \frac{\partial p}{\partial z} = \frac{\partial h/\partial z}{-\rho g}$:

$$\langle \omega \frac{\partial h}{\partial p} \rangle = \int_0^{z_{top}} \frac{\omega}{g} \frac{\partial h}{\partial z} \, dz$$

```python
dhdz = h.differentiate('altitude')            # J/kg per m
integrand = (ds.omega / g) * dhdz             # (Pa/s)(1/m·s²)(J/kg/m) → W/m² per m
vert_mse_adv = integrand.sum('altitude') * 10.0  # Δz = 10 m
```

#### Approach B: Interpolate to pressure levels

Interpolate both `omega` and `h` onto a regular pressure grid, then
integrate directly:

```python
import numpy as np
p_levels = np.arange(10000, 100100, 2500)  # 100–1000 hPa, 25 hPa steps

# For each circle, interpolate h and omega from altitude to pressure levels
# using p_mean as the coordinate mapping
```

This approach is more traditional but requires interpolation since the
altitude-to-pressure mapping varies by circle.

### 4.3 Physical Interpretation

| Sign | Meaning | Profile Shape |
|------|---------|---------------|
| $\langle \omega \partial h / \partial p \rangle > 0$ | MSE exported vertically | Top-heavy ω (deep convection) |
| $\langle \omega \partial h / \partial p \rangle < 0$ | MSE imported vertically | Bottom-heavy ω (shallow/congestus) |

This connects directly to the profile categories already in the dataset:

- **Top-Heavy** circles → positive vertical MSE advection → MSE export →
  stabilizing (Bui et al. 2016)
- **Bottom-Heavy** circles → negative vertical MSE advection → MSE import →
  destabilizing

---

## 5. Horizontal MSE Advection: $\langle \mathbf{v}_H \cdot \nabla_H h \rangle$

### 5.1 Formula

$$\langle \mathbf{v}_H \cdot \nabla_H h \rangle = \frac{1}{g} \int_{p_t}^{p_s} \left( u \frac{\partial h}{\partial x} + v \frac{\partial h}{\partial y} \right) dp$$

### 5.2 From Dataset Variables

The dataset provides the horizontal gradients of $T$ and $q$ directly:

$$\frac{\partial h}{\partial x} = C_p \frac{\partial T}{\partial x} + L_v \frac{\partial q}{\partial x}$$

$$\frac{\partial h}{\partial y} = C_p \frac{\partial T}{\partial y} + L_v \frac{\partial q}{\partial y}$$

Note: the $gz$ term vanishes in horizontal gradients on constant-$z$
surfaces (since $z$ is the altitude coordinate, $\partial z / \partial x |_z = 0$).

```python
dhdx = Cp * ds.ta_dtadx + Lv * ds.q_dqdx   # J/kg per m
dhdy = Cp * ds.ta_dtady + Lv * ds.q_dqdy   # J/kg per m

h_horiz_adv = ds.u_mean * dhdx + ds.v_mean * dhdy   # J/kg/s per altitude level
```

Then column-integrate (in altitude coordinates):

```python
Rd = 287.0                                       # J/kg/K
rho = ds.p_mean / (Rd * ds.ta_mean)              # kg/m^3

horiz_mse_adv = (rho * h_horiz_adv).sum('altitude') * 10.0 / ... # see §4.2
```

Or more precisely, mass-weight using $dp$:

$$\langle \mathbf{v}_H \cdot \nabla_H h \rangle = \frac{1}{g} \sum_k (u_k \frac{\partial h}{\partial x}\bigg|_k + v_k \frac{\partial h}{\partial y}\bigg|_k) \Delta p_k$$

### 5.3 Key Advantage of This Dataset

Unlike the old guide's calculation (which incorrectly tried to compute
$\partial h / \partial r$ from a single circle), **this dataset already
provides the horizontal gradients** (`ta_dtadx`, `ta_dtady`, `q_dqdx`,
`q_dqdy`) estimated from the dropsonde ring via regression. These are
area-representative gradients — not radial derivatives at one point.

---

## 6. Gross Moist Stability (GMS)

### 6.1 Definition (Inoue & Back 2015)

The **normalised GMS** is defined as:

$$G = \frac{-\langle \mathbf{v} \cdot \nabla h \rangle}{-\langle \mathbf{v} \cdot \nabla s \rangle}$$

where $s = C_p T + gz$ is DSE and $h = s + L_v q$ is MSE. The full
advection $\langle \mathbf{v} \cdot \nabla h \rangle$ includes both horizontal
and vertical components.

### 6.2 Practical Computation

In practice, the denominator uses DSE advection (which is dominated by
vertical advection under WTG):

$$G \approx \frac{-\langle \omega \, \partial h / \partial p \rangle - \langle \mathbf{v}_H \cdot \nabla_H h \rangle}{-\langle \omega \, \partial s / \partial p \rangle - \langle \mathbf{v}_H \cdot \nabla_H s \rangle}$$

### 6.3 Vertical GMS (Most Useful for Profile Shape Analysis)

For dropsonde circle data where the primary interest is how the omega
profile shape controls MSE export, the **vertical GMS** is most relevant:

$$G_V = \frac{-\langle \omega \, \partial h / \partial p \rangle}{-\langle \omega \, \partial s / \partial p \rangle}$$

This simplifies to:

$$G_V = 1 - \frac{\langle \omega \, \partial (L_v q) / \partial p \rangle}{\langle \omega \, \partial s / \partial p \rangle}$$

since $h = s + L_v q$.

```python
dsdz = (Cp * ds.ta_mean + g * ds.altitude).differentiate('altitude')
d_Lq_dz = (Lv * ds.q_mean).differentiate('altitude')

vert_dse_adv = ((ds.omega / g) * dsdz).sum('altitude') * 10.0
vert_Lq_adv  = ((ds.omega / g) * d_Lq_dz).sum('altitude') * 10.0

G_V = -(vert_dse_adv + vert_Lq_adv) / (-vert_dse_adv)
# equivalently:
# G_V = 1 - vert_Lq_adv / vert_dse_adv
```

### 6.4 Full GMS (Including Horizontal Advection)

$$G = \frac{-(\text{vert\_mse\_adv} + \text{horiz\_mse\_adv})}{-(\text{vert\_dse\_adv} + \text{horiz\_dse\_adv})}$$

where:

```python
dsdx = Cp * ds.ta_dtadx   # gz term vanishes on constant-z surfaces
dsdy = Cp * ds.ta_dtady

horiz_dse_adv = ds.u_mean * dsdx + ds.v_mean * dsdy
# ... then column-integrate
```

### 6.5 Sign Convention and Interpretation

| $G_V$ Value | Physical Meaning | Expected Profile |
|-------------|------------------|------------------|
| $G_V > 0$ | Column exports MSE vertically | Top-heavy ω |
| $G_V < 0$ | Column imports MSE vertically | Bottom-heavy ω |
| $G_V \approx 0$ | Minimal vertical MSE transport | Weak / suppressed |

This should correlate with the existing `category_evolutionary` labels:

- `Top-Heavy` / `Top-Heavy (Fully Ascending)` → $G_V > 0$
- `Bottom-Heavy` / `Bottom-Heavy (Fully Ascending)` → $G_V < 0$
- `Inactive / Suppressed` → $G_V \approx 0$

### 6.6 Critical GMS and Drying Efficiency (Inoue & Back 2015)

The **critical GMS** is:

$$G_C = \frac{F}{-\langle \mathbf{v} \cdot \nabla s \rangle}$$

where $F = \langle Q_R \rangle + S$ (radiative heating + surface fluxes).

**Not computable from dropsondes alone**: $Q_R$ and surface fluxes are not
measured by the dropsonde circle. These need to come from:

- ERA5 reanalysis (radiative fluxes, surface fluxes)
- CERES satellite products (TOA and surface radiation)
- Bulk flux parameterisation using SST + near-surface sonde observations

The **drying efficiency** $\Delta G = G - G_C$ determines whether the
convective system is amplifying ($\Delta G < 0$) or decaying ($\Delta G > 0$).

---

## 7. The MSE Budget Equation

### 7.1 Full Budget (Inoue & Back 2015, Eq. 6)

$$\frac{\partial \langle L_v q \rangle}{\partial t} \approx -\nabla \cdot \langle \mathbf{v} h \rangle + \langle Q_R \rangle + S$$

Under the **weak temperature gradient (WTG)** approximation (DSE tendency
$\approx 0$ on timescales > 1 day), the moisture tendency equals the full MSE
budget residual.

### 7.2 What the Dropsonde Dataset Can Provide

| Budget Term | Computable? | How |
|-------------|-------------|-----|
| $\langle \omega \, \partial h / \partial p \rangle$ | **Yes** | From `omega`, `ta_mean`, `q_mean`, `altitude` (§4) |
| $\langle \mathbf{v}_H \cdot \nabla_H h \rangle$ | **Yes** | From `u_mean`, `v_mean`, gradient fields (§5) |
| $\langle \omega \, \partial s / \partial p \rangle$ | **Yes** | Same approach with DSE |
| $LP$ (precip.) | **No** — use IMERG | Satellite precipitation product |
| $LE + H$ (surface fluxes) | **No** — use ERA5 or bulk formula | Reanalysis or SST-based |
| $\langle Q_R \rangle$ (radiative) | **No** — use ERA5 or CERES | Reanalysis or satellite |
| $\partial \langle h \rangle / \partial t$ (tendency) | **Partial** | Difference between successive circles if time gap is small |

### 7.3 Residual Approach

If external data provide $\langle Q_R \rangle$ and $S$, one can close the
budget and check consistency:

$$\text{Residual} = \frac{\partial \langle L_v q \rangle}{\partial t} + \langle \omega \frac{\partial h}{\partial p} \rangle + \langle \mathbf{v}_H \cdot \nabla_H h \rangle - \langle Q_R \rangle - S$$

A small residual (< 10% of the dominant terms) indicates the budget is
well-closed.

---

## 8. Step-by-Step Computational Procedure

### Step 1: Load the Data

```python
import xarray as xr
import numpy as np

ds = xr.open_zarr('/g/data/k10/zr7147/ORCESTRA_dropsondes_categorized.zarr')

Cp = 1005.0
Lv = 2.501e6
g  = 9.81
Rd = 287.0
```

### Step 2: Compute MSE and DSE Profiles

```python
h = Cp * ds.ta_mean + Lv * ds.q_mean + g * ds.altitude     # (circle, altitude)
s = Cp * ds.ta_mean + g * ds.altitude                       # (circle, altitude)
Lq = Lv * ds.q_mean                                         # (circle, altitude)
```

### Step 3: Define Vertical Integration Mask

```python
# Mask to tropospheric pressures: 100–1000 hPa
mask = (ds.p_mean >= 10000) & (ds.p_mean <= 100000) & (~np.isnan(ds.p_mean))

h  = h.where(mask)
s  = s.where(mask)
Lq = Lq.where(mask)
omega = ds.omega.where(mask)
```

### Step 4: Compute Vertical MSE Advection

```python
dhdz = h.differentiate('altitude')             # J kg⁻¹ m⁻¹
dsdz = s.differentiate('altitude')             # J kg⁻¹ m⁻¹
dLqdz = Lq.differentiate('altitude')           # J kg⁻¹ m⁻¹

dz = 10.0  # metres (uniform grid spacing)

# Integrand: (omega / g) × dh/dz × dz, integrated over altitude
# Units: (Pa/s) × (1 / m s⁻²) × (J kg⁻¹ m⁻¹) × m = W m⁻² per level
vert_mse_adv = ((omega / g) * dhdz * dz).sum('altitude')    # W m⁻²
vert_dse_adv = ((omega / g) * dsdz * dz).sum('altitude')    # W m⁻²
vert_Lq_adv  = ((omega / g) * dLqdz * dz).sum('altitude')   # W m⁻²
```

### Step 5: Compute Horizontal MSE Advection

```python
dhdx = Cp * ds.ta_dtadx + Lv * ds.q_dqdx      # J kg⁻¹ m⁻¹
dhdy = Cp * ds.ta_dtady + Lv * ds.q_dqdy      # J kg⁻¹ m⁻¹
dsdx = Cp * ds.ta_dtadx                        # J kg⁻¹ m⁻¹ (gz vanishes)
dsdy = Cp * ds.ta_dtady                        # J kg⁻¹ m⁻¹

h_hadv_integrand = ds.u_mean * dhdx + ds.v_mean * dhdy  # J kg⁻¹ s⁻¹
s_hadv_integrand = ds.u_mean * dsdx + ds.v_mean * dsdy

# Mass-weight: multiply by density and integrate
rho = ds.p_mean / (Rd * ds.ta_mean)            # kg m⁻³
horiz_mse_adv = (rho * h_hadv_integrand * dz).sum('altitude')   # W m⁻²
# Note: this is equivalent to (1/g) ∫ ... dp
horiz_dse_adv = (rho * s_hadv_integrand * dz).sum('altitude')
```

### Step 6: Compute GMS

```python
# Total advection
total_mse_adv = vert_mse_adv + horiz_mse_adv
total_dse_adv = vert_dse_adv + horiz_dse_adv

# Full GMS
G = (-total_mse_adv) / (-total_dse_adv)

# Vertical GMS only (most relevant for profile-shape analysis)
G_V = (-vert_mse_adv) / (-vert_dse_adv)
```

### Step 7: Quality Control

```python
# Filter out circles where:
# 1. Denominator is too small (singularity)
min_dse_adv = 5.0  # W/m², threshold to avoid division by near-zero
valid = np.abs(total_dse_adv) > min_dse_adv

# 2. GMS is outside physical bounds (|G| > 2 suggests computational issues)
valid = valid & (np.abs(G) < 2.0)

# 3. Category is not "Missing Data" or "Inactive / Suppressed"
active = ~ds.category_evolutionary.isin(['Missing Data', 'Inactive / Suppressed'])
valid = valid & active
```

---

## 9. Connecting GMS to Profile Shape Categories

The existing `category_evolutionary` classification uses the **Singh & Li
(2025) evolutionary angle method**, which characterises the vertical
velocity profile shape. GMS provides the **energetic consequence** of that
shape:

| Category | Angle θ | Expected $G_V$ | Physical Meaning |
|----------|---------|-----------------|------------------|
| Top-Heavy | > 45° | Positive | Deep outflow exports MSE → stabilising |
| Top-Heavy (Fully Ascending) | > 45° | Positive (larger) | Strong deep export |
| Bottom-Heavy | ≤ 45° | Negative | Shallow circulation imports MSE → destabilising |
| Bottom-Heavy (Fully Ascending) | ≤ 45° | Negative | MSE import, moistening |
| Inactive / Suppressed | — | ≈ 0 | Weak vertical transport |

The scatter plot of `top_heaviness_angle` vs $G_V$ should show a clear
relationship, providing independent verification of both the classification
and the GMS calculation.

---

## 10. What Needs External Data

The dropsonde dataset alone provides the **advective** part of the MSE budget.
To fully close the budget or compute the critical GMS / drying efficiency,
external datasets are needed:

| Quantity | Source | Notes |
|----------|--------|-------|
| Precipitation $P$ | IMERG (GPM) | Already downloaded to `/g/data/k10/zr7147/GPM_IMERG_Data/` |
| TOA & surface radiation $Q_R$ | ERA5 or CERES | Column-integrated radiative heating |
| Surface latent heat flux $LE$ | ERA5 or bulk formula | Near-surface T, q, wind from lowest sonde levels |
| Surface sensible heat flux $H$ | ERA5 or bulk formula | Usually small over tropical ocean |
| SST | ERA5 or OSTIA | Needed for bulk flux calculation |

### 10.1 What Auxiliary Data We Already Have

- **IMERG precipitation**: `/g/data/k10/zr7147/GPM_IMERG_Data/` and combined
  file `ORCESTRA_IMERG_Combined_Cropped.nc`
- **EarthCARE CPR**: `/g/data/k10/zr7147/EarthCARE_Data/`

### 10.2 What Would Need To Be Downloaded

- **ERA5** hourly surface and pressure-level data for radiative fluxes,
  surface fluxes, and SST over the campaign domain
  (0–30°N, 70°W–0°W, Aug–Sep 2024)

---

## 11. Summary of Corrections to the Old Guide

The [old guide](how%20to%20calculate%20MSE.md) contained several errors
that are corrected here:

| Issue | Old Guide | Corrected Here |
|-------|-----------|----------------|
| Theorem name | "Stokes' theorem" throughout | Gauss divergence theorem for div/omega; Stokes for vorticity |
| Divergence from single ring | Tried to compute $\partial v_r / \partial r$ | Uses integral form directly (area-averaged D) — already done in dataset |
| ω recovery equation | Had spurious factor of $g$; used linear approximation | No extra $g$; use level-by-level integration preserving profile shape |
| GMS denominator | $G_H$ and $G_V$ had inconsistent denominators | Both use the same denominator: $-\langle \mathbf{v} \cdot \nabla s \rangle$ |
| Radial MSE gradient | Assumed computable from single circle | Not computable; use the gradient fields provided by the dataset |
| Coordinate mixing | Part 7 mixed density and pressure formulations | Consistent altitude-coordinate approach throughout |
| Integration limits | Inconsistent sign convention between equations | Consistent: integrate upward in $z$, or from $p_t$ to $p_s$ in positive $dp$ |

---

## References

- **Inoue, K. and L. E. Back (2015)**: Gross Moist Stability Assessment during
  TOGA COARE: Various Interpretations of Gross Moist Stability.
  *J. Atmos. Sci.*, 72, 4148–4166.
- **Bui, H. X., J.-Y. Yu, and C. Chou (2016)**: Impacts of Vertical Structure
  of Large-Scale Vertical Motion in Tropical Climate: Moist Static Energy
  Framework. *J. Atmos. Sci.*, 73, 4427–4437.
- **Handlos, Z. J. and L. E. Back (2014)**: Estimating Vertical Motion Profile
  Shape within Tropical Weather States over the Oceans. *J. Climate*, 27,
  7667–7686.
- **Raymond, D. J., S. L. Sessions, A. H. Sobel, and Z. Fuchs (2009)**:
  The Mechanics of Gross Moist Stability. *J. Adv. Model. Earth Syst.*, 1, 9.
- **Singh and Li (2025)**: Evolutionary angle method for ω-profile
  classification.
- **PERCUSION / ORCESTRA**: Gross, S., B. Stevens, J. Windmiller et al.
