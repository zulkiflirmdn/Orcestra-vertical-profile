# 🌪️ Comprehensive Guide: Calculating MSE and GMS Along a Dropsonde Halo Circle

**Mathematical Framework for Energy Transport Calculations Using Dropsonde Data**

---

## 📋 Table of Contents

1. [Fundamental Definitions](#part-1-fundamental-definitions-and-concepts)
2. [MSE Budget Equations](#part-2-mse-budget-equations)
3. [Stokes' Theorem Application](#part-3-stokes-theorem-application-for-circular-halo)
4. [MSE Advection Methods](#part-4-mse-advection-calculation-methods)
5. [Gross Moist Stability](#part-5-gross-moist-stability-gms-calculation)
6. [Computational Procedure](#part-6-step-by-step-computational-procedure-for-dropsonde-halo-data)
7. [Flux-Form Closure](#part-7-flux-form-closure-using-stokes-theorem)
8. [Practical Notes](#part-8-practical-computational-notes)
9. [Result Interpretation](#part-9-interpretation-of-results)

---

## Part 1: Fundamental Definitions and Concepts

### 1.1 Moist Static Energy (MSE) Definition

The **moist static energy** is conserved following air parcels in adiabatic processes:

$$h = C_p T + Lq + gz$$

#### Key Parameters:

| Parameter | Symbol | Value | Unit |
|-----------|--------|-------|------|
| Specific heat of air (constant pressure) | $C_p$ | 1005 | J/kg·K |
| Absolute temperature | $T$ | — | K |
| Latent heat of vaporization | $L$ | ~2.5 × 10⁶ | J/kg |
| Specific humidity | $q$ | — | kg/kg |
| Gravitational acceleration | $g$ | 9.81 | m/s² |
| Height above surface | $z$ | — | m |

**Alternative decomposition** into dry static energy (DSE) and latent heat:

$$h = s + Lq$$

where the **Dry Static Energy (DSE)** is:

$$s = C_p T + gz$$

> **💡 Energy Units Convention:** Scale specific humidity into energy units: $Lq$ expressed in J/kg

---

### 1.2 Column-Integrated MSE

For a vertical column, integrate MSE over the atmospheric depth:

$$\langle h \rangle = \int_{p_s}^{p_t} h(p) \, dp$$

**Mass-weighted vertical integration** from surface pressure ($p_s$ ≈ 1000 hPa) to tropopause ($p_t$ ≈ 100 hPa):

$$\langle h \rangle = \frac{1}{g} \int_{1000}^{100} h(p) {dp}$$

The angle brackets denote **mass-weighted integration**:

$$\langle A \rangle = \frac{1}{g} \int_{p_s}^{p_t} A(p) dp$$

---

## Part 2: MSE Budget Equations

### 2.1 Basic MSE Budget (Yanai et al. 1973)

The **vertically integrated energy budget equation**:

$$\frac{\partial \langle h \rangle}{\partial t} = -\nabla \cdot \langle \mathbf{v} h \rangle + F_{net}$$

**Expanded advection term:**

$$\frac{\partial \langle h \rangle}{\partial t} = -\langle \mathbf{v}_H \cdot \nabla_H h \rangle - \langle w \frac{\partial h}{\partial p} \rangle + F_{net}$$

#### Components:

- **First term on RHS:** Horizontal MSE advection
- **Second term on RHS:** Vertical MSE advection (related to GMS)
- **$F_{net}$:** Net diabatic fluxes (radiative, surface fluxes)

---

### 2.2 Flux-Form MSE Budget

Using mass continuity and integration by parts (assuming $w$ vanishes at surface and tropopause):

$$\frac{\partial \langle h \rangle}{\partial t} = -\nabla \cdot \langle \mathbf{v} h \rangle + Q_R + E - P + H$$

#### Flux Components:

| Component | Symbol | Description | Unit |
|-----------|--------|-------------|------|
| Radiative heating | $Q_R$ | Column radiative heating | W/m² |
| Evaporation | $E$ | Surface evaporation | kg/m²/s |
| Precipitation | $P$ | Precipitation | kg/m²/s |
| Sensible heat flux | $H$ | Surface sensible heat flux | W/m² |

> **Energy units convention:** Multiply precipitation and evaporation by latent heat:
> - $LE$ = latent heat flux from evaporation (W/m²)
> - $LP$ = latent heat removed by precipitation (W/m²)

---

## Part 3: Stokes' Theorem Application for Circular Halo

### 3.1 Applying Stokes' Theorem to Boundary Flux Calculations

For a circular flight path around a convective system, **Stokes' theorem** provides a powerful approach:

**Stokes' Theorem (Mathematical Form):**

$$\oint_C \mathbf{v} \cdot d\mathbf{l} = \iint_A (\nabla \times \mathbf{v}) \cdot d\mathbf{A}$$

**2D Representation:**

$$\oint_C (u \, dx + v \, dy) = \iint_A \left( \frac{\partial v}{\partial x} - \frac{\partial u}{\partial y} \right) dA$$

#### For a Circular Halo of Radius $R$:

$$\oint_{circle} \mathbf{v} \cdot d\mathbf{l} = 2\int_0^{2\pi} v_{\tan}(\theta) R \, d\theta$$

where $v_{\tan}(\theta)$ is the **tangential wind component** at angle $\theta$.

---

### 3.2 Mass Flux Calculation from Dropsonde Wind Data

#### Horizontal Wind Components:

From dropsonde data at each observation point:
- $u$ = zonal wind component (m/s)
- $v$ = meridional wind component (m/s)
- Position on circle: $(x_i, y_i)$ at angle $\theta_i$

#### Tangential Velocity Component:

$$v_{\tan} = -u \sin(\theta) + v \cos(\theta)$$

where $(\sin(\theta), \cos(\theta))$ is the **unit tangent vector**.

#### Mass Flux (Mass Continuity):

Using the divergence theorem:

$$\oint_C \mathbf{v} \cdot \mathbf{n} \, dl = \iint_A \nabla \cdot \mathbf{v} \, dA$$

where $\mathbf{n}$ is the **outward normal unit vector**.

**For a circular path**, the outward normal is the **radial direction**:

$$\mathbf{n} = (\cos(\theta), \sin(\theta))$$

#### Radial (Outward) Wind Component:

$$v_r = u \cos(\theta) + v \sin(\theta)$$

#### Cumulative Mass Flux Integral:

$$M_{out} = \rho \oint_{circle} v_r \, dl = \rho R \int_0^{2\pi} v_r(\theta) \, d\theta$$

where $\rho$ is air density (kg/m³).

---

### 3.3 Vertical Velocity from Mass Continuity

Assuming **mass conservation** in the cylindrical column:

$$\frac{\partial \rho}{\partial t} + \nabla \cdot (\rho \mathbf{v}) = 0$$

For a convective system, horizontal divergence at the boundary implies:

$$\int_0^{2\pi} v_r(\theta) d\theta = \frac{1}{R} \int_0^H \omega(z) dz$$

where the integral on the right is the **column-integrated vertical velocity**.

---

## Part 4: MSE Advection Calculation Methods

### 4.1 Direct Vertical MSE Advection

The **column-integrated vertical MSE advection**:

$$\langle w \frac{\partial h}{\partial p} \rangle = \int_{p_s}^{p_t} \omega \frac{\partial h}{\partial p} \frac{dp}{g}$$

#### Parameters:
- $\omega = \frac{dp}{dt}$ = vertical velocity in pressure coordinates (Pa/s)
- $\frac{\partial h}{\partial p}$ = vertical gradient of MSE

#### Computational Approach (with Dropsonde Data):

1. Calculate MSE at each pressure level: $h_i = C_p T_i + Lq_i + gz_i$
2. Calculate MSE gradient: $\frac{\partial h}{\partial p} \approx \frac{h_{i+1} - h_{i-1}}{p_{i+1} - p_{i-1}}$
3. Estimate $\omega$ from divergence
4. Integrate vertically

---

### 4.2 Direct Horizontal MSE Advection

The **column-integrated horizontal MSE advection**:

$$\langle \mathbf{v}_H \cdot \nabla_H h \rangle = \int_{p_s}^{p_t} (u \frac{\partial h}{\partial x} + v \frac{\partial h}{\partial y}) \frac{dp}{g}$$

#### For Dropsonde Halo Data:

At each radial distance and angle on the circle:

$$\langle \mathbf{v}_H \cdot \nabla_H h \rangle = \int_{p_s}^{p_t} v_r \frac{\partial h}{\partial r} \frac{dp}{g} + \int_{p_s}^{p_t} v_{\tan} \frac{1}{r} \frac{\partial h}{\partial \theta} \frac{dp}{g}$$

where:
- $v_r, v_{\tan}$ = radial and tangential components
- $\frac{\partial h}{\partial r}, \frac{\partial h}{\partial \theta}$ = radial and azimuthal MSE gradients

#### Simplified Approach (Averaged Around Circle):

If the circle is far enough that a plane approximation is valid:

$$\langle \mathbf{v}_H \cdot \nabla_H h \rangle \approx \langle u \rangle \frac{\partial \langle h \rangle}{\partial x} + \langle v \rangle \frac{\partial \langle h \rangle}{\partial y}$$

where angle brackets denote **azimuthal averaging**.

---

## Part 5: Gross Moist Stability (GMS) Calculation

### 5.1 Definition of GMS

**Gross Moist Stability** measures the **efficiency of MSE export per unit mass flux**:

$$G = \frac{-\langle v \cdot \nabla h \rangle}{\langle v \cdot \nabla s \rangle} = \frac{\text{Column MSE export}}{\text{Column DSE export}}$$

Or equivalently, normalized by vertical velocity:

$$G = \frac{\langle \nabla h \rangle}{\langle \nabla s \rangle}$$

#### Physical Interpretation:

| GMS Value | Behavior | Effect |
|-----------|----------|--------|
| **$G > 0$** | Column exports MSE | Stabilizing effect |
| **$G < 0$** | Column imports MSE | Destabilizing effect |
| **$G ≈ 0$** | Neither import nor export | Neutral |

---

### 5.2 Component-Based GMS

GMS can be decomposed into **horizontal and vertical components**:

$$G = G_H + G_V$$

**Horizontal component:**

$$G_H = \frac{\langle u \frac{\partial h}{\partial x} + v \frac{\partial h}{\partial y} \rangle}{\langle v_x \frac{\partial s}{\partial x} \rangle}$$

**Vertical component:**

$$G_V = \frac{\langle w \frac{\partial h}{\partial p} \rangle}{\langle v_x \frac{\partial s}{\partial x} \rangle}$$

---

### 5.3 Critical GMS and Drying Efficiency

From **Inoue & Back (2015)**, the **critical GMS** is:

$$G_C = \frac{F}{\langle v \cdot \nabla s \rangle} = \frac{\langle Q_R \rangle + S}{\langle v \cdot \nabla s \rangle}$$

where:
- $F = \langle Q_R \rangle + S$ = diabatic forcing (radiative + surface fluxes)
- $S = LE + H$ = surface fluxes (latent + sensible)

#### Drying Efficiency:

$$\Delta G = G - G_C$$

#### Interpretation:

| $\Delta G$ Value | System State | Phase |
|-----------------|--------------|-------|
| **$\Delta G < 0$** | System moistening | 📈 Amplification |
| **$\Delta G = 0$** | Maximum precipitation | 🎯 Critical point |
| **$\Delta G > 0$** | System drying | 📉 Decay |

---

## Part 6: Step-by-Step Computational Procedure for Dropsonde Halo Data

### Step 1: Data Organization

#### Input Data from Dropsonde Circle:

- Latitude/Longitude: $(\phi_i, \lambda_i)$ at $N$ points around circle
- Temperature profile: $T_i(p)$ for $i = 1, ..., N$ and $p \in [100, 1000]$ hPa
- Specific humidity: $q_i(p)$ for each point
- Horizontal wind: $u_i(p), v_i(p)$ for each point

#### Convert to Standard Coordinates:

- Distance from center: $r_i$ (meters)
- Azimuthal angle: $\theta_i$ (radians, 0 to $2\pi$)
- Pressure: $p$ (Pa, in 25 or 50 hPa increments)

---

### Step 2: Calculate Column-Integrated Fields

#### For Each Dropsonde Location $i$:

**MSE profile:**

$$h_i(p) = 1005 \cdot T_i(p) + 2.5 \times 10^6 \cdot q_i(p) + 9.81 \cdot z_i(p)$$

**Column MSE:**

$$\langle h_i \rangle = \frac{1}{g} \int_{1000}^{100} h_i(p) dp$$

**Numerical integration (trapezoid rule):**

$$\langle h_i \rangle = \frac{1}{g} \sum_{k=1}^{n-1} \frac{h_i(p_k) + h_i(p_{k+1})}{2} (p_{k+1} - p_k)$$

**DSE profile and column:**

$$s_i(p) = 1005 \cdot T_i(p) + 9.81 \cdot z_i(p)$$

$$\langle s_i \rangle = \frac{1}{g} \int_{1000}^{100} s_i(p) dp$$

---

### Step 3: Calculate Vertical Velocity from Divergence

#### Wind Components in Cylindrical Coordinates:

At each dropsonde location:

$$v_{r,i} = u_i \cos(\theta_i) + v_i \sin(\theta_i)$$

$$v_{\tan,i} = -u_i \sin(\theta_i) + v_i \cos(\theta_i)$$

#### Horizontal Divergence (Finite Difference Around Circle):

**Radial divergence:**

$$\frac{\partial v_r}{\partial r} \bigg|_{\theta_i} \approx \frac{v_{r,i+1} - v_{r,i-1}}{2 \Delta r}$$

where $\Delta r$ = radial spacing between dropsonde circle points.

**Azimuthal divergence:**

$$\frac{\partial v_{\tan}}{\partial \theta}\bigg|_{r} \approx \frac{v_{\tan,i+1} - v_{\tan,i-1}}{2 r_i \Delta \theta}$$

#### Total Divergence:

$$\delta_i = \frac{\partial v_r}{\partial r} + \frac{1}{r_i} v_{r,i} + \frac{1}{r_i} \frac{\partial v_{\tan}}{\partial \theta}$$

#### Column-Integrated Divergence:

$$\langle \delta \rangle_i = \frac{1}{g} \int_{1000}^{100} \delta_i(p) dp$$

#### Vertical Velocity from Mass Continuity:

Integrating downward from tropopause:

$$\omega(p) = -g \int_p^{p_t} \delta(p') dp'$$

Alternatively, for a **local estimate at level** $p$:

$$\omega_i(p) \approx -g \langle \delta \rangle_i \cdot \frac{p_t - p}{p_t - p_s}$$

---

### Step 4: Calculate MSE Advection Terms

#### Vertical MSE Advection:

For each dropsonde location:

$$\langle \omega \frac{\partial h}{\partial p} \rangle_i = \frac{1}{g} \int_{1000}^{100} \omega_i(p) \frac{\partial h_i}{\partial p} dp$$

#### Horizontal MSE Advection:

**Calculate MSE gradients (radial):**

$$\frac{\partial \langle h \rangle}{\partial r} \approx \frac{\langle h_{i+1} \rangle - \langle h_{i-1} \rangle}{2 \Delta r}$$

**Calculate MSE gradients (azimuthal):**

$$\frac{\partial \langle h \rangle}{\partial \theta} \approx \frac{\langle h_{i+1} \rangle - \langle h_{i-1} \rangle}{2 \Delta \theta}$$

**Horizontal advection at each point:**

$$\langle u \frac{\partial h}{\partial x} + v \frac{\partial h}{\partial y} \rangle_i = \langle v_r \frac{\partial h}{\partial r} + \frac{v_{\tan}}{r} \frac{\partial h}{\partial \theta} \rangle_i$$

#### Total MSE Advection:

$$-\nabla \cdot \langle v h \rangle_i = \langle u \frac{\partial h}{\partial x} + v \frac{\partial h}{\partial y} \rangle_i + \langle \omega \frac{\partial h}{\partial p} \rangle_i$$

---

### Step 5: Calculate GMS

#### DSE Advection:

$$-\langle v \cdot \nabla s \rangle = \langle u \frac{\partial s}{\partial x} + v \frac{\partial s}{\partial y} \rangle + \langle \omega \frac{\partial s}{\partial p} \rangle$$

#### GMS at Each Location:

$$G_i = \frac{-\langle v \cdot \nabla h \rangle_i}{-\langle v \cdot \nabla s \rangle_i}$$

#### Average Around Circle:

$$G_{mean} = \frac{1}{N} \sum_i G_i$$

---

### Step 6: Vertical Component Decomposition

#### Vertical DSE Advection:

$$\langle \omega \frac{\partial s}{\partial p} \rangle$$

#### Vertical GMS:

$$G_V = \frac{\langle \omega \frac{\partial h}{\partial p} \rangle}{\langle \omega \frac{\partial s}{\partial p} \rangle}$$

#### Horizontal GMS:

$$G_H = \frac{\langle u \frac{\partial h}{\partial x} + v \frac{\partial h}{\partial y} \rangle}{\langle \omega \frac{\partial s}{\partial p} \rangle}$$

---

## Part 7: Flux-Form Closure Using Stokes' Theorem

### 7.1 Boundary Flux Calculation

For the circular halo boundary, the **outward energy flux**:

$$F_{boundary} = \oint_{circle} \rho_0 \mathbf{v} \cdot \mathbf{n} h \, dl$$

where $\mathbf{n}$ is the **outward normal** (radial direction).

#### Decomposed as:

$$F_{boundary} = \rho_0 R \int_0^{2\pi} v_r(\theta) h(\theta) d\theta$$

where the integral is over azimuthal angle.

---

### 7.2 Stokes' Theorem Application

The **net MSE flux** out of the circle equals the interior divergence:

$$F_{boundary} = \iint_A \nabla \cdot (\rho \mathbf{v} h) \, dA$$

Using the product rule:

$$\nabla \cdot (\rho \mathbf{v} h) = \mathbf{v} \cdot \nabla (\rho h) + (\rho h) \nabla \cdot \mathbf{v}$$

If we assume $\rho$ slowly varying:

$$F_{boundary} \approx \rho_0 \iint_A \mathbf{v} \cdot \nabla h + h \nabla \cdot \mathbf{v} \, dA$$

#### Interpretation:

- **First term** = MSE advection within the domain
- **Second term** = mass flux times MSE (convergence effect)

---

### 7.3 Verification of Energy Budget

The dropsonde circle should satisfy:

$$\text{Interior divergence} = \text{Boundary flux}$$

Or equivalently:

$$\iint_A \nabla \cdot (\rho \mathbf{v} h) \, dA = \oint_C \rho \mathbf{v} \cdot \mathbf{n} h \, dl$$

**If this balance is satisfied** (within measurement error), the dropsonde observations capture the true energy transport.

---

## Part 8: Practical Computational Notes

### 8.1 Handling Finite Differences

#### Circular Domain Requires Special Handling:

**Azimuthal averaging** uses **periodic boundary conditions**:
- Point 1 wraps to point $N$
- Point $N+1$ wraps to point 1

**Finite differences around circle:**

$$\frac{\partial f}{\partial \theta}\bigg|_{i} = \frac{f_{i+1 \, (mod N)} - f_{i-1 \, (mod N)}}{2 \Delta \theta}$$

---

### 8.2 Quality Control

#### Check for Errors:

1. **Mass flux closure:** $\int v_r dl$ should be consistent with $\int \omega dp$
2. **Energy budget residual:** $\text{storage} + \text{advection} - \text{sources}$ should be small (<10%)
3. **GMS physical bounds:** $-1 < G < 2$ for tropical systems
4. **Vertical motion:** $\omega$ profiles should show structure (not constant)

---

### 8.3 Vertical Integration Sensitivity

#### Critical for GMS Calculation:

The **sign and magnitude** of vertical MSE advection is **highly sensitive** to upper integration bound (Bui et al., 2016):

- **Top-heavy systems:** $\langle \omega \frac{\partial h}{\partial p} \rangle$ ranges from -8 to +40 W/m² depending on whether integration goes to 200, 100, or 50 hPa
- **Bottom-heavy systems:** Insensitive to upper bound (consistent ~-12 W/m²)

#### Recommendation:

- ✓ Use consistent integration bound (typically **100 hPa** for tropics)
- ✓ Document the choice explicitly
- ✓ Perform sensitivity analysis

---

## Part 9: Interpretation of Results

### 9.1 Profile Shape Indicators

#### Bottom-Heavy Profile:

$$
\begin{aligned}
G_V &< 0 \quad \text{(negative vertical GMS)} \\
&\Rightarrow \text{Vertical advection imports energy} \\
&\Rightarrow \text{Column moistens} \\
&\Rightarrow \text{Associated with convective amplification}
\end{aligned}
$$

#### Top-Heavy Profile:

$$
\begin{aligned}
G_V &> 0 \quad \text{(positive vertical GMS)} \\
&\Rightarrow \text{Vertical advection exports energy} \\
&\Rightarrow \text{Column dries} \\
&\Rightarrow \text{Associated with convective decay}
\end{aligned}
$$

#### Neutral/Uniform Profile:

$$
\begin{aligned}
G_V &≈ 0 \\
&\Rightarrow \text{Minimal vertical energy transport} \\
&\Rightarrow \text{Horizontal advection may dominate}
\end{aligned}
$$

---

### 9.2 Comparison to Theory

#### For a Top-Heavy Structure (Western Pacific Pattern):

| Parameter | Expected Range |
|-----------|-----------------|
| GMS | $G ≈ +0.5$ to $+1.0$ |
| Vertical component | $G_V > 0.3$ |
| Horizontal component | $G_H < 0$ (dry air advection) |

#### For a Bottom-Heavy Structure (Eastern Pacific Pattern):

| Parameter | Expected Range |
|-----------|-----------------|
| GMS | $G ≈ -0.5$ to $0.0$ |
| Vertical component | $G_V < -0.2$ |
| Horizontal component | $G_H < 0$ (similar to top-heavy) |

---

## Summary Table: Key Equations for Dropsonde Halo Analysis

| **Quantity** | **Equation** | **Units** |
|---|---|---|
| **MSE** | $h = C_p T + Lq + gz$ | J/kg |
| **Column MSE** | $\langle h \rangle = \frac{1}{g} \int h(p) dp$ | J/m² |
| **Vertical MSE advection** | $\langle \omega \frac{\partial h}{\partial p} \rangle = \frac{1}{g} \int \omega \frac{\partial h}{\partial p} dp$ | W/m² |
| **Horizontal MSE advection** | $\langle \mathbf{v} \cdot \nabla h \rangle = \frac{1}{g} \int (u \frac{\partial h}{\partial x} + v \frac{\partial h}{\partial y}) dp$ | W/m² |
| **GMS** | $G = \frac{-\langle v \cdot \nabla h \rangle}{-\langle v \cdot \nabla s \rangle}$ | Dimensionless |
| **Critical GMS** | $G_C = \frac{F}{-\langle v \cdot \nabla s \rangle}$ | Dimensionless |
| **Drying Efficiency** | $\Delta G = G - G_C$ | Dimensionless |
| **Boundary Flux (Stokes)** | $F = \oint v_r h \, dl$ | W |
| **Mass flux divergence** | $\nabla \cdot (\rho \mathbf{v}) = \frac{\partial v_r}{\partial r} + \frac{1}{r}v_r + \frac{1}{r}\frac{\partial v_\theta}{\partial \theta}$ | s⁻¹ |

---

## ✅ Conclusion

**This comprehensive framework provides all necessary equations and procedures for:**

- ✓ Calculating MSE budgets from dropsonde data
- ✓ Computing GMS and its components
- ✓ Quantifying energy transport using Stokes' theorem
- ✓ Decomposing vertical and horizontal contributions
- ✓ Interpreting convective system evolution

**Use this guide for analyzing dropsonde halo observations around tropical cyclones and other convective systems.**

---

*Last Updated: 2026-03-30*