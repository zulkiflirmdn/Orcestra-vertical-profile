"""
MSE Budget Calculation for ORCESTRA Dropsonde Circles
=====================================================

Two methods for computing the column moist static energy (MSE) budget:

  Method 1 — Advective Form (circle-mean fields)
      dh/dt + <v·∇h> + <ω ∂h/∂p> = F

  Method 2 — Flux Form / Line-Integral (individual sonde data)
      dh/dt + <∇·(vh)> = F
      where <∇·(vh)> is evaluated via the divergence theorem around the
      dropsonde ring.

References:
  - Inoue & Back (2015), doi:10.1175/JAS-D-15-0111.1
  - Bui et al. (2016), doi:10.1175/JAS-D-15-0349.1
  - Handlos & Back (2014), doi:10.1002/2013GL058846
  - Singh & Li (2025), evolutionary-angle top-heaviness classification
"""

import numpy as np
import xarray as xr
import warnings

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------
CP = 1004.0        # specific heat at constant pressure  [J kg⁻¹ K⁻¹]
G  = 9.81          # gravitational acceleration          [m s⁻²]
LV = 2.501e6       # latent heat of vaporisation         [J kg⁻¹]

# GMS denominator threshold: if |vert_adv_dse| < this, GMS is set to NaN
# to avoid blow-up from near-zero denominators.
GMS_DENOM_MIN = 10.0   # W m⁻²

# Default zarr path
DEFAULT_ZARR = "/g/data/k10/zr7147/ORCESTRA_dropsondes_categorized.zarr"


# ===================================================================
# Helpers
# ===================================================================

def load_dataset(zarr_path=DEFAULT_ZARR):
    """Load the BEACH Level-4 categorized dropsonde dataset."""
    ds = xr.open_zarr(zarr_path)
    return ds


def compute_mse_profile(T, z, q):
    """MSE  h = cp*T + g*z + Lv*q  (J kg⁻¹)."""
    return CP * T + G * z + LV * q


def compute_dse_profile(T, z):
    """DSE  s = cp*T + g*z  (J kg⁻¹)."""
    return CP * T + G * z


def _gradient_over_pressure(field, pressure):
    """
    Compute d(field)/dp along the altitude axis, handling NaNs.
    Returns array of same shape; NaN where input is NaN.
    """
    out = np.full_like(field, np.nan)
    valid = ~np.isnan(field) & ~np.isnan(pressure)
    if valid.sum() < 3:
        return out
    out[valid] = np.gradient(field[valid], pressure[valid])
    return out


def _column_integrate_dp_over_g(integrand, pressure):
    """
    Column integral  ∫ (integrand) dp/g   from p_top to p_sfc.

    Pressure must be in Pa.  Integration is done in ascending-pressure
    order (p_top → p_sfc, i.e. positive dp) so the sign convention is
    consistent with the standard budget.
    """
    valid = ~np.isnan(integrand) & ~np.isnan(pressure)
    if valid.sum() < 3:
        return np.nan
    p_v = pressure[valid]
    f_v = integrand[valid]
    idx = np.argsort(p_v)          # ascending pressure
    return np.trapezoid(f_v[idx], p_v[idx]) / G


# ===================================================================
# METHOD 1 — ADVECTIVE FORM  (circle-mean fields)
# ===================================================================

def advective_form(ds):
    """
    Compute MSE budget terms using the advective decomposition.

    Returns an xr.Dataset with variables (all per circle):
        h_profile        : MSE profile  h(z)                [J kg⁻¹]
        s_profile        : DSE profile  s(z)                [J kg⁻¹]
        col_h            : column-integrated MSE  <h>       [J m⁻²]
        horiz_adv        : <v·∇h>  column horizontal adv.   [W m⁻²]
        vert_adv         : <ω ∂h/∂p> column vertical adv.   [W m⁻²]
        vert_adv_dse     : <ω ∂s/∂p> column vertical adv.   [W m⁻²]
        gms              : normalised GMS  = vert_adv / vert_adv_dse  [–]
        total_adv        : horiz_adv + vert_adv              [W m⁻²]
    """
    T     = ds["ta_mean"].values          # (circle, altitude)
    z     = ds["altitude"].values         # (altitude,)
    q     = ds["q_mean"].values
    p     = ds["p_mean"].values           # Pa
    omega = ds["omega"].values            # Pa s⁻¹
    u     = ds["u_mean"].values
    v     = ds["v_mean"].values

    # Horizontal MSE gradients
    # ∂h/∂x = cp ∂T/∂x + Lv ∂q/∂x   (the g·∂z/∂x ≈ 0 on constant-z levels)
    dhdx = CP * ds["ta_dtadx"].values + LV * ds["q_dqdx"].values
    dhdy = CP * ds["ta_dtady"].values + LV * ds["q_dqdy"].values

    ncircle = ds.sizes["circle"]
    nalt    = ds.sizes["altitude"]

    h_prof = compute_mse_profile(T, z[np.newaxis, :], q)
    s_prof = compute_dse_profile(T, z[np.newaxis, :])

    col_h       = np.full(ncircle, np.nan)
    horiz_adv   = np.full(ncircle, np.nan)
    vert_adv    = np.full(ncircle, np.nan)
    vert_adv_dse = np.full(ncircle, np.nan)
    gms         = np.full(ncircle, np.nan)

    for i in range(ncircle):
        p_i  = p[i]
        om_i = omega[i]

        # ---- Column-integrated MSE ----
        col_h[i] = _column_integrate_dp_over_g(h_prof[i], p_i)

        # ---- Horizontal advection  v·∇h  ----
        hadv_i = u[i] * dhdx[i] + v[i] * dhdy[i]          # J kg⁻¹ s⁻¹ per level
        horiz_adv[i] = _column_integrate_dp_over_g(hadv_i, p_i)

        # ---- Vertical advection  ω ∂h/∂p  ----
        dhdp = _gradient_over_pressure(h_prof[i], p_i)
        vadv_i = om_i * dhdp                                # J kg⁻¹ s⁻¹ per level
        vert_adv[i] = _column_integrate_dp_over_g(vadv_i, p_i)

        # ---- Vertical advection of DSE (for GMS denominator) ----
        dsdp = _gradient_over_pressure(s_prof[i], p_i)
        vadv_dse_i = om_i * dsdp
        vert_adv_dse[i] = _column_integrate_dp_over_g(vadv_dse_i, p_i)

        # ---- GMS ----
        if abs(vert_adv_dse[i]) > GMS_DENOM_MIN:
            gms[i] = vert_adv[i] / vert_adv_dse[i]

    out = xr.Dataset(
        {
            "h_profile":    (("circle", "altitude"), h_prof),
            "s_profile":    (("circle", "altitude"), s_prof),
            "col_h":        ("circle", col_h),
            "horiz_adv":    ("circle", horiz_adv),
            "vert_adv":     ("circle", vert_adv),
            "vert_adv_dse": ("circle", vert_adv_dse),
            "gms":          ("circle", gms),
            "total_adv":    ("circle", horiz_adv + vert_adv),
        },
        coords={
            "circle":      ds["circle"],
            "altitude":    ds["altitude"],
            "circle_time": ds["circle_time"],
        },
        attrs={"method": "advective_form",
               "description": "MSE budget via advective decomposition "
                              "using BEACH circle-mean fields."},
    )
    return out


# ===================================================================
# METHOD 2 — FLUX FORM  (total column MSE export)
# ===================================================================

def flux_form(ds):
    """
    Compute the total column MSE flux divergence — the quantity one
    would get from the line integral  (1/A) ∮ vᵣ h dl  around the
    dropsonde ring, column-integrated.

    In principle:
        <∇·(vh)> = <v·∇h> + <h·(∇·v)>

    However, the column integral of h·(∇·v) requires ω → 0 at both
    boundaries, which the dropsonde profiles do not satisfy (they end
    well below the tropopause).  To avoid this boundary-term error
    we use the mathematically equivalent advective decomposition:

        <∇·(vh)> = <v·∇h> + <ω ∂h/∂p>       (exact for the column)

    This gives the TOTAL horizontal MSE export — unlike Method 1 which
    reports horizontal and vertical advection separately.

    The GMS here normalises the total export, not just the vertical
    part:
        GMS_flux = <∇·(vh)> / <∇·(vs)>

    This measures overall energy export efficiency including
    environmental horizontal advection, whereas Method 1's GMS isolates
    the vertical-advection component (omega-shape effect only).

    Returns an xr.Dataset with variables (all per circle):
        flux_div_mse   : <∇·(vh)>  total column MSE export  [W m⁻²]
        flux_div_dse   : <∇·(vs)>  total column DSE export  [W m⁻²]
        gms_flux       : GMS = flux_div_mse / flux_div_dse   [–]
    """
    T     = ds["ta_mean"].values
    z     = ds["altitude"].values
    q     = ds["q_mean"].values
    p     = ds["p_mean"].values           # Pa
    omega = ds["omega"].values
    u     = ds["u_mean"].values
    v     = ds["v_mean"].values

    dhdx = CP * ds["ta_dtadx"].values + LV * ds["q_dqdx"].values
    dhdy = CP * ds["ta_dtady"].values + LV * ds["q_dqdy"].values
    dsdx = CP * ds["ta_dtadx"].values
    dsdy = CP * ds["ta_dtady"].values

    ncircle = ds.sizes["circle"]

    h_prof = compute_mse_profile(T, z[np.newaxis, :], q)
    s_prof = compute_dse_profile(T, z[np.newaxis, :])

    flux_div_mse = np.full(ncircle, np.nan)
    flux_div_dse = np.full(ncircle, np.nan)
    gms_flux     = np.full(ncircle, np.nan)

    for i in range(ncircle):
        p_i  = p[i]
        om_i = omega[i]

        # Horizontal advection: v·∇h and v·∇s
        hadv_h = u[i] * dhdx[i] + v[i] * dhdy[i]
        hadv_s = u[i] * dsdx[i] + v[i] * dsdy[i]

        # Vertical advection: ω ∂h/∂p and ω ∂s/∂p
        dhdp = _gradient_over_pressure(h_prof[i], p_i)
        dsdp = _gradient_over_pressure(s_prof[i], p_i)
        vadv_h = om_i * dhdp
        vadv_s = om_i * dsdp

        # Total flux divergence = horiz + vert
        flux_div_mse[i] = (_column_integrate_dp_over_g(hadv_h, p_i)
                           + _column_integrate_dp_over_g(vadv_h, p_i))
        flux_div_dse[i] = (_column_integrate_dp_over_g(hadv_s, p_i)
                           + _column_integrate_dp_over_g(vadv_s, p_i))

        if abs(flux_div_dse[i]) > GMS_DENOM_MIN and not np.isnan(flux_div_dse[i]):
            gms_flux[i] = flux_div_mse[i] / flux_div_dse[i]

    out = xr.Dataset(
        {
            "flux_div_mse": ("circle", flux_div_mse),
            "flux_div_dse": ("circle", flux_div_dse),
            "gms_flux":     ("circle", gms_flux),
        },
        coords={
            "circle":      ds["circle"],
            "circle_time": ds["circle_time"],
        },
        attrs={"method": "flux_form",
               "description": "Total column MSE/DSE flux divergence "
                              "via advective decomposition, equivalent "
                              "to the Stokes line integral ∮ vr·h dl "
                              "column-integrated."},
    )
    return out


# ===================================================================
# COMBINED — run both and merge
# ===================================================================

def compute_budget(ds=None, zarr_path=DEFAULT_ZARR, methods="both"):
    """
    Compute the MSE budget.

    Parameters
    ----------
    ds : xr.Dataset, optional
        Pre-loaded dataset.  If None, loads from zarr_path.
    zarr_path : str
        Path to the zarr store (used only if ds is None).
    methods : str
        "advective", "flux", or "both".

    Returns
    -------
    xr.Dataset with all computed budget terms plus original metadata.
    """
    if ds is None:
        ds = load_dataset(zarr_path)

    results = {}

    if methods in ("advective", "both"):
        adv = advective_form(ds)
        results.update({v: adv[v] for v in adv.data_vars})

    if methods in ("flux", "both"):
        flx = flux_form(ds)
        results.update({v: flx[v] for v in flx.data_vars})

    # Copy useful metadata from the original dataset
    meta_vars = ["category_evolutionary", "category_avg",
                 "top_heaviness_angle", "omega"]
    for v in meta_vars:
        if v in ds:
            results[v] = ds[v]

    out = xr.Dataset(
        results,
        coords={
            "circle":      ds["circle"],
            "altitude":    ds["altitude"],
            "circle_time": ds["circle_time"],
            "circle_lat":  ds["circle_lat"],
            "circle_lon":  ds["circle_lon"],
        },
    )
    out.attrs["methods"] = methods
    return out


# ===================================================================
# Quick CLI
# ===================================================================

if __name__ == "__main__":
    import argparse, sys

    parser = argparse.ArgumentParser(description="Compute MSE budget from BEACH dropsondes")
    parser.add_argument("--zarr", default=DEFAULT_ZARR, help="Path to zarr store")
    parser.add_argument("--method", default="both", choices=["advective", "flux", "both"])
    parser.add_argument("--output", default=None,
                        help="Path to save output (NetCDF). Default: print summary.")
    args = parser.parse_args()

    print(f"Loading {args.zarr} ...")
    ds = load_dataset(args.zarr)
    print(f"Computing MSE budget (method={args.method}) ...")
    budget = compute_budget(ds, methods=args.method)

    if args.output:
        budget.to_netcdf(args.output)
        print(f"Saved to {args.output}")
    else:
        print("\n" + "=" * 60)
        print("MSE BUDGET SUMMARY")
        print("=" * 60)
        cat = ds["category_evolutionary"].values

        if "vert_adv" in budget:
            print("\n--- Advective Form ---")
            for label in ["Top-Heavy", "Bottom-Heavy"]:
                mask = np.array([label in str(c) for c in cat])
                va = budget["vert_adv"].values[mask]
                ha = budget["horiz_adv"].values[mask]
                g  = budget["gms"].values[mask]
                print(f"\n  {label} (n={mask.sum()}):")
                print(f"    <ω ∂h/∂p>  mean = {np.nanmean(va):+.1f} W m⁻²")
                print(f"    <v·∇h>     mean = {np.nanmean(ha):+.1f} W m⁻²")
                print(f"    GMS        mean = {np.nanmean(g):.3f}")

        if "flux_div_mse" in budget:
            print("\n--- Flux Form (Line Integral) ---")
            for label in ["Top-Heavy", "Bottom-Heavy"]:
                mask = np.array([label in str(c) for c in cat])
                fd = budget["flux_div_mse"].values[mask]
                gf = budget["gms_flux"].values[mask]
                print(f"\n  {label} (n={mask.sum()}):")
                print(f"    <∇·(vh)>   mean = {np.nanmean(fd):+.1f} W m⁻²")
                print(f"    GMS (flux)  mean = {np.nanmean(gf):.3f}")

        print()
