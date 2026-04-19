# MSE & GMS Budget Methods — ORCESTRA BEACH L4
**Last updated:** 2026-04-19  
**Status:** Three methods implemented in `scripts/mse_budget.py`. Read this before touching the calculation.

---

## 1. Dataset Reality Check (what you actually have)

Before choosing a method, it's essential to know the structure of BEACH L4.

| Property | Detail |
|---|---|
| **Primary coordinate** | Altitude in **metres**, uniform **10 m spacing**, 0–14590 m (1460 levels) |
| **Circles / Sondes** | 89 circles, 1058 sondes total, ~12 sondes per circle |
| **Sonde order** | Consecutive in the `sonde` dimension; sondes for circle `i` start at `Σ sondes_per_circle[:i]` |
| **Temperature** | `ta_mean` (circle, altitude) K — NaN fraction ~6% |
| **Humidity** | `q_mean` (circle, altitude) kg/kg — NaN fraction ~14% |
| **Pressure** | `p_mean` (circle, altitude) Pa — hydrostatically consistent, NaN ~9% |
| **Omega** | `omega` (circle, altitude) Pa s⁻¹ — pre-derived from `div` integration, NaN ~9% |
| **Divergence** | `div` (circle, altitude) s⁻¹ — BEACH least-squares estimate, same NaN mask as omega |
| **Horizontal gradients** | `ta_dtadx/y`, `q_dqdx/y`, `u_dudx/y`, `v_dvdx/y` — all (circle, altitude) |
| **Per-sonde position** | `x`, `y` (sonde, altitude) m — circle-relative, **varies with altitude** (sonde drift ~3 km) |

**Key fact:** The altitude coordinate is uniform at 10 m. This matters a lot for numerical derivatives.

---

## 2. MSE and DSE Definitions

$$h = c_p T + gz + L_v q \quad \text{[J kg}^{-1}\text{]}$$
$$s = c_p T + gz \quad \text{(Dry Static Energy)}$$

| Symbol | Value |
|---|---|
| $c_p$ | 1004 J kg⁻¹ K⁻¹ |
| $g$ | 9.81 m s⁻² |
| $L_v$ | 2.501 × 10⁶ J kg⁻¹ |

In code, `z` is literally the altitude coordinate (metres). No pressure conversion needed for the MSE profile itself.

**Typical tropical values:** $h \approx 3–3.5 \times 10^5$ J kg⁻¹. This is a large number — it matters because it amplifies small errors in divergence when forming $h \cdot \nabla \cdot \mathbf{v}$ products (see Method 2 problem below).

---

## 3. Column Integral Convention

Standard meteorological column integral:

$$\langle X \rangle = \frac{1}{g} \int_{p_\text{top}}^{p_\text{sfc}} X \, dp \quad \text{[units of } X \cdot \text{Pa} / (g) \text{]}$$

For $X$ in W kg⁻¹, this gives W m⁻².

**Implementation** (in altitude space with `p_mean`):

```python
# Sort by ascending p (p_top → p_sfc), then trapezoid
idx = np.argsort(p_profile)
result = np.trapezoid(field[idx], p_profile[idx]) / g
```

---

## 4. The Altitude-Space Gradient Identity

BEACH L4 has a **uniform 10 m altitude grid** but an **irregular pressure grid** (from `p_mean`).  
Computing `∂h/∂p` numerically on the irregular pressure grid is **noisier** than computing `∂h/∂z` on the uniform altitude grid.

The exact identity (chain rule):

$$\left\langle \omega \frac{\partial h}{\partial p} \right\rangle
= \frac{1}{g} \int_{p_\text{top}}^{p_\text{sfc}} \omega \frac{\partial h}{\partial p} \, dp
= -\frac{1}{g} \int_{z_\text{bot}}^{z_\text{top}} \omega \frac{\partial h}{\partial z} \, dz$$

This is **exact** (no approximation) and allows computing vertical advection entirely in altitude space using `np.gradient(h, alt)` on the uniform 10 m grid.

**In code:**
```python
dhdz = np.gradient(h_profile, altitude)   # clean: uniform 10 m grid
vadv = -np.trapezoid(omega * dhdz, altitude) / G
```

---

## 5. Method 1 — Advective Form

### What it computes

Decomposes the column MSE budget into two additive terms:

$$\frac{\partial \langle h \rangle}{\partial t}
+ \underbrace{\langle \mathbf{v} \cdot \nabla h \rangle}_\text{horizontal advection}
+ \underbrace{\left\langle \omega \frac{\partial h}{\partial p} \right\rangle}_\text{vertical advection}
= F$$

### Computation steps

**Step 1 — MSE profile per circle** (altitude-space):
$$h(z) = c_p \cdot T_\text{mean}(z) + g \cdot z + L_v \cdot q_\text{mean}(z)$$

**Step 2 — Vertical advection** (altitude-space identity, cleanest):
$$\left\langle \omega \frac{\partial h}{\partial p} \right\rangle
= -\frac{1}{g} \int \omega(z) \frac{\partial h}{\partial z} \, dz$$
Uses `np.gradient(h, alt)` on the uniform 10 m grid. Also computed for DSE ($s$) as the denominator for normalised GMS.

**Step 3 — Horizontal advection** (pressure-weighted):
$$\langle \mathbf{v} \cdot \nabla h \rangle
= \frac{1}{g} \int (u \, \partial_x h + v \, \partial_y h) \, dp$$
where $\partial_x h = c_p \partial_x T + L_v \partial_x q$ (from `ta_dtadx`, `q_dqdx`).

**Step 4 — Normalised GMS** (Inoue & Back 2015):
$$\tilde{M}_\text{adv} = \frac{\langle \omega \, \partial h / \partial p \rangle}{\langle \omega \, \partial s / \partial p \rangle}$$

Normalising by the DSE denominator removes the dependence on the overall strength of upwelling and isolates the **shape** of the omega profile. This is the right GMS definition for RQ2.

### Numerical results

| Category | $\langle \omega \partial h/\partial p \rangle$ | $\langle \mathbf{v} \cdot \nabla h \rangle$ | GMS_adv (group mean) | GMS_adv (median) |
|---|---|---|---|---|
| Top-Heavy (n=27) | +227 W m⁻² | −31 W m⁻² | **0.29** | 0.14 |
| Bottom-Heavy (n=35) | −86 W m⁻² | +15 W m⁻² | **−0.41** | −0.03 |

### Problems found

**Problem 1: Noisy horizontal advection gradients**  
The gradient variables (`ta_dtadx`, `q_dqdx/y`) are estimated by fitting a plane to ~12 sonde observations on a ring. This is inherently noisy — you're fitting a spatial derivative from 12 noisy point measurements.  
`q_dqdx` and `q_dqdy` have **14% NaN fraction** — the highest of all variables.  
Horizontal advection (−31 / +15 W m⁻²) is small compared to vertical advection (227 / −86 W m⁻²), so this noise matters less for GMS but more for the full budget closure.

**Problem 2: Only circle-mean covariance**  
The product $u_\text{mean} \cdot (\partial h/\partial x)_\text{circle}$ captures advection by the mean flow but misses sub-circle eddy correlations $\overline{u'h'}$. These could be non-negligible.

### Suggested fixes

**Fix for Problem 1:**  
Use Method 3 (residual) to get a better horizontal advection estimate, if the boundary-term issue in Method 2 can be controlled (see below).  
Alternatively, apply a simple smoothing or outlier filter on `q_dqdx/y` before using them (e.g., reject circles where the gradient magnitude is more than 3σ from the median).

**Fix for Problem 2:**  
No fix possible from BEACH L4 alone — would require full sonde-level spatial correlation analysis. Accept this as a known limitation and document it.

---

## 6. Method 2 — Flux Form (Product Rule + BEACH `div`)

### What it computes

The **total column MSE flux divergence** via the product rule:

$$\langle \nabla \cdot (\mathbf{v} h) \rangle
= \underbrace{\langle \mathbf{v} \cdot \nabla h \rangle}_\text{advective part}
+ \underbrace{\langle h \cdot \nabla \cdot \mathbf{v} \rangle}_\text{mass-divergence part}$$

The mass-divergence part uses BEACH's pre-derived `div` field:
$$\langle h \cdot \nabla \cdot \mathbf{v} \rangle = \frac{1}{g} \int h(z) \cdot \text{div}(z) \, dp$$

**Flux GMS:**
$$\tilde{M}_\text{flux} = \frac{\langle \nabla \cdot (\mathbf{v}h) \rangle}{\langle \nabla \cdot (\mathbf{v}s) \rangle}$$

### What was tried first and why it failed

**Per-sonde line integral (discarded):**  
The first attempt computed flux divergence directly from per-sonde data using the divergence theorem:
$$\langle \nabla \cdot (\mathbf{v}h) \rangle_z \approx \frac{2}{n R} \sum_i v_{r,i}(z) \, h_i(z)$$
where $v_{r,i} = (u_i x_i + v_i y_i) / |r_i|$ is the outward radial wind.

**The diagnostic test:**  
Comparing `(2/nR) * Σ vr_i` (ring formula estimate of divergence) against BEACH `div` at the same level:

| Level | Ring formula | BEACH div |
|---|---|---|
| Launch altitude (~12 km) | **−3.2 × 10⁻⁵ s⁻¹** (wrong sign) | +9.1 × 10⁻⁶ s⁻¹ |
| Near surface (~100 m) | +6.4 × 10⁻⁶ s⁻¹ (agrees) | +7.2 × 10⁻⁶ s⁻¹ |

**Factor of ~4 discrepancy with wrong sign at launch altitude.** The ring formula breaks at the launch level because sondes have just been released from the aircraft — they cluster at the launch position and don't yet represent a well-distributed ring. BEACH handles this by using a least-squares fit to all available sonde positions at each altitude, which is robust to irregular spacing.

Surface level agrees because by the time sondes reach the surface they have spread out into a well-distributed ring.

**Consequence:** The per-sonde line integral gave physically nonsensical flux divergence values (~1300 W m⁻² for top-heavy vs expected ~200 W m⁻²).

### The boundary-term problem (unavoidable with current data)

Even with the correct BEACH `div`, there is a fundamental issue. Integration by parts shows:

$$\langle h \cdot \nabla \cdot \mathbf{v} \rangle
= \underbrace{\left\langle \omega \frac{\partial h}{\partial p} \right\rangle}_\text{vertical advection}
+ \underbrace{\frac{[h \omega]_\text{boundaries}}{g}}_\text{boundary term}$$

If $\omega = 0$ at **both** boundaries (surface and tropopause), the boundary term vanishes and $\langle h \cdot \nabla \cdot \mathbf{v} \rangle = \langle \omega \, \partial h / \partial p \rangle$, which makes Methods 1 and 2 equivalent.

**BEACH L4 boundary conditions:**  
BEACH derives omega by integrating `div` from one boundary with $\omega = 0$ imposed there. The other boundary is **not** constrained. BEACH profiles reach ~16 km but the tropical tropopause is ~17 km, so $\omega$ at the top of profiles is **non-zero** (typically ~0.02–0.15 Pa/s).

**Estimated boundary term magnitude:**  
$h_\text{top} \cdot \omega_\text{top} / g \approx 3.4 \times 10^5 \times 0.1 / 9.81 \approx 3500$ W m⁻²

This is an order of magnitude larger than the physical signal (~200 W m⁻²).

### Numerical results

| Category | $\langle \nabla \cdot (\mathbf{v}h) \rangle$ | GMS_flux |
|---|---|---|
| Top-Heavy (n=27) | −5322 W m⁻² | 1.97 |
| Bottom-Heavy (n=35) | +237 W m⁻² | 0.51 |

The top-heavy value is dominated by the boundary term. The bottom-heavy value is closer to Method 1 because bottom-heavy circles have weaker omega at the profile top.

### Problems found

**Problem 1: Open-boundary error dominates for top-heavy circles**  
The $\langle h \cdot \nabla \cdot \mathbf{v} \rangle$ term does not reduce to $\langle \omega \, \partial h / \partial p \rangle$ when $\omega \neq 0$ at the top of the profile. The error scales with $h_\text{top} \cdot \omega_\text{top} / g$, and $\omega_\text{top}$ is larger for top-heavy circles (stronger upper-tropospheric upwelling). This makes GMS_flux unreliable for the research question.

**Problem 2: Large h amplifies div errors**  
$h \approx 3.5 \times 10^5$ J kg⁻¹. Any small error in `div` gets multiplied by this large number. For example, a div error of $10^{-6}$ s⁻¹ creates an error of $3.5 \times 10^5 \times 10^{-6} = 0.35$ W kg⁻¹, which column-integrates to ~$3000$ W m⁻².

### Suggested fixes

**Fix for Problem 1 (most important):**  
Apply an explicit boundary-term correction:
$$\langle \nabla \cdot (\mathbf{v}h) \rangle_\text{corrected}
= \langle h \cdot \nabla \cdot \mathbf{v} \rangle_\text{computed}
- \frac{h_\text{top} \, \omega_\text{top}}{g} + \frac{h_\text{sfc} \, \omega_\text{sfc}}{g}$$

where $h_\text{top}$, $\omega_\text{top}$ are taken at the highest valid altitude in each circle's profile. This requires knowing the BEACH boundary condition precisely (which end has $\omega = 0$).

**Alternative fix:**  
Work only with **anomaly MSE**: $h' = h - \bar{h}(z)$ where $\bar{h}(z)$ is the campaign mean profile at each altitude. Then $\langle h' \cdot \nabla \cdot \mathbf{v} \rangle$ removes the large background contribution and the boundary error scales with $\bar{h}'_\text{top}$ instead of $h_\text{top}$. This changes the physical interpretation (you're now computing anomaly export, not total export), but the result is more numerically stable.

**Fix for Problem 2:**  
Same as above — use anomaly MSE to reduce the effective magnitude of $h$.

---

## 7. Method 3 — Residual Horizontal Advection

### What it computes

Uses the product-rule identity to isolate horizontal advection as a residual:

$$\langle \mathbf{v} \cdot \nabla h \rangle_\text{res}
= \langle \nabla \cdot (\mathbf{v}h) \rangle
- \left\langle \omega \frac{\partial h}{\partial p} \right\rangle$$

Expanding using the integration-by-parts relation:

$$\langle \mathbf{v} \cdot \nabla h \rangle_\text{res}
= \langle \mathbf{v} \cdot \nabla h \rangle_\text{direct}
+ \underbrace{\frac{[h\omega]_\text{boundaries}}{g}}_\text{boundary term}$$

**This is also a diagnostic:** the difference between $\langle h \cdot \nabla \cdot \mathbf{v} \rangle$ and $\langle \omega \, \partial h / \partial p \rangle$ directly measures the boundary term, which tells you how "open" the top of the BEACH profile is.

### Numerical results

| Category | $\langle \mathbf{v} \cdot \nabla h \rangle_\text{res}$ | Boundary term |
|---|---|---|
| Top-Heavy (n=27) | −5550 W m⁻² | **−5519 W m⁻²** |
| Bottom-Heavy (n=35) | +323 W m⁻² | +307 W m⁻² |

**The boundary term completely dominates the residual.** This means Method 3 does NOT give a reliable horizontal advection estimate with the current data.

However, the asymmetry is physically meaningful: the top-heavy boundary term is ~18× larger than for bottom-heavy. This directly reflects that top-heavy circles have stronger omega at the top of the profile (upward motion persisting to the upper troposphere), exactly consistent with the omega profile shape.

### Problems found

**Problem 1: Boundary term > actual signal by ~100×**  
For top-heavy circles, the residual is −5550 W m⁻² but the true horizontal advection from Method 1 is only −31 W m⁻². The boundary term (~5519 W m⁻²) overwhelms the physical signal.

**Problem 2: Sensitive to BEACH boundary condition choice**  
If BEACH sets $\omega = 0$ at the surface (bottom), then $\omega_\text{top} \neq 0$ and the boundary term is large (as seen). If BEACH sets $\omega = 0$ at the top, then $\omega_\text{sfc} \neq 0$ and the boundary term still exists (at the surface, where $h_\text{sfc}$ is also large).

### Suggested fixes

**Fix for Problem 1:**  
Determine exactly which boundary condition BEACH uses for omega integration (check the BEACH Level-4 paper — most likely $\omega = 0$ at the surface). Then correct:
$$\langle \mathbf{v} \cdot \nabla h \rangle_\text{corrected}
= \langle \mathbf{v} \cdot \nabla h \rangle_\text{res}
- h_\text{top} \cdot \omega_\text{top} / g$$

With $h_\text{top}$ and $\omega_\text{top}$ from the highest valid level of each circle.

**Fix for Problem 2 (conceptual):**  
Extend BEACH profiles to the tropopause by blending with ERA5 data above the profile top. This is the cleanest fix but requires ERA5 integration (which is already planned for this project).

---

## 8. Summary Table

| | Method 1 (Advective) | Method 2 (Flux) | Method 3 (Residual) |
|---|---|---|---|
| **What it gives** | $\langle \omega \partial h/\partial p \rangle$ + $\langle \mathbf{v} \cdot \nabla h \rangle$ | $\langle \nabla \cdot (\mathbf{v}h) \rangle$ | $\langle \mathbf{v} \cdot \nabla h \rangle_\text{res}$ + boundary diagnostic |
| **GMS definition** | $\langle \omega \partial h/\partial p \rangle / \langle \omega \partial s/\partial p \rangle$ | $\langle \nabla \cdot (\mathbf{v}h) \rangle / \langle \nabla \cdot (\mathbf{v}s) \rangle$ | N/A (boundary-dominated) |
| **Reliability** | **High** | **Low** (boundary term) | **Low** (boundary-dominated) |
| **Best for RQ2?** | **Yes** — directly captures omega-shape effect | No (for current data) | No (for current data) |
| **Main problem** | Noisy horiz. adv. gradients | Open boundary, large $h$ amplification | Boundary term ~100× signal |
| **Fix status** | Acceptable as-is | Needs boundary correction or anomaly approach | Needs BEACH boundary info or ERA5 extension |

---

## 9. Recommendation for RQ2

**Use Method 1 GMS_adv as the primary metric.**

$$\tilde{M}_\text{adv} = \frac{\langle \omega \, \partial h / \partial p \rangle}{\langle \omega \, \partial s / \partial p \rangle}$$

It is:
- The only method unaffected by the open-boundary problem
- Directly connected to the omega profile shape (top-heavy vs bottom-heavy)
- Numerically stable (uses `∂h/∂z` on the uniform 10 m grid)
- Physically interpretable: how efficiently the omega profile exports MSE relative to DSE

**Current results support the expected direction of RQ2:**  
Top-heavy GMS_adv (0.29) > Bottom-heavy GMS_adv (−0.03 median), consistent with the theoretical chain:
$$\text{Top-Heavy } \omega \rightarrow \text{Larger GMS} \rightarrow \text{More efficient energy export}$$

**Method 2 and 3 are useful for:**
- Documenting the budget closure problem (boundary term)
- Future work: boundary term correction using ERA5 above profile top
- Showing asymmetry in boundary term magnitude between top/bottom heavy (itself a physically interesting result)

---

## 10. Code Reference

All three methods are in [scripts/mse_budget.py](../scripts/mse_budget.py).

```python
from scripts.mse_budget import compute_budget, load_dataset

ds = load_dataset()
budget = compute_budget(ds)

# Key outputs
budget["gms_adv"]        # Method 1 normalised GMS per circle
budget["vert_adv"]       # Method 1 <ω ∂h/∂p> per circle [W m⁻²]
budget["horiz_adv"]      # Method 1 <v·∇h> per circle [W m⁻²]
budget["flux_div_mse"]   # Method 2 <∇·(vh)> per circle [W m⁻²]
budget["gms_flux"]       # Method 2 GMS per circle
budget["horiz_adv_res"]  # Method 3 residual horiz. adv. [W m⁻²]
budget["h_div_residual"] # Method 3 boundary term diagnostic [W m⁻²]
```

**CLI quick check:**
```bash
/g/data/k10/zr7147/orcestra_env/bin/python scripts/mse_budget.py
```
