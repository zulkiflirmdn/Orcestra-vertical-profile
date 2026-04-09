# MSE Budget Methods for ORCESTRA Dropsonde Circles

## Overview

This document describes two methods for computing the **column moist static energy (MSE) budget** from the BEACH Level-4 dropsonde circle dataset.  Both methods answer the same physical question — *how much MSE is exported horizontally from the convective column?* — but they approach it differently.

The MSE budget connects **vertical motion profile shapes** (measured by the Singh & Li 2025 top-heaviness angle) to **energy export efficiency** (measured by Gross Moist Stability, GMS).  This is the central relationship in our analysis of tropical convection during PERCUSION / ORCESTRA.

---

## Background: Moist Static Energy

The moist static energy at a point in the atmosphere is

$$h = c_p T + gz + L_v q$$

where

| Symbol | Meaning | Value / Units |
|--------|---------|---------------|
| $c_p$  | Specific heat at constant pressure | 1004 J kg⁻¹ K⁻¹ |
| $T$    | Air temperature | K |
| $g$    | Gravitational acceleration | 9.81 m s⁻² |
| $z$    | Geopotential height | m |
| $L_v$  | Latent heat of vaporisation | 2.501 × 10⁶ J kg⁻¹ |
| $q$    | Specific humidity | kg kg⁻¹ |

MSE is approximately conserved under moist adiabatic processes, which makes it the natural energy variable for diagnosing tropical convection.  When convection exports MSE from a column, it acts as a brake on further instability.  The efficiency of this export — the **Gross Moist Stability** — depends on the shape of the vertical motion profile.

The **Dry Static Energy** (DSE) is the non-moisture component:

$$s = c_p T + gz$$

---

## The Full MSE Tendency Equation

The local tendency of MSE is governed by:

$$\frac{\partial h}{\partial t} + \nabla \cdot (\mathbf{v}h) + \frac{\partial (\omega h)}{\partial p} = Q_R + L_v(E - P) + SH$$

where $\mathbf{v} = (u, v)$ is the horizontal wind, $\omega$ is the vertical pressure velocity, and the right-hand side contains radiative heating ($Q_R$), surface latent heat ($L_v(E-P)$), and surface sensible heat ($SH$).

**Column-integrating** this equation (i.e., applying $\langle \cdot \rangle = \int_{p_t}^{p_s} (\cdot)\, dp/g$) eliminates the vertical flux divergence term because $\omega \approx 0$ at both the surface and the tropopause:

$$\frac{\partial \langle h \rangle}{\partial t} + \langle \nabla \cdot (\mathbf{v}h) \rangle = F$$

where $F$ lumps all forcing terms.  The key unknown is the **horizontal MSE flux divergence** $\langle \nabla \cdot (\mathbf{v}h) \rangle$, which represents the net MSE export from the column.

---

## Method 1: Advective Form

### Derivation

Using the mass continuity equation ($\nabla \cdot \mathbf{v} + \partial\omega/\partial p = 0$), the 3-D flux divergence can be decomposed:

$$\nabla \cdot (\mathbf{v}h) + \frac{\partial(\omega h)}{\partial p} = \mathbf{v} \cdot \nabla h + \omega \frac{\partial h}{\partial p}$$

After column integration (the vertical flux divergence vanishes):

$$\boxed{\frac{\partial \langle h \rangle}{\partial t} + \underbrace{\langle \mathbf{v} \cdot \nabla h \rangle}_{\text{horizontal advection}} + \underbrace{\left\langle \omega \frac{\partial h}{\partial p} \right\rangle}_{\text{vertical advection}} = F}$$

### Physical interpretation

- **Horizontal advection** $\langle \mathbf{v} \cdot \nabla h \rangle$: MSE transport by the mean horizontal wind acting on the MSE gradient across the circle.  This depends on the large-scale environment (wind shear, moisture gradients).
- **Vertical advection** $\langle \omega \frac{\partial h}{\partial p} \rangle$: MSE transport by the vertical circulation (omega).  This is the term that **directly depends on the omega profile shape**.

### Why this matters for our research

Because the tropical MSE profile has a characteristic **minimum in the mid-troposphere** (around 500–600 hPa), the *shape* of omega determines the sign and magnitude of the vertical advection:

- **Top-heavy omega** (peak ascent in upper troposphere): lifts high-MSE upper-tropospheric air upward, exporting MSE efficiently → **large positive GMS**
- **Bottom-heavy omega** (peak ascent in lower troposphere): lifts high-MSE boundary-layer air, but the column integral is dominated by the mid-level MSE minimum → **smaller or negative GMS**

### Computation from the dataset

**Horizontal advection at each level:**

$$(\mathbf{v} \cdot \nabla h)_k = \bar{u}_k \frac{\partial \bar{h}}{\partial x}\bigg|_k + \bar{v}_k \frac{\partial \bar{h}}{\partial y}\bigg|_k$$

where the MSE gradients are built from temperature and humidity gradients:

$$\frac{\partial h}{\partial x} = c_p \frac{\partial T}{\partial x} + L_v \frac{\partial q}{\partial x}$$

**Vertical advection at each level:**

$$\left(\omega \frac{\partial h}{\partial p}\right)_k = \omega_k \cdot \frac{\partial h}{\partial p}\bigg|_k$$

where $\partial h / \partial p$ is computed by finite-differencing the MSE profile with respect to pressure.

**Column integrals:**

$$\langle \mathbf{v} \cdot \nabla h \rangle = \int_{p_t}^{p_s} (\mathbf{v} \cdot \nabla h)\, \frac{dp}{g}$$

$$\left\langle \omega \frac{\partial h}{\partial p} \right\rangle = \int_{p_t}^{p_s} \omega \frac{\partial h}{\partial p}\, \frac{dp}{g}$$

**Gross Moist Stability (normalised):**

$$\tilde{M} = \frac{\langle \omega\, \partial h / \partial p \rangle}{\langle \omega\, \partial s / \partial p \rangle}$$

The denominator uses DSE ($s$) to normalise by the "dry" vertical energy transport, giving a dimensionless measure of how efficiently convection exports MSE relative to total energy throughput.

### Strengths and limitations

| ✓ Strengths | ✗ Limitations |
|-------------|---------------|
| Separates horizontal and vertical advection | Neglects eddy covariances ($\overline{v'h'}$) |
| Directly links omega shape to GMS | Requires accurate circle-mean gradient fields |
| Fast — uses pre-computed circle products | Cannot directly validate against a single "total export" |
| Isolates the term relevant to our research question | |

---

## Method 2: Flux Form (Total Column MSE Export)

### Derivation

Instead of decomposing the flux divergence into separate horizontal and vertical terms, the flux form keeps them together as a single total export:

$$\boxed{\frac{\partial \langle h \rangle}{\partial t} + \underbrace{\langle \nabla \cdot (\mathbf{v}h) \rangle}_{\text{total horizontal MSE export}} = F}$$

The total export is what one would measure by applying the 2-D divergence theorem (Gauss) to the dropsonde ring:

$$\frac{1}{A} \iint_A \nabla \cdot (\mathbf{v}h)\, dA = \frac{1}{A} \oint_C (\mathbf{v}h) \cdot \hat{n}\, dl$$

where, with $N$ sondes distributed around a circle of radius $R$ (area $A = \pi R^2$):

$$\overline{\nabla \cdot (\mathbf{v}h)} \approx \frac{1}{\pi R^2} \sum_{i=1}^{N} (v_{r,i} \cdot h_i)\, \Delta l_i$$

| Quantity | Definition |
|----------|-----------|
| $\theta_i$ | Azimuthal angle of sonde $i$: $\theta_i = \text{arctan2}(y_i, x_i)$ |
| $v_{r,i}$ | Outward radial wind: $v_{r,i} = u_i \cos\theta_i + v_i \sin\theta_i$ |
| $h_i$ | MSE at sonde $i$: $h_i = c_p T_i + g z_i + L_v q_i$ |
| $\Delta l_i$ | Arc length (midpoint rule): $\Delta l_i = R \cdot (\theta_{i+1} - \theta_{i-1})/2$ |

### Important numerical caveat

Direct evaluation of the line integral and column integration suffers from a **boundary-term problem**: the decomposition $\nabla \cdot (\mathbf{v}h) = \mathbf{v} \cdot \nabla h + h \cdot \nabla \cdot \mathbf{v}$ produces a dominant $h \cdot \nabla \cdot \mathbf{v}$ term at each level.  When column-integrated, this converts to the vertical advection via integration by parts:

$$\int h \, \nabla \cdot \mathbf{v}\, \frac{dp}{g} = -\frac{[h\omega]_{p_t}^{p_s}}{g} + \int \omega \frac{\partial h}{\partial p}\, \frac{dp}{g}$$

The boundary term $[h\omega/g]$ requires $\omega \to 0$ at both the surface and tropopause.  In the BEACH dataset, dropsonde profiles often terminate well below the tropopause (~270 hPa instead of ~100 hPa), where $\omega$ is still significant (~0.1 Pa/s).  This produces boundary errors of **O(4000 W m⁻²)** — far larger than the physical signal.

### Numerically stable computation

To avoid the boundary-term issue, we compute the column-integrated flux divergence using the advective decomposition:

$$\langle \nabla \cdot (\mathbf{v}h) \rangle = \langle \mathbf{v} \cdot \nabla h \rangle + \left\langle \omega \frac{\partial h}{\partial p} \right\rangle$$

This is mathematically identical to the line integral after proper column integration but avoids catastrophic cancellation.  The result is a **single number per circle** representing the total horizontal MSE export — exactly the quantity the line integral would give with perfect data.

### Computation from the dataset

The total column MSE export uses the same variables as Method 1:

$$\langle \nabla \cdot (\mathbf{v}h) \rangle = \int_{p_t}^{p_s} \left(\bar{u} \frac{\partial \bar{h}}{\partial x} + \bar{v} \frac{\partial \bar{h}}{\partial y} + \omega \frac{\partial h}{\partial p}\right) \frac{dp}{g}$$

**Flux-form GMS** (total export efficiency):

$$\tilde{M}_{\text{flux}} = \frac{\langle \nabla \cdot (\mathbf{v}h) \rangle}{\langle \nabla \cdot (\mathbf{v}s) \rangle}$$

### Connection to what BEACH already does

The BEACH Level-4 processing applies the divergence theorem to the sonde ring to compute `div` ($\nabla \cdot \mathbf{v}$), `omega` (from the continuity equation), and all gradient fields.  Our computation extends this framework to the MSE flux product $\mathbf{v}h$.

### Strengths and limitations

| ✓ Strengths | ✗ Limitations |
|-------------|---------------|
| Gives a single total-export number per circle | Cannot separate horizontal from vertical contributions |
| Includes both environmental advection and vertical transport | |
| Equivalent to the Stokes line integral (in principle) | Direct line integral is noisy with 12 sondes |
| Numerically stable via advective decomposition | |

---

## Relationship Between the Two Methods

The advective form and flux form are **mathematically equivalent** when:

1. The eddy covariance $\overline{v'h'} \approx 0$ (i.e., the circle is large enough that sub-circle correlations are small)
2. The vertical flux divergence $\partial(\omega h)/\partial p$ integrates to zero over the column

Under these conditions:

$$\underbrace{\langle \nabla \cdot (\mathbf{v}h) \rangle}_{\text{Flux form}} = \underbrace{\langle \mathbf{v} \cdot \nabla h \rangle + \left\langle \omega \frac{\partial h}{\partial p} \right\rangle}_{\text{Advective form}}$$

Comparing the two provides a **budget closure check**: if they agree, the assumptions hold and the dropsonde sampling is adequate.

---

## Gross Moist Stability (GMS)

Both methods can produce a GMS estimate:

**Advective GMS** (isolates the vertical term):

$$\tilde{M}_{\text{adv}} = \frac{\langle \omega\, \partial h / \partial p \rangle}{\langle \omega\, \partial s / \partial p \rangle}$$

**Flux GMS** (total column export):

$$\tilde{M}_{\text{flux}} = \frac{\langle \nabla \cdot (\mathbf{v}h) \rangle}{\langle \nabla \cdot (\mathbf{v}s) \rangle}$$

The advective GMS directly captures the effect of omega shape on energy export, making it the more natural metric for our research question.

---

## Recommendation

**Use the advective form as the primary analysis method.**  It isolates $\langle \omega\, \partial h / \partial p \rangle$, which is the exact term that links vertical motion profile shape to energy export efficiency.

**Use the flux form as a cross-validation.**  Agreement between the two confirms that the budget closes and the dropsonde sampling is reliable.

---

## Dataset Variables Used

### Method 1: Advective Form — Circle-Mean Fields

These variables have dimensions `(circle, altitude)` unless noted.

| Variable | Units | Role in Budget |
|----------|-------|----------------|
| `ta_mean` | K | Temperature → MSE profile $h$ and DSE profile $s$ |
| `q_mean` | kg kg⁻¹ | Specific humidity → MSE profile $h$ |
| `p_mean` | Pa | Pressure → $\partial h / \partial p$ and column integration |
| `omega` | Pa s⁻¹ | Vertical velocity → vertical advection $\omega \partial h / \partial p$ |
| `u_mean` | m s⁻¹ | Zonal wind → horizontal advection $\mathbf{v} \cdot \nabla h$ |
| `v_mean` | m s⁻¹ | Meridional wind → horizontal advection $\mathbf{v} \cdot \nabla h$ |
| `ta_dtadx` | K m⁻¹ | Zonal temperature gradient → $\partial h / \partial x$ |
| `ta_dtady` | K m⁻¹ | Meridional temperature gradient → $\partial h / \partial y$ |
| `q_dqdx` | kg kg⁻¹ m⁻¹ | Zonal humidity gradient → $\partial h / \partial x$ |
| `q_dqdy` | kg kg⁻¹ m⁻¹ | Meridional humidity gradient → $\partial h / \partial y$ |
| `altitude` | m | Height coordinate → geopotential $gz$ in MSE |

**Metadata used for grouping and labelling:**

| Variable | Dimensions | Role |
|----------|-----------|------|
| `category_evolutionary` | `(circle,)` | Profile shape category (Top-Heavy, Bottom-Heavy, etc.) |
| `top_heaviness_angle` | `(circle,)` | Singh & Li (2025) angle for scatter plots |
| `circle_time` | `(circle,)` | Time coordinate for temporal analysis |
| `circle_lat` | `(circle,)` | Latitude for spatial analysis |
| `circle_lon` | `(circle,)` | Longitude for spatial analysis |

### Method 2: Flux Form — Same Circle-Mean Fields

The flux form uses the **same circle-mean fields** as Method 1 (because we compute it via the advective decomposition for numerical stability).  No individual sonde fields are needed.

All variables listed in the Method 1 table above are used identically.  The only difference is how the results are presented: Method 2 sums horizontal and vertical advection into a single total-export number instead of reporting them separately.

**Individual sonde data** (listed below) are only needed if you want to compute the line integral directly for validation or comparison.  These are available in the dataset but not used in the standard flux-form computation:

| Variable | Dimensions | Units | Role (line integral only) |
|----------|-----------|-------|---------------------------|
| `ta` | `(sonde, altitude)` | K | Sonde temperature → $h_i$ |
| `q` | `(sonde, altitude)` | kg kg⁻¹ | Sonde humidity → $h_i$ |
| `p` | `(sonde, altitude)` | Pa | Sonde pressure → column integration |
| `u` | `(sonde, altitude)` | m s⁻¹ | Zonal wind → radial wind $v_{r,i}$ |
| `v` | `(sonde, altitude)` | m s⁻¹ | Meridional wind → radial wind $v_{r,i}$ |
| `x` | `(sonde,)` | m | Sonde x-position → azimuth $\theta_i$ |
| `y` | `(sonde,)` | m | Sonde y-position → azimuth $\theta_i$ |
| `sondes_per_circle` | `(circle,)` | — | Sonde-to-circle mapping |
| `circle_radius` | `(circle,)` | m | Circle radius $R$ → area $A = \pi R^2$ |

### Dataset Summary

| Property | Value |
|----------|-------|
| Path | `/g/data/k10/zr7147/ORCESTRA_dropsondes_categorized.zarr` |
| Circles | 89 |
| Sondes | 1058 |
| Altitude levels | 1460 (0–14590 m, Δz = 10 m) |
| Circle radii | 59–134 km |
| Sondes per circle | 3–18 (typically 12) |
| Campaign | PERCUSION / ORCESTRA, Aug–Sep 2024 |
| Region | Tropical Atlantic, 3–18°N, 59–21°W |

---

## References

- Inoue, K. and L. E. Back, 2015: Column-integrated moist static energy budget analysis on various time scales during TOGA COARE. *J. Atmos. Sci.*, **72**, 1856–1871, doi:10.1175/JAS-D-15-0111.1.
- Bui, H. X., J.-Y. Yu, and C. Chou, 2016: Impacts of vertical structure of large-scale vertical motion in tropical climate: Moist static energy framework. *J. Atmos. Sci.*, **73**, 4427–4437, doi:10.1175/JAS-D-15-0349.1.
- Handlos, Z. J. and L. E. Back, 2014: Estimating vertical motion profile shape within tropical weather states over the oceans. *J. Climate*, **27**, 7667–7675, doi:10.1002/2013GL058846.
- Singh, M. and R. Li, 2025: Evolutionary angle-based classification of tropical vertical motion profiles. *(in preparation)*.
