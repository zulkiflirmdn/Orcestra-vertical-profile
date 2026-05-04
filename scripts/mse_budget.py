"""
MSE Budget — Three Methods for ORCESTRA BEACH L4 Dropsonde Circles
===================================================================

Method 1  Advective   : <v·∇h> + <ω ∂h/∂p> from circle-mean fields.
                        GMS_adv = <ω ∂h/∂p> / <ω ∂s/∂p>

Method 2  Flux        : <∇·(vh)> decomposed as <v·∇h> + <h·∇·v>, where the
                        mass-divergence term <h·∇·v> uses the BEACH-derived `div`
                        field (robust least-squares estimate from the sonde ring).
                        GMS_flux = <∇·(vh)> / <∇·(vs)>

                        NOTE: a per-sonde line-integral approach was tested and
                        discarded — at the aircraft launch level the simple ring
                        formula disagrees with BEACH div by a factor of ~4 (wrong
                        sign) because BEACH uses a least-squares fit that properly
                        accounts for irregular sonde positions, whereas the ring
                        formula assumes equally-spaced sondes on a perfect circle.

Method 3  Residual    : <v·∇h>_res = <∇·(vh)> − <ω ∂h/∂p>
                        Uses the product-rule identity:
                            <∇·(vh)> ≡ <v·∇h> + <h·∇·v>
                        and the integration-by-parts relation:
                            <h·∇·v> = <ω ∂h/∂p> + [h ω / g]_boundaries
                        So the residual equals:
                            <v·∇h>_res = <v·∇h>_direct + [h ω / g]_boundaries
                        When BEACH imposes ω = 0 at both ends the boundary term
                        vanishes and Methods 1 & 3 must agree.  Any discrepancy
                        quantifies the open-boundary error.

Numerical strategy
------------------
BEACH L4 stores profiles on a UNIFORM 10 m altitude grid.  All vertical
derivatives are therefore computed in altitude space (∂/∂z) rather than
on the irregular pressure grid:

    <ω ∂h/∂p>  ≡  −(1/g) ∫_{z_bot}^{z_top} ω (∂h/∂z) dz

This is exact (chain rule) and avoids differentiating h over a gappy,
irregular pressure grid.  Column integrals that require pressure
weighting (horizontal advection, flux divergence) use p_mean with
trapezoid integration over the altitude coordinate.

References
----------
Inoue & Back (2015)  doi:10.1175/JAS-D-15-0111.1
Raymond et al. (2009) doi:10.3894/JAMES.2009.1.9
Bony & Stevens (2019) doi:10.1175/JAS-D-19-0087.1
"""

import numpy as np
import xarray as xr

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------
CP   = 1004.0      # specific heat at constant pressure  [J kg⁻¹ K⁻¹]
G    = 9.81        # gravitational acceleration          [m s⁻²]
LV   = 2.501e6     # latent heat of vaporisation         [J kg⁻¹]
RD   = 287.05      # specific gas constant for dry air   [J kg⁻¹ K⁻¹]

# GMS denominator guard — set GMS to NaN if |denominator| < this [W m⁻²]
GMS_DENOM_MIN = 10.0

DEFAULT_ZARR = "/g/data/k10/zr7147/ORCESTRA_dropsondes_categorized.zarr"
# DEFAULT_NC is kept for legacy compat only — always prefer DEFAULT_ZARR
DEFAULT_NC   = DEFAULT_ZARR


# ===========================================================================
# Helpers
# ===========================================================================

def load_dataset(path=DEFAULT_ZARR):
    """Load the categorized BEACH L4 dataset (zarr — canonical source)."""
    import pathlib
    p = str(path)
    if p.endswith(".zarr") or pathlib.Path(p).is_dir():
        return xr.open_zarr(p)
    return xr.open_dataset(p)


def _mse(T, z, q):
    """Moist static energy  h = cp T + g z + Lv q  [J kg⁻¹].  z in metres."""
    return CP * T + G * z + LV * q


def _dse(T, z):
    """Dry static energy  s = cp T + g z  [J kg⁻¹].  z in metres."""
    return CP * T + G * z


def _col_int_p(field_z, p_z):
    """
    Column integral  (1/g) ∫_{p_top}^{p_sfc} X dp  [field_units · Pa / (m s⁻²)].

    Both arrays are on the altitude grid and may contain NaNs.
    Integration is ordered p_top → p_sfc (ascending pressure).
    """
    valid = np.isfinite(field_z) & np.isfinite(p_z)
    if valid.sum() < 3:
        return np.nan
    p_v = p_z[valid]
    f_v = field_z[valid]
    idx = np.argsort(p_v)          # ascending: p_top first
    return np.trapezoid(f_v[idx], p_v[idx]) / G


def _vadv_col(omega_z, h_z, alt):
    """
    Column vertical MSE/DSE advection using the altitude-space identity:
        <ω ∂h/∂p>  =  −(1/g) ∫_{z_bot}^{z_top} ω (∂h/∂z) dz

    ∂h/∂z is computed on the uniform 10 m grid → numerically clean.
    omega_z and h_z are on the same altitude grid (may have NaNs).
    """
    dhdz = np.gradient(h_z, alt)          # finite differences on uniform grid
    valid = np.isfinite(omega_z) & np.isfinite(dhdz)
    if valid.sum() < 3:
        return np.nan
    # Integrate from z_bot to z_top (alt is ascending), negate per the identity
    return -np.trapezoid(omega_z[valid] * dhdz[valid], alt[valid]) / G


def _safe_gms(numerator, denominator, threshold=GMS_DENOM_MIN):
    """Return numerator/denominator or NaN if denominator is near zero."""
    if np.isfinite(denominator) and abs(denominator) > threshold:
        return numerator / denominator
    return np.nan


# ===========================================================================
# Method 1 — Advective form  (circle-mean fields)
# ===========================================================================

def method1_advective(ds):
    """
    Compute the MSE budget using circle-mean fields.

    Vertical advection  <ω ∂h/∂p>  uses ∂h/∂z on the uniform altitude grid
    (see module docstring).  Horizontal advection  <v·∇h>  uses the circle-
    mean gradient variables (ta_dtadx, q_dqdx, …) with pressure-weighted
    column integration.

    Returns xr.Dataset with per-circle variables:
        h_profile       MSE profile h(z)                   [J kg⁻¹]
        s_profile       DSE profile s(z)                   [J kg⁻¹]
        col_h           Column-integrated MSE <h>           [J m⁻²]
        vert_adv        <ω ∂h/∂p>  vertical MSE advection   [W m⁻²]
        vert_adv_dse    <ω ∂s/∂p>  vertical DSE advection   [W m⁻²]
        horiz_adv       <v·∇h>   horizontal MSE advection   [W m⁻²]
        horiz_adv_dse   <v·∇s>   horizontal DSE advection   [W m⁻²]
        gms_adv         Normalised GMS = vert_adv/vert_adv_dse  [–]
    """
    alt   = ds["altitude"].values          # (nalt,) metres, uniform 10 m
    T     = ds["ta_mean"].values           # (ncircle, nalt)
    q     = ds["q_mean"].values
    p     = ds["p_mean"].values            # Pa
    omega = ds["omega"].values             # Pa s⁻¹
    u     = ds["u_mean"].values            # m s⁻¹
    v     = ds["v_mean"].values

    # Horizontal MSE gradients  ∂h/∂x ≈ cp ∂T/∂x + Lv ∂q/∂x
    # (the g ∂z/∂x term is zero on constant-altitude levels)
    dhdx = CP * ds["ta_dtadx"].values + LV * ds["q_dqdx"].values
    dhdy = CP * ds["ta_dtady"].values + LV * ds["q_dqdy"].values
    dsdx = CP * ds["ta_dtadx"].values
    dsdy = CP * ds["ta_dtady"].values

    ncircle = ds.sizes["circle"]
    nalt    = ds.sizes["altitude"]

    h_prof = _mse(T, alt[np.newaxis, :], q)     # (ncircle, nalt)
    s_prof = _dse(T, alt[np.newaxis, :])

    col_h         = np.full(ncircle, np.nan)
    vert_adv      = np.full(ncircle, np.nan)
    vert_adv_dse  = np.full(ncircle, np.nan)
    horiz_adv     = np.full(ncircle, np.nan)
    horiz_adv_dse = np.full(ncircle, np.nan)
    gms_adv       = np.full(ncircle, np.nan)

    for i in range(ncircle):
        p_i  = p[i]
        om_i = omega[i]

        col_h[i] = _col_int_p(h_prof[i], p_i)

        # Vertical advection — altitude-space identity
        vert_adv[i]     = _vadv_col(om_i, h_prof[i], alt)
        vert_adv_dse[i] = _vadv_col(om_i, s_prof[i], alt)

        # Horizontal advection — pressure-weighted column integral
        hadv_h_i = u[i] * dhdx[i] + v[i] * dhdy[i]   # J kg⁻¹ s⁻¹ per level
        hadv_s_i = u[i] * dsdx[i] + v[i] * dsdy[i]
        horiz_adv[i]     = _col_int_p(hadv_h_i, p_i)
        horiz_adv_dse[i] = _col_int_p(hadv_s_i, p_i)

        gms_adv[i] = _safe_gms(vert_adv[i], vert_adv_dse[i])

    return xr.Dataset(
        {
            "h_profile":      (("circle", "altitude"), h_prof),
            "s_profile":      (("circle", "altitude"), s_prof),
            "col_h":          ("circle", col_h),
            "vert_adv":       ("circle", vert_adv),
            "vert_adv_dse":   ("circle", vert_adv_dse),
            "horiz_adv":      ("circle", horiz_adv),
            "horiz_adv_dse":  ("circle", horiz_adv_dse),
            "gms_adv":        ("circle", gms_adv),
        },
        coords={
            "circle":      ds["circle"],
            "altitude":    ds["altitude"],
            "circle_time": ds["circle_time"],
        },
        attrs={"method": "advective",
               "description": "MSE budget via circle-mean advective decomposition."},
    )


# ===========================================================================
# Method 2 — Flux form  (product rule + BEACH divergence field)
# ===========================================================================

def method2_flux(ds):
    """
    Compute the total column MSE/DSE flux divergence using the product rule:

        ∇·(vh) = v·∇h  +  h · (∇·v)

    The two terms are column-integrated separately:
        <v·∇h>    : same gradient-product as Method 1 (circle-mean fields).
        <h·∇·v>   : uses BEACH's `div` field — a robust least-squares estimate
                    of area-averaged divergence from the sonde ring.

    Why not a per-sonde line integral?
        A ring-formula test showed that at the aircraft launch level the simple
        line integral disagrees with BEACH div by ~4× (wrong sign) because
        sondes bunch together right at launch.  BEACH's least-squares fit
        handles the irregular geometry correctly; the ring formula does not.

    Relation to Method 1 (integration by parts):
        <h·∇·v> = <ω ∂h/∂p> + [h ω / g]_boundaries
        So <∇·(vh)>_flux = <v·∇h> + <ω ∂h/∂p> + boundary_term.
        The boundary term quantifies the open-top error (ω ≠ 0 at top of
        BEACH profiles).  Method 3 exposes it explicitly.

    GMS_flux = <∇·(vh)> / <∇·(vs)>  — total MSE export efficiency.

    Returns xr.Dataset with per-circle variables:
        h_div_col      <h · ∇·v>  column mass-divergence MSE term  [W m⁻²]
        s_div_col      <s · ∇·v>  column mass-divergence DSE term  [W m⁻²]
        flux_div_mse   <∇·(vh)>   total column MSE flux divergence  [W m⁻²]
        flux_div_dse   <∇·(vs)>   total column DSE flux divergence  [W m⁻²]
        gms_flux       GMS = flux_div_mse / flux_div_dse            [–]
    """
    alt   = ds["altitude"].values      # (nalt,) metres, uniform 10 m
    T     = ds["ta_mean"].values       # (ncircle, nalt)
    q     = ds["q_mean"].values
    p     = ds["p_mean"].values        # Pa
    div   = ds["div"].values           # s⁻¹  — BEACH least-squares divergence
    u     = ds["u_mean"].values
    v_w   = ds["v_mean"].values

    dhdx = CP * ds["ta_dtadx"].values + LV * ds["q_dqdx"].values
    dhdy = CP * ds["ta_dtady"].values + LV * ds["q_dqdy"].values
    dsdx = CP * ds["ta_dtadx"].values
    dsdy = CP * ds["ta_dtady"].values

    ncircle = ds.sizes["circle"]

    h_prof = _mse(T, alt[np.newaxis, :], q)   # (ncircle, nalt)
    s_prof = _dse(T, alt[np.newaxis, :])

    h_div_col    = np.full(ncircle, np.nan)
    s_div_col    = np.full(ncircle, np.nan)
    flux_div_mse = np.full(ncircle, np.nan)
    flux_div_dse = np.full(ncircle, np.nan)
    gms_flux     = np.full(ncircle, np.nan)

    for i in range(ncircle):
        p_i = p[i]

        # <h · ∇·v>  =  (1/g) ∫ h * div dp
        h_div_col[i] = _col_int_p(h_prof[i] * div[i], p_i)
        s_div_col[i] = _col_int_p(s_prof[i] * div[i], p_i)

        # <v · ∇h>  (same as Method 1)
        hadv_h = u[i] * dhdx[i] + v_w[i] * dhdy[i]
        hadv_s = u[i] * dsdx[i] + v_w[i] * dsdy[i]
        horiz_h = _col_int_p(hadv_h, p_i)
        horiz_s = _col_int_p(hadv_s, p_i)

        # Total flux divergence
        flux_div_mse[i] = horiz_h + h_div_col[i]
        flux_div_dse[i] = horiz_s + s_div_col[i]
        gms_flux[i]     = _safe_gms(flux_div_mse[i], flux_div_dse[i])

    return xr.Dataset(
        {
            "h_div_col":    ("circle", h_div_col),
            "s_div_col":    ("circle", s_div_col),
            "flux_div_mse": ("circle", flux_div_mse),
            "flux_div_dse": ("circle", flux_div_dse),
            "gms_flux":     ("circle", gms_flux),
        },
        coords={
            "circle":      ds["circle"],
            "circle_time": ds["circle_time"],
        },
        attrs={"method": "flux",
               "description": "Column MSE/DSE flux divergence via product rule "
                              "using BEACH div field for the mass-divergence term."},
    )


# ===========================================================================
# Method 3 — Residual horizontal advection
# ===========================================================================

def method3_residual(adv_ds, flux_ds):
    """
    Derive residual horizontal advection and expose the boundary-term error.

    From the product rule and integration by parts:

        <∇·(vh)>  =  <v·∇h>  +  <h·∇·v>
        <h·∇·v>   =  <ω ∂h/∂p>  +  [h ω / g]_boundaries

    Combining:
        <v·∇h>_res  =  <∇·(vh)> − <ω ∂h/∂p>
                     =  <v·∇h>_direct  +  [h ω / g]_boundaries

    If BEACH imposes ω = 0 at BOTH boundaries, the boundary term is zero
    and horiz_adv_res == horiz_adv (Method 1 direct).  Any discrepancy
    between them is the boundary-term error — a useful diagnostic for how
    open the top of the BEACH profile is.

    The mass-divergence residual:
        h_div_residual  =  <h·∇·v> − <ω ∂h/∂p>
                        =  [h ω / g]_boundaries
    directly quantifies the boundary term.

    Returns xr.Dataset with per-circle variables:
        horiz_adv_res      <v·∇h>_res = <∇·(vh)> − <ω ∂h/∂p>  [W m⁻²]
        horiz_adv_dse_res  DSE equivalent                        [W m⁻²]
        h_div_residual     <h·∇·v> − <ω ∂h/∂p>  (boundary term) [W m⁻²]
        s_div_residual     DSE equivalent                         [W m⁻²]
    """
    horiz_adv_res     = flux_ds["flux_div_mse"] - adv_ds["vert_adv"]
    horiz_adv_dse_res = flux_ds["flux_div_dse"] - adv_ds["vert_adv_dse"]
    h_div_resid       = flux_ds["h_div_col"]    - adv_ds["vert_adv"]
    s_div_resid       = flux_ds["s_div_col"]    - adv_ds["vert_adv_dse"]

    return xr.Dataset(
        {
            "horiz_adv_res":     horiz_adv_res.rename(None),
            "horiz_adv_dse_res": horiz_adv_dse_res.rename(None),
            "h_div_residual":    h_div_resid.rename(None),
            "s_div_residual":    s_div_resid.rename(None),
        },
        coords={
            "circle":      adv_ds["circle"],
            "circle_time": adv_ds["circle_time"],
        },
        attrs={"method": "residual",
               "description": "Residual horizontal advection and boundary-term "
                              "diagnostics from Methods 1 and 2."},
    )


# ===========================================================================
# Combined — all three methods
# ===========================================================================

def compute_budget(ds=None, zarr_path=DEFAULT_ZARR, mass_correct=False):
    """
    Compute the full MSE budget using all three methods and return one Dataset.

    Parameters
    ----------
    ds : xr.Dataset or None
        BEACH L4 dataset.  Loaded from DEFAULT_ZARR if None.
    zarr_path : str
        Path to the zarr store (used only if ds is None).
    mass_correct : bool
        If True, apply the unified mass correction (apply_mass_correction) before
        running any method.  This forces ω=0 at both profile ends and applies the
        consistent depth-uniform correction to div.  After correction, Methods 1,
        2, and 3 are internally consistent and h_div_residual ≈ 0 (closure check).
        Default False preserves the original uncorrected behaviour.

    Method 1 variables : h_profile, s_profile, col_h, vert_adv, vert_adv_dse,
                         horiz_adv, horiz_adv_dse, gms_adv
    Method 2 variables : flux_div_mse, flux_div_dse, gms_flux
    Method 3 variables : horiz_adv_res, horiz_adv_dse_res, h_div_residual
    Extra (if mass_correct) : delta_div

    Metadata carried over from the input dataset:
                         omega, category_evolutionary, category_avg,
                         top_heaviness_angle
    """
    if ds is None:
        ds = load_dataset(zarr_path)

    delta_div = None
    if mass_correct:
        ds, delta_div = apply_mass_correction(ds)

    adv_ds  = method1_advective(ds)
    flux_ds = method2_flux(ds)
    res_ds  = method3_residual(adv_ds, flux_ds)

    meta_vars = ["omega", "category_plane", "category_evolutionary", "category_avg",
                 "top_heaviness_angle"]

    out = xr.merge([adv_ds, flux_ds, res_ds])

    for v in meta_vars:
        if v in ds:
            out[v] = ds[v]

    if mass_correct and delta_div is not None:
        out["delta_div"] = ("circle", delta_div)

    out.attrs.update(
        {
            "methods": "advective + flux + residual",
            "mass_corrected": str(mass_correct),
            "description": "Full MSE budget for ORCESTRA BEACH L4 circles.",
        }
    )
    return out


# ===========================================================================
# Fix-idea helpers  (for exploration and future correction of Methods 2 & 3)
# ===========================================================================

def compute_boundary_term(ds):
    """
    Idea A — Explicit boundary correction.

    Quantify the open-boundary error in Method 2/3:

        boundary_term_i = h_top_i * omega_top_i / g   [W m⁻²]

    where "top" is the highest valid altitude in circle i's profile.

    This is the term that prevents <h·∇·v> from equalling <ω ∂h/∂p> when
    ω ≠ 0 at the profile top.  If you subtract it from Method 2's
    flux_div_mse, you recover the identity:

        <∇·(vh)>_corrected  ≈  <v·∇h>  +  <ω ∂h/∂p>

    Returns xr.Dataset with per-circle variables:
        z_top          Highest valid altitude [m]
        p_top          Pressure at that level [Pa]
        h_top          MSE at that level      [J kg⁻¹]
        omega_top      ω at that level        [Pa s⁻¹]
        boundary_term  h_top * omega_top / g  [W m⁻²]
    """
    alt   = ds["altitude"].values
    T     = ds["ta_mean"].values
    q     = ds["q_mean"].values
    p     = ds["p_mean"].values
    omega = ds["omega"].values
    ncircle = ds.sizes["circle"]

    h_prof = _mse(T, alt[np.newaxis, :], q)

    z_top_arr    = np.full(ncircle, np.nan)
    p_top_arr    = np.full(ncircle, np.nan)
    h_top_arr    = np.full(ncircle, np.nan)
    om_top_arr   = np.full(ncircle, np.nan)
    bnd_arr      = np.full(ncircle, np.nan)

    for i in range(ncircle):
        valid = np.isfinite(omega[i]) & np.isfinite(h_prof[i]) & np.isfinite(p[i])
        if valid.sum() < 3:
            continue
        idx_top = np.where(valid)[0][-1]      # highest valid altitude index
        z_top_arr[i]  = alt[idx_top]
        p_top_arr[i]  = p[i, idx_top]
        h_top_arr[i]  = h_prof[i, idx_top]
        om_top_arr[i] = omega[i, idx_top]
        bnd_arr[i]    = h_top_arr[i] * om_top_arr[i] / G

    return xr.Dataset(
        {
            "z_top":         ("circle", z_top_arr),
            "p_top":         ("circle", p_top_arr),
            "h_top":         ("circle", h_top_arr),
            "omega_top":     ("circle", om_top_arr),
            "boundary_term": ("circle", bnd_arr),
        },
        coords={"circle": ds["circle"], "circle_time": ds["circle_time"]},
        attrs={"description": "Open-boundary diagnostic: h_top * omega_top / g."},
    )


def omega_mass_corrected(ds):
    """
    Idea B — Linear mass correction (force ω = 0 at both profile ends).

    BEACH derives omega by integrating div upward from the surface (ω_sfc = 0).
    The profile ends at ~16 km, short of the tropopause, so ω_top ≠ 0 in general.

    This function applies a linear-in-pressure correction that forces ω → 0 at
    the top of the integration domain:

        ω_corr(p) = ω(p) − ω_top · (p_sfc − p) / (p_sfc − p_top)

    At p = p_top : correction = ω_top  →  ω_corr = 0  ✓
    At p = p_sfc : correction = 0      →  ω_corr = ω_sfc (preserves surface BC)

    The corresponding divergence adjustment is depth-uniform in pressure:
        Δdiv = ω_top / (p_sfc − p_top)   [s⁻¹, constant throughout column]

    Critical: the valid mask uses the SAME criteria as _vadv_col and _col_int_p
    (finite omega AND p AND h_prof), so the correction zeros omega exactly at the
    top of the range that those functions integrate over.  Using a looser mask
    (e.g., only omega & p) moves the zero to a higher, unused altitude level and
    leaves the boundary term unaffected.

    Returns:
        omega_corr  (ncircle, nalt) ndarray  [Pa s⁻¹]
        delta_div   (ncircle,)      ndarray  [s⁻¹]  uniform div adjustment per circle
    """
    alt   = ds["altitude"].values
    T     = ds["ta_mean"].values
    q     = ds["q_mean"].values
    p     = ds["p_mean"].values
    omega = ds["omega"].values
    ncircle = ds.sizes["circle"]

    h_prof = _mse(T, alt[np.newaxis, :], q)

    omega_corr = omega.copy().astype(float)
    delta_div  = np.full(ncircle, np.nan)

    for i in range(ncircle):
        # Same valid mask as _vadv_col: all three arrays must be finite.
        valid = np.isfinite(omega[i]) & np.isfinite(p[i]) & np.isfinite(h_prof[i])
        if valid.sum() < 3:
            continue
        idx_valid = np.where(valid)[0]
        idx_bot   = idx_valid[0]
        idx_top   = idx_valid[-1]

        p_sfc  = p[i, idx_bot]
        p_top  = p[i, idx_top]
        om_top = omega[i, idx_top]

        if abs(p_sfc - p_top) < 1e3:
            continue

        correction = om_top * (p_sfc - p[i, idx_valid]) / (p_sfc - p_top)
        omega_corr[i, idx_valid] -= correction
        delta_div[i] = om_top / (p_sfc - p_top)

    return omega_corr, delta_div


def anomaly_mse(ds):
    """
    Idea C — Campaign-mean anomaly MSE/DSE.

    Replace h with its anomaly from the campaign-mean profile:
        h'(circle, z) = h(circle, z) − h̄(z)
        s'(circle, z) = s(circle, z) − s̄(z)

    Why this helps Method 2:
        The large background value of h (~3.5 × 10⁵ J kg⁻¹) amplifies any
        error in div or boundary terms.  Using h' reduces the effective
        magnitude by an order of magnitude and removes the mean background
        contribution, which carries no information about circle-to-circle
        variability.

    Returns:
        h_prime  (ncircle, nalt) ndarray  [J kg⁻¹]  MSE anomaly
        s_prime  (ncircle, nalt) ndarray  [J kg⁻¹]  DSE anomaly
        h_mean   (nalt,)         ndarray  [J kg⁻¹]  campaign-mean MSE profile
        s_mean   (nalt,)         ndarray  [J kg⁻¹]  campaign-mean DSE profile
    """
    alt   = ds["altitude"].values
    T     = ds["ta_mean"].values
    q     = ds["q_mean"].values

    h_prof = _mse(T, alt[np.newaxis, :], q)
    s_prof = _dse(T, alt[np.newaxis, :])

    h_mean  = np.nanmean(h_prof, axis=0)   # (nalt,)
    s_mean  = np.nanmean(s_prof, axis=0)

    h_prime = h_prof - h_mean[np.newaxis, :]
    s_prime = s_prof - s_mean[np.newaxis, :]

    return h_prime, s_prime, h_mean, s_mean


def method2_flux_anomaly(ds):
    """
    Idea C applied — Method 2 flux form using anomaly MSE/DSE.

    Replaces h → h' = h − h̄(z) in the mass-divergence term:
        <∇·(v h')> = <v·∇h> + <h'·∇·v>

    Note: horizontal gradients ∂h/∂x, ∂h/∂y are unchanged (the mean
    profile h̄(z) is spatially uniform so its gradient is zero).

    Returns xr.Dataset with same variables as method2_flux() but computed
    with the anomaly MSE, reducing the boundary-term error.
    """
    alt   = ds["altitude"].values
    T     = ds["ta_mean"].values
    q     = ds["q_mean"].values
    p     = ds["p_mean"].values
    div   = ds["div"].values
    u     = ds["u_mean"].values
    v_w   = ds["v_mean"].values

    dhdx = CP * ds["ta_dtadx"].values + LV * ds["q_dqdx"].values
    dhdy = CP * ds["ta_dtady"].values + LV * ds["q_dqdy"].values
    dsdx = CP * ds["ta_dtadx"].values
    dsdy = CP * ds["ta_dtady"].values

    h_prime, s_prime, _, _ = anomaly_mse(ds)

    ncircle = ds.sizes["circle"]

    h_div_col    = np.full(ncircle, np.nan)
    s_div_col    = np.full(ncircle, np.nan)
    flux_div_mse = np.full(ncircle, np.nan)
    flux_div_dse = np.full(ncircle, np.nan)
    gms_flux_a   = np.full(ncircle, np.nan)

    for i in range(ncircle):
        p_i = p[i]
        h_div_col[i] = _col_int_p(h_prime[i] * div[i], p_i)
        s_div_col[i] = _col_int_p(s_prime[i] * div[i], p_i)

        hadv_h = u[i] * dhdx[i] + v_w[i] * dhdy[i]
        hadv_s = u[i] * dsdx[i] + v_w[i] * dsdy[i]

        flux_div_mse[i] = _col_int_p(hadv_h, p_i) + h_div_col[i]
        flux_div_dse[i] = _col_int_p(hadv_s, p_i) + s_div_col[i]
        gms_flux_a[i]   = _safe_gms(flux_div_mse[i], flux_div_dse[i])

    return xr.Dataset(
        {
            "h_div_col_a":    ("circle", h_div_col),
            "s_div_col_a":    ("circle", s_div_col),
            "flux_div_mse_a": ("circle", flux_div_mse),
            "flux_div_dse_a": ("circle", flux_div_dse),
            "gms_flux_a":     ("circle", gms_flux_a),
        },
        coords={"circle": ds["circle"], "circle_time": ds["circle_time"]},
        attrs={"method": "flux_anomaly",
               "description": "Method 2 with anomaly MSE (h − campaign mean)."},
    )


def apply_mass_correction(ds):
    """
    Return a copy of ds with omega AND div corrected for mass conservation.

    BEACH derives omega and div independently from sonde data.  Their
    relationship ∂ω/∂p = −div is not exactly satisfied, so ω_top ≠ 0.

    This function applies the Idea B linear-in-pressure correction to omega:

        ω_corr(p) = ω(p) − ω_top · (p_sfc − p) / (p_sfc − p_top)

    and the consistent depth-uniform correction to div required by continuity
    (∂ω/∂p = −div  →  ∂(Δω)/∂p = ω_top/(p_sfc−p_top) = −Δdiv):

        div_corr = −∂(ω_corr)/∂p   (reconstructed from corrected omega)

    After correction:
        ω_corr tapers smoothly to 0 at the profile top      ✓
        div_corr exactly consistent with ω_corr             ✓

    Applying this to the dataset before running all three methods makes Methods
    1, 2, and 3 mutually consistent — the h_div_residual (boundary term) in
    Method 3 should collapse to near zero, providing a closure check.

    Returns:
        ds_corr   xr.Dataset  corrected copy of ds
        delta_div (ncircle,)  ndarray [s⁻¹]  uniform div adjustment per circle
    """
    omega_corr, delta_div = omega_mass_corrected(ds)

    # Subtract the depth-uniform Δdiv implied by the linear-ramp correction.
    # Adding Δω(p) = −ω_top·(p_sfc−p)/(p_sfc−p_top) to omega requires
    # subtracting Δdiv = ω_top/(p_sfc−p_top) from div (continuity: ∂ω/∂p = −div).
    div_corr = ds["div"].values.copy().astype(float)
    for i in range(ds.sizes["circle"]):
        if np.isfinite(delta_div[i]):
            div_corr[i] -= delta_div[i]

    ds_corr = ds.assign(
        {
            "omega": xr.DataArray(
                omega_corr,
                dims=ds["omega"].dims,
                coords=ds["omega"].coords,
                attrs=ds["omega"].attrs,
            ),
            "div": xr.DataArray(
                div_corr,
                dims=ds["div"].dims,
                coords=ds["div"].coords,
                attrs=ds["div"].attrs,
            ),
        }
    )
    return ds_corr, delta_div


def omega_step_zero(ds):
    """
    Hard-zero fix: set ω = 0 at the highest valid level of each circle.

    Unlike the linear-ramp correction (omega_mass_corrected), this applies no
    correction below the top — it simply zeros the boundary point directly.
    The valid mask is identical to _vadv_col (finite omega & p & h_prof) so
    the zero lands at the exact top of the integration domain.

    Returns:
        omega_step  (ncircle, nalt) ndarray  [Pa s⁻¹]
    """
    alt    = ds["altitude"].values
    T      = ds["ta_mean"].values
    q      = ds["q_mean"].values
    p      = ds["p_mean"].values
    omega  = ds["omega"].values
    ncircle = ds.sizes["circle"]

    h_prof     = _mse(T, alt[np.newaxis, :], q)
    omega_step = omega.copy().astype(float)

    for i in range(ncircle):
        valid = np.isfinite(omega[i]) & np.isfinite(p[i]) & np.isfinite(h_prof[i])
        if valid.sum() < 3:
            continue
        idx_top = np.where(valid)[0][-1]
        omega_step[i, idx_top] = 0.0

    return omega_step


def apply_step_zero_correction(ds):
    """
    Return a copy of ds with ω zeroed at the profile top (step, not ramp).

    This is the minimal boundary-closing assumption: assert ω = 0 at the
    last valid level without distributing any correction below it.  The div
    field is deliberately left unchanged — this function isolates the effect
    of the boundary condition on the vertical-advection integral alone.

    Returns:
        ds_corr  xr.Dataset  corrected copy of ds
    """
    omega_step = omega_step_zero(ds)
    ds_corr = ds.assign(
        {
            "omega": xr.DataArray(
                omega_step,
                dims=ds["omega"].dims,
                coords=ds["omega"].coords,
                attrs=ds["omega"].attrs,
            )
        }
    )
    return ds_corr


def apply_step_zero_consistent(ds):
    """
    Hard-zero fix with consistent div correction.

    Sets ω = 0 at the highest valid level AND corrects div at that same level
    so that ∂ω_corr/∂p = −div_corr holds at the top of the column.

    Derivation:
        Zeroing ω_top changes ∂ω/∂p at the top interval by:
            Δ(∂ω/∂p) = −ω_top / (p[idx_top−1] − p[idx_top])
        Continuity requires div_corr = −∂ω_corr/∂p, so:
            Δdiv[idx_top] = −ω_top / (p[idx_top−1] − p[idx_top])

        All levels below the top are left unchanged — the correction is
        concentrated entirely at the top grid point.

    This differs from the linear-ramp correction which distributes a
    depth-uniform Δdiv across the whole column.  The hard-zero concentrates
    the same total correction at one level.

    Returns:
        ds_corr  xr.Dataset  corrected copy of ds
    """
    alt     = ds["altitude"].values
    T       = ds["ta_mean"].values
    q       = ds["q_mean"].values
    p       = ds["p_mean"].values
    omega   = ds["omega"].values
    div     = ds["div"].values
    ncircle = ds.sizes["circle"]

    h_prof     = _mse(T, alt[np.newaxis, :], q)
    omega_corr = omega.copy().astype(float)
    div_corr   = div.copy().astype(float)

    for i in range(ncircle):
        valid = np.isfinite(omega[i]) & np.isfinite(p[i]) & np.isfinite(h_prof[i])
        if valid.sum() < 3:
            continue
        idx_valid = np.where(valid)[0]
        idx_top   = idx_valid[-1]
        idx_prev  = idx_valid[-2]   # level just below the top

        om_top = float(omega[i, idx_top])
        dp     = float(p[i, idx_prev]) - float(p[i, idx_top])  # > 0 (sfc pressure higher)

        if dp < 1.0:   # guard against degenerate spacing
            continue

        # Zero the top omega
        omega_corr[i, idx_top] = 0.0

        # Correct div at the top level only: Δdiv = −ω_top / Δp
        div_corr[i, idx_top] -= om_top / dp

    ds_corr = ds.assign(
        {
            "omega": xr.DataArray(
                omega_corr,
                dims=ds["omega"].dims,
                coords=ds["omega"].coords,
                attrs=ds["omega"].attrs,
            ),
            "div": xr.DataArray(
                div_corr,
                dims=ds["div"].dims,
                coords=ds["div"].coords,
                attrs=ds["div"].attrs,
            ),
        }
    )
    return ds_corr


def method1_mass_corrected(ds):
    """
    Idea B applied — Method 1 vertical advection with mass-corrected omega.

    Recomputes <ω ∂h/∂p> and GMS_adv after applying the linear mass
    correction that forces ω = 0 at both profile ends.  Horizontal
    advection is unchanged (it does not depend on omega).

    Returns xr.Dataset with per-circle variables:
        vert_adv_mc     <ω_corr ∂h/∂p>    [W m⁻²]
        vert_adv_dse_mc <ω_corr ∂s/∂p>    [W m⁻²]
        gms_adv_mc      corrected GMS_adv  [–]
        delta_div       uniform div shift per circle [s⁻¹]
    """
    alt   = ds["altitude"].values
    T     = ds["ta_mean"].values
    q     = ds["q_mean"].values
    ncircle = ds.sizes["circle"]

    h_prof = _mse(T, alt[np.newaxis, :], q)
    s_prof = _dse(T, alt[np.newaxis, :])

    omega_corr, delta_div = omega_mass_corrected(ds)

    vert_adv_mc     = np.full(ncircle, np.nan)
    vert_adv_dse_mc = np.full(ncircle, np.nan)
    gms_adv_mc      = np.full(ncircle, np.nan)

    for i in range(ncircle):
        vert_adv_mc[i]     = _vadv_col(omega_corr[i], h_prof[i], alt)
        vert_adv_dse_mc[i] = _vadv_col(omega_corr[i], s_prof[i], alt)
        gms_adv_mc[i]      = _safe_gms(vert_adv_mc[i], vert_adv_dse_mc[i])

    return xr.Dataset(
        {
            "vert_adv_mc":     ("circle", vert_adv_mc),
            "vert_adv_dse_mc": ("circle", vert_adv_dse_mc),
            "gms_adv_mc":      ("circle", gms_adv_mc),
            "delta_div":       ("circle", delta_div),
        },
        coords={"circle": ds["circle"], "circle_time": ds["circle_time"]},
        attrs={"method": "advective_mass_corrected",
               "description": "Method 1 vertical advection with omega "
                              "corrected to satisfy omega=0 at both ends."},
    )


# ===========================================================================
# Quick CLI
# ===========================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Compute MSE budget (3 methods) from BEACH L4 dropsondes"
    )
    parser.add_argument("--zarr", default=DEFAULT_ZARR)
    parser.add_argument("--output", default=None,
                        help="Save output to this NetCDF path.")
    args = parser.parse_args()

    print(f"Loading {args.zarr} ...")
    ds = load_dataset(args.zarr)

    print("Computing MSE budget (all 3 methods) ...")
    budget = compute_budget(ds)

    if args.output:
        budget.drop_vars(["h_profile", "s_profile"]).to_netcdf(args.output)
        print(f"Saved to {args.output}")
    else:
        cat_var = "category_plane" if "category_plane" in ds else "category_evolutionary"
        cat = ds[cat_var].values
        sep = "=" * 60

        for label in ["Top-Heavy", "Bottom-Heavy"]:
            mask = np.array([label in str(c) for c in cat])
            n = mask.sum()
            print(f"\n{sep}")
            print(f"  {label}  (n={n})")
            print(sep)

            va  = budget["vert_adv"].values[mask]
            vds = budget["vert_adv_dse"].values[mask]
            ha1 = budget["horiz_adv"].values[mask]
            g1  = budget["gms_adv"].values[mask]
            fd  = budget["flux_div_mse"].values[mask]
            fds = budget["flux_div_dse"].values[mask]
            g2  = budget["gms_flux"].values[mask]
            hr  = budget["horiz_adv_res"].values[mask]

            # Group-level GMS (ratio of means, more stable than mean of ratios)
            gms_adv_grp  = (np.nanmean(va)  / np.nanmean(vds)
                            if abs(np.nanmean(vds)) > 0 else np.nan)
            gms_flux_grp = (np.nanmean(fd)  / np.nanmean(fds)
                            if abs(np.nanmean(fds)) > 0 else np.nan)

            print(f"\n  Method 1 — Advective")
            print(f"    <ω ∂h/∂p>   = {np.nanmean(va):+8.2f} W m⁻²")
            print(f"    <v·∇h>      = {np.nanmean(ha1):+8.2f} W m⁻²")
            print(f"    GMS_adv     = {gms_adv_grp:.4f}  "
                  f"(median per-circle = {np.nanmedian(g1):.4f})")

            bnd = budget["h_div_residual"].values[mask]
            print(f"\n  Method 2 — Flux (product rule + BEACH div)")
            print(f"    <∇·(vh)>    = {np.nanmean(fd):+8.2f} W m⁻²")
            print(f"    GMS_flux    = {gms_flux_grp:.4f}  "
                  f"(median per-circle = {np.nanmedian(g2):.4f})")

            print(f"\n  Method 3 — Residual + boundary-term diagnostic")
            print(f"    <v·∇h>_res         = {np.nanmean(hr):+8.2f} W m⁻²"
                  f"  (= <∇·(vh)> − <ω∂h/∂p>)")
            print(f"    boundary term      = {np.nanmean(bnd):+8.2f} W m⁻²"
                  f"  (= <h·∇·v> − <ω∂h/∂p>)")
            print(f"    → if large, BEACH ω ≠ 0 at profile top; "
                  f"Method 1 <v·∇h> more reliable.")

        print()