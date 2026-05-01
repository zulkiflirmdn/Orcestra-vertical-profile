"""
ERA5 Extension for BEACH L4 Omega Profiles
===========================================

Stitches ERA5 pressure-velocity (omega) above the top of BEACH L4 dropsonde
profiles, closing the open upper boundary and eliminating the boundary term.

ERA5 variable conventions
--------------------------
Variable name  : `w`  — **already ω in Pa s⁻¹** (positive = downward/subsidence).
                 CDS ERA5 "vertical_velocity" on pressure levels is ω, not w_geo.
Pressure coord : `pressure_level`  stored in hPa in the file → multiply ×100 for Pa.
Time coord     : `valid_time`  (renamed to `time` internally for convenience).

Expected ERA5 file
------------------
Download via CDS API (notebooks/download_era5.ipynb):
    dataset  : reanalysis-era5-pressure-levels
    variables: vertical_velocity, temperature
    levels   : 20–1000 hPa
    period   : 2024-08-10 to 2024-09-30
    domain   : 0–30 N, 70 W–0 W
    format   : netcdf
    → saved to /g/data/k10/zr7147/ERA5/era5_omega_pressure_levels.nc

References
----------
Inoue & Back (2015)  doi:10.1175/JAS-D-15-0111.1
"""

import numpy as np
import xarray as xr

CP = 1004.0    # J kg⁻¹ K⁻¹
G  = 9.81      # m s⁻²
LV = 2.501e6   # J kg⁻¹
RD = 287.05    # J kg⁻¹ K⁻¹


def _default_era5_omega_path():
    from scripts.config import default_era5_omega_path
    return default_era5_omega_path()


def _get_era5_ds(era5_ds, era5_path):
    """Return era5_ds if already loaded, otherwise load from era5_path."""
    if era5_ds is not None:
        return era5_ds
    return load_era5_omega(era5_path)


# ===========================================================================
# ERA5 loading
# ===========================================================================

def load_era5_omega(era5_path=None):
    """
    Load ERA5 omega and temperature, standardising coordinate names.

    Returns xr.Dataset with dims (time, pressure_level, latitude, longitude):
        w                    Pa s⁻¹  omega (already in Pa/s from CDS)
        t                    K       temperature
        pressure_level_pa    Pa      pressure in Pa (added coord)

    Raises FileNotFoundError if the ERA5 file does not exist.
    """
    import pathlib

    if era5_path is None:
        era5_path = _default_era5_omega_path()

    era5_path = pathlib.Path(era5_path)
    if not era5_path.exists():
        raise FileNotFoundError(
            f"ERA5 omega file not found: {era5_path}\n"
            "Run notebooks/download_era5.ipynb (Download A) to create it."
        )

    ds = xr.open_dataset(era5_path)

    # Normalise time coordinate name → 'time'
    if 'valid_time' in ds.coords and 'time' not in ds.coords:
        ds = ds.rename({'valid_time': 'time'})

    # Add pressure coordinate in Pa (ERA5 stores hPa)
    p_pa = ds['pressure_level'].values * 100.0
    ds   = ds.assign_coords(pressure_level_pa=('pressure_level', p_pa))
    ds['pressure_level_pa'].attrs.update(
        {'units': 'Pa', 'long_name': 'pressure level in Pa'}
    )
    return ds


# ===========================================================================
# Per-circle matching
# ===========================================================================

def match_era5_to_circle(era5_ds, circle_lat, circle_lon, circle_time,
                          spatial_half_deg=2.0):
    """
    Extract ERA5 omega and temperature matched to one dropsonde circle.

    Nearest-time lookup; spatial mean within ±spatial_half_deg of the centre.

    Returns
    -------
    omega_pa : (n_levels,)  Pa s⁻¹  sorted descending pressure (sfc first)
    p_pa     : (n_levels,)  Pa
    t_k      : (n_levels,)  K
    """
    times = era5_ds['time'].values
    t_idx = int(np.argmin(np.abs(times - np.datetime64(circle_time, 'ns'))))
    ds_t  = era5_ds.isel(time=t_idx)

    lat = ds_t['latitude'].values
    lon = ds_t['longitude'].values
    lat_mask = (lat >= circle_lat - spatial_half_deg) & (lat <= circle_lat + spatial_half_deg)
    lon_mask = (lon >= circle_lon - spatial_half_deg) & (lon <= circle_lon + spatial_half_deg)

    ds_box    = ds_t.isel(latitude=lat_mask, longitude=lon_mask)
    omega_arr = ds_box['w'].mean(dim=['latitude', 'longitude']).values
    t_arr     = ds_box['t'].mean(dim=['latitude', 'longitude']).values
    p_arr     = ds_box['pressure_level_pa'].values

    idx = np.argsort(p_arr)[::-1]   # descending pressure (surface first)
    omega_s = omega_arr[idx]
    p_s     = p_arr[idx]
    t_s     = t_arr[idx]

    # ERA5 divergence from continuity: div = -∂ω/∂p
    # np.gradient uses central differences internally and handles endpoints.
    div_s = -np.gradient(omega_s, p_s)

    return omega_s, p_s, t_s, div_s


# ===========================================================================
# ERA5-anchored O'Brien correction  (proper M4 preparation)
# ===========================================================================

def apply_era5_anchored_correction(ds_beach, era5_path=None, era5_ds=None):
    """
    O'Brien ramp correction that targets ERA5 ω at the BEACH profile top
    instead of zero.

    The standard linear ramp forces ω → 0 at the BEACH data top (~100 hPa),
    imposing a false boundary condition at a level that still has real vertical
    motion.  This function instead forces BEACH ω to smoothly connect to ERA5 ω
    at the same pressure level, so the combined BEACH + ERA5 profile is
    continuous across the junction.

    For each circle:
        1. Find the BEACH profile top: (idx_top, p_top, ω_beach_top).
        2. Get ERA5 ω at the ERA5 pressure level nearest to p_top → ω_era5_junction.
        3. Compute junction mismatch: Δω = ω_beach_top − ω_era5_junction.
        4. Apply linear ramp:
               ω_corr(p) = ω(p) − Δω · (p_sfc − p) / (p_sfc − p_top)
           This zeroes the mismatch at p_top while preserving ω at the surface.
        5. Consistent depth-uniform div correction:
               Δdiv = Δω / (p_sfc − p_top)

    Physical meaning:
        After correction ω_beach_top ≈ ω_era5_junction, so stitching ERA5 above
        gives a continuous profile with no jump at the junction.  ERA5 naturally
        → 0 near 20 hPa, closing the column at the true atmospheric top.

    Parameters
    ----------
    ds_beach  : xr.Dataset  BEACH L4 (from load_dataset())
    era5_path : str or Path  path to ERA5 omega NetCDF

    Returns
    -------
    ds_corr    : xr.Dataset  corrected copy of ds_beach
    delta_div  : (ncircle,) ndarray  [s⁻¹]  uniform div adjustment per circle
    """
    from scripts.mse_budget import _mse

    era5_ds = _get_era5_ds(era5_ds, era5_path)

    alt     = ds_beach['altitude'].values
    omega   = ds_beach['omega'].values.astype(float)
    p       = ds_beach['p_mean'].values.astype(float)
    T       = ds_beach['ta_mean'].values
    q       = ds_beach['q_mean'].values
    div     = ds_beach['div'].values.astype(float)
    ncircle = ds_beach.sizes['circle']

    h_prof     = _mse(T, alt[np.newaxis, :], q)
    omega_corr = omega.copy()
    div_corr   = div.copy()
    delta_div  = np.full(ncircle, np.nan)

    for i in range(ncircle):
        valid = np.isfinite(omega[i]) & np.isfinite(p[i]) & np.isfinite(h_prof[i])
        if valid.sum() < 3:
            continue

        idx_valid = np.where(valid)[0]
        idx_top   = idx_valid[-1]
        idx_bot   = idx_valid[0]

        p_top  = float(p[i, idx_top])
        p_sfc  = float(p[i, idx_bot])
        om_top = float(omega[i, idx_top])

        if p_sfc - p_top < 1e3:
            continue

        # Get ERA5 ω at the ERA5 level nearest to the BEACH profile top
        try:
            om_e, p_e, _, _ = match_era5_to_circle(
                era5_ds,
                float(ds_beach['circle_lat'].values[i]),
                float(ds_beach['circle_lon'].values[i]),
                ds_beach['circle_time'].values[i],
            )
        except Exception:
            continue

        # Nearest ERA5 level to p_top
        nearest_idx     = int(np.argmin(np.abs(p_e - p_top)))
        om_era5_junction = float(om_e[nearest_idx])

        # Junction mismatch — this is what the ramp needs to remove
        delta_om = om_top - om_era5_junction

        if abs(delta_om) < 1e-8:
            continue   # profiles already match at junction

        # Linear ramp over the BEACH valid column
        ramp = delta_om * (p_sfc - p[i, idx_valid]) / (p_sfc - p_top)
        omega_corr[i, idx_valid] -= ramp

        # Depth-uniform div correction (continuity: Δdiv = Δω / Δp)
        dd = delta_om / (p_sfc - p_top)
        div_corr[i, idx_valid] -= dd
        delta_div[i] = dd

    ds_corr = ds_beach.assign({
        'omega': xr.DataArray(omega_corr, dims=ds_beach['omega'].dims,
                              coords=ds_beach['omega'].coords,
                              attrs=ds_beach['omega'].attrs),
        'div':   xr.DataArray(div_corr,   dims=ds_beach['div'].dims,
                              coords=ds_beach['div'].coords,
                              attrs=ds_beach['div'].attrs),
    })
    return ds_corr, delta_div


# ===========================================================================
# Stitching
# ===========================================================================

def stitch_beach_era5(ds_beach, era5_path=None, p_stitch_pa=15000.0, era5_ds=None):
    """
    Extend BEACH L4 omega profiles upward using ERA5 above p_stitch_pa.

    For each circle the function:
    1. Keeps the full BEACH column (altitude grid, 0–14590 m at 10 m spacing).
    2. Appends ERA5 levels with p < p_stitch_pa, matched by time/location.
    3. Computes altitude for each ERA5 level via the hypsometric equation
       anchored at the top of the BEACH valid data.
    4. Sorts the combined column by descending pressure.

    The result is stored as (circle, ext_level) arrays where the first nalt
    entries correspond to the original BEACH altitude grid and the remaining
    entries are the ERA5 pressure levels.

    Parameters
    ----------
    ds_beach    : xr.Dataset  BEACH L4 (from load_dataset())
    era5_path   : str or Path  path to ERA5 NetCDF (default_era5_omega_path())
    p_stitch_pa : float  [Pa]  ERA5 levels with p < this are appended.
                  Default 150 hPa = 15000 Pa.

    Returns
    -------
    ds_ext : xr.Dataset  copy of ds_beach with extra variables:
        omega_ext      (circle, ext_level)  Pa s⁻¹  stitched omega
        p_ext          (circle, ext_level)  Pa       stitched pressure
        alt_ext        (circle, ext_level)  m        stitched altitude
        era5_n_levels  (circle,)            int      ERA5 levels added

    Raises FileNotFoundError if ERA5 file is missing.
    """
    from scripts.mse_budget import _mse

    era5_ds = _get_era5_ds(era5_ds, era5_path)

    alt     = ds_beach['altitude'].values          # (nalt,) metres, uniform 10 m
    omega_b = ds_beach['omega'].values.astype(float)
    p_b     = ds_beach['p_mean'].values.astype(float)
    T_b     = ds_beach['ta_mean'].values
    q_b     = ds_beach['q_mean'].values
    ncircle = ds_beach.sizes['circle']
    nalt    = ds_beach.sizes['altitude']
    h_prof  = _mse(T_b, alt[np.newaxis, :], q_b)

    # Max ERA5 levels that could be added (all levels above p_stitch_pa + buffer)
    era5_p_all  = era5_ds['pressure_level_pa'].values
    n_era5_max  = len(era5_p_all)   # safe upper bound: ERA5 can fill from p_top upward
    n_ext       = nalt + n_era5_max

    omega_ext    = np.full((ncircle, n_ext), np.nan)
    p_ext        = np.full((ncircle, n_ext), np.nan)
    alt_ext      = np.full((ncircle, n_ext), np.nan)
    ta_era5_ext  = np.full((ncircle, n_ext), np.nan)
    div_era5_ext = np.full((ncircle, n_ext), np.nan)
    era5_n       = np.zeros(ncircle, dtype=int)

    # BEACH portion (first nalt columns)
    omega_ext[:,    :nalt] = omega_b
    p_ext[:,        :nalt] = p_b
    alt_ext[:,      :nalt] = alt[np.newaxis, :]
    ta_era5_ext[:,  :nalt] = T_b
    div_era5_ext[:, :nalt] = ds_beach['div'].values.astype(float)

    for i in range(ncircle):
        # Match ERA5 to this circle
        try:
            om_e, p_e, t_e, div_e = match_era5_to_circle(
                era5_ds,
                float(ds_beach['circle_lat'].values[i]),
                float(ds_beach['circle_lon'].values[i]),
                ds_beach['circle_time'].values[i],
            )
        except Exception:
            continue

        # Find top of BEACH valid data for this circle first
        valid_b = (np.isfinite(omega_b[i]) & np.isfinite(p_b[i])
                   & np.isfinite(h_prof[i]))
        if valid_b.sum() < 3:
            continue
        idx_top = np.where(valid_b)[0][-1]
        z_top   = float(alt[idx_top])
        p_top   = float(p_b[i, idx_top])
        T_top   = float(T_b[i, idx_top])

        # Add ERA5 levels strictly above the BEACH top (no gap at junction)
        above = p_e < p_top
        if above.sum() == 0:
            continue

        om_add  = om_e[above]
        p_add   = p_e[above]
        t_add   = t_e[above]
        div_add = div_e[above]
        n_add   = len(om_add)

        # Altitude of each ERA5 level via hypsometric equation
        z_add = np.array([
            z_top + (RD * 0.5 * (T_top + float(t_add[k]))
                     * np.log(p_top / float(p_add[k]))) / G
            for k in range(n_add)
        ])

        omega_ext[i,    nalt:nalt + n_add] = om_add
        p_ext[i,        nalt:nalt + n_add] = p_add
        alt_ext[i,      nalt:nalt + n_add] = z_add
        ta_era5_ext[i,  nalt:nalt + n_add] = t_add
        div_era5_ext[i, nalt:nalt + n_add] = div_add
        era5_n[i]                           = n_add

    # Sort all five arrays together by descending pressure per circle
    for i in range(ncircle):
        finite = np.isfinite(p_ext[i])
        if finite.sum() < 2:
            continue
        idx_f = np.where(finite)[0]
        order = idx_f[np.argsort(p_ext[i, idx_f])[::-1]]
        n_f   = len(order)
        for arr in (omega_ext, p_ext, alt_ext, ta_era5_ext, div_era5_ext):
            buf = np.full(n_ext, np.nan)
            buf[:n_f] = arr[i, order]
            arr[i]    = buf

    ds_ext = ds_beach.assign({
        'omega_ext': xr.DataArray(omega_ext, dims=('circle', 'ext_level'),
                                  attrs={'units': 'Pa s-1',
                                         'long_name': 'omega stitched BEACH + ERA5'}),
        'p_ext':     xr.DataArray(p_ext, dims=('circle', 'ext_level'),
                                  attrs={'units': 'Pa',
                                         'long_name': 'pressure for stitched column'}),
        'alt_ext':   xr.DataArray(alt_ext, dims=('circle', 'ext_level'),
                                  attrs={'units': 'm',
                                         'long_name': 'altitude for stitched column'}),
        'ta_era5_ext':   xr.DataArray(ta_era5_ext, dims=('circle', 'ext_level'),
                                      attrs={'units': 'K',
                                             'long_name': 'temperature: BEACH below, ERA5 above'}),
        'div_era5_ext':  xr.DataArray(div_era5_ext, dims=('circle', 'ext_level'),
                                      attrs={'units': 's-1',
                                             'long_name': 'divergence: BEACH below, ERA5 (-dω/dp) above'}),
        'era5_n_levels': xr.DataArray(era5_n, dims='circle',
                                      attrs={'long_name': 'ERA5 levels added above BEACH top'}),
    })
    ds_ext.attrs.update({'era5_stitched': 'True', 'p_stitch_pa': str(p_stitch_pa)})
    return ds_ext


# ===========================================================================
# Budget helper for ERA5-extended column
# ===========================================================================

def compute_budget_ext(ds_ext, mass_correct=False, recompute_div=False):
    """
    Compute the MSE budget using the ERA5-extended omega and pressure columns.

    Builds a fresh minimal xr.Dataset whose 'altitude' dimension spans the
    stitched column (BEACH altitudes + ERA5 levels), then calls compute_budget().

    The altitude coordinate uses the circle-mean alt_ext profile so that
    _vadv_col computes ∂h/∂z correctly.  Variation in ERA5 level altitudes
    across circles at these stratospheric pressures is small (~1 km) and
    does not materially affect the result.

    Parameters
    ----------
    ds_ext        : xr.Dataset  returned by stitch_beach_era5() or blend_beach_era5()
    mass_correct  : bool  passed through to compute_budget()
    recompute_div : bool  if True, derive div = −∂ω/∂p from the stitched omega
                    profile per circle instead of using div_era5_ext.  This
                    ensures exact consistency between omega and div throughout
                    the extended column, eliminating spurious residuals caused
                    by (a) the div jump at the BEACH–ERA5 junction or (b) the
                    cosine-blend inconsistency in M4.  GMS (vert_adv) is
                    unaffected since it uses omega directly.  Default False for
                    backward compatibility; pass True for M3 and M4.
    """
    from scripts.mse_budget import compute_budget

    nalt_orig = ds_ext.sizes['altitude']
    n_ext     = ds_ext.sizes['ext_level']
    n_pad     = n_ext - nalt_orig
    ncircle   = ds_ext.sizes['circle']

    def _pad_nan(arr2d):
        """Pad with NaN (for variables with no ERA5 equivalent)."""
        return np.concatenate(
            [arr2d, np.full((arr2d.shape[0], n_pad), np.nan)], axis=1
        )

    def _pad_zero(arr2d):
        """Pad with zero (e.g. specific humidity above tropopause ≈ 0)."""
        return np.concatenate(
            [arr2d, np.zeros((arr2d.shape[0], n_pad))], axis=1
        )

    # Mean altitude profile — correct metres for np.gradient in _vadv_col
    alt_mean = np.nanmean(ds_ext['alt_ext'].values, axis=0)

    # ta_mean for the extended column: BEACH T below, ERA5 T above
    ta_ext = ds_ext['ta_era5_ext'].values   # (circle, ext_level)

    # q_mean: BEACH q below, 0 above tropopause (ERA5 levels are dry)
    q_ext  = _pad_zero(ds_ext['q_mean'].values)

    # Divergence field
    if recompute_div:
        # Derive div = −∂ω/∂p from the extended omega profile per circle.
        # This ensures exact consistency between omega and div throughout the
        # column — eliminating the junction-discontinuity residual in M3 and
        # the cosine-blend inconsistency in M4.
        omega_ext = ds_ext['omega_ext'].values
        p_ext     = ds_ext['p_ext'].values
        div_ext   = np.full_like(omega_ext, np.nan)
        for i in range(ncircle):
            valid = np.isfinite(omega_ext[i]) & np.isfinite(p_ext[i])
            if valid.sum() < 3:
                continue
            idx = np.where(valid)[0]
            # p_ext is sorted descending (surface first); np.gradient handles
            # non-uniform spacing and returns the correct sign automatically.
            div_ext[i, idx] = -np.gradient(omega_ext[i, idx], p_ext[i, idx])
        div_to_use = div_ext
    else:
        div_to_use = ds_ext['div_era5_ext'].values

    coords = {
        'circle':      ds_ext['circle'],
        'altitude':    alt_mean,
        'circle_time': ds_ext['circle_time'],
    }

    def _da(arr, attrs=None):
        return xr.DataArray(arr, dims=('circle', 'altitude'), attrs=attrs or {})

    ds_new = xr.Dataset(
        {
            'omega':    _da(ds_ext['omega_ext'].values),
            'p_mean':   _da(ds_ext['p_ext'].values),
            'ta_mean':  _da(ta_ext, ds_ext['ta_mean'].attrs),
            'q_mean':   _da(q_ext,  ds_ext['q_mean'].attrs),
            'div':      _da(div_to_use),
            'ta_dtadx': _da(_pad_nan(ds_ext['ta_dtadx'].values)),
            'ta_dtady': _da(_pad_nan(ds_ext['ta_dtady'].values)),
            'q_dqdx':   _da(_pad_nan(ds_ext['q_dqdx'].values)),
            'q_dqdy':   _da(_pad_nan(ds_ext['q_dqdy'].values)),
            'u_mean':   _da(_pad_nan(ds_ext['u_mean'].values)),
            'v_mean':   _da(_pad_nan(ds_ext['v_mean'].values)),
        },
        coords=coords,
    )
    return compute_budget(ds_new, mass_correct=mass_correct)


# ===========================================================================
# Method 4 — cosine blend near BEACH top
# ===========================================================================

def blend_beach_era5(ds_beach, era5_path=None, era5_ds=None,
                     blend_width_pa=5000.0, p_stitch_pa=15000.0):
    """
    Method 4 omega preparation: smooth cosine blend from BEACH to ERA5.

    Unlike the O'Brien ramp (which applies a linear correction across the
    entire BEACH column), this only modifies the top `blend_width_pa` Pa of
    each profile.  BEACH omega is completely unchanged below that zone.

    For each circle:
        1.  Find BEACH top pressure p_top and surface pressure p_sfc.
        2.  Define blend zone: p in [p_top, min(p_top + blend_width_pa, p_sfc)].
        3.  Interpolate ERA5 omega and div to each BEACH pressure in blend zone.
        4.  Apply cosine taper:
                frac = (p_blend_bot − p) / blend_width_pa   [0 at blend_bot, 1 at p_top]
                w(p) = 0.5 * (1 + cos(π · frac))
                → w = 1 at p_blend_bot (pure BEACH), w = 0 at p_top (pure ERA5)
                omega_blend = w * omega_beach + (1−w) * omega_era5_interp
        5.  Stitch pure ERA5 levels above p_top (no gap at junction).
        6.  Apply same cosine taper to divergence in the blend zone.

    The physical motivation: the O'Brien ramp distorts the whole BEACH column
    to fix the boundary.  Here only the topmost ~50 hPa are modified, keeping
    the observationally-constrained mid-troposphere intact.

    Parameters
    ----------
    ds_beach        : xr.Dataset  BEACH L4
    era5_path       : str or None  path to ERA5 NetCDF (used if era5_ds is None)
    era5_ds         : xr.Dataset or None  pre-loaded ERA5 (avoids re-loading)
    blend_width_pa  : float  [Pa]  width of the cosine transition zone.
                      Default 5000 Pa (50 hPa).
    p_stitch_pa     : float  [Pa]  skip circle if BEACH top > this pressure.
                      Default 15000 Pa (150 hPa).

    Returns ds_ext in the same format as stitch_beach_era5() so that
    compute_budget_ext() can be called directly on the result.
    """
    from scripts.mse_budget import _mse

    era5_ds = _get_era5_ds(era5_ds, era5_path)

    alt     = ds_beach['altitude'].values
    omega_b = ds_beach['omega'].values.astype(float)
    p_b     = ds_beach['p_mean'].values.astype(float)
    T_b     = ds_beach['ta_mean'].values
    q_b     = ds_beach['q_mean'].values
    div_b   = ds_beach['div'].values.astype(float)
    ncircle = ds_beach.sizes['circle']
    nalt    = ds_beach.sizes['altitude']
    h_prof  = _mse(T_b, alt[np.newaxis, :], q_b)

    era5_p_all = era5_ds['pressure_level_pa'].values
    n_era5_max = len(era5_p_all)
    n_ext      = nalt + n_era5_max

    omega_ext    = np.full((ncircle, n_ext), np.nan)
    p_ext        = np.full((ncircle, n_ext), np.nan)
    alt_ext      = np.full((ncircle, n_ext), np.nan)
    ta_era5_ext  = np.full((ncircle, n_ext), np.nan)
    div_era5_ext = np.full((ncircle, n_ext), np.nan)
    era5_n       = np.zeros(ncircle, dtype=int)

    # Fill BEACH portion (blend will modify top levels in-place)
    omega_ext[:,    :nalt] = omega_b
    p_ext[:,        :nalt] = p_b
    alt_ext[:,      :nalt] = alt[np.newaxis, :]
    ta_era5_ext[:,  :nalt] = T_b
    div_era5_ext[:, :nalt] = div_b

    for i in range(ncircle):
        try:
            om_e, p_e, t_e, div_e = match_era5_to_circle(
                era5_ds,
                float(ds_beach['circle_lat'].values[i]),
                float(ds_beach['circle_lon'].values[i]),
                ds_beach['circle_time'].values[i],
            )
        except Exception:
            continue

        valid_b = (np.isfinite(omega_b[i]) & np.isfinite(p_b[i])
                   & np.isfinite(h_prof[i]))
        if valid_b.sum() < 3:
            continue

        idx_valid   = np.where(valid_b)[0]
        idx_top     = idx_valid[-1]
        idx_bot     = idx_valid[0]
        p_top       = float(p_b[i, idx_top])
        p_sfc       = float(p_b[i, idx_bot])
        p_blend_bot = min(p_top + blend_width_pa, p_sfc)

        # ERA5 sorted ascending pressure (low p first) for np.interp
        sort_asc  = np.argsort(p_e)
        p_e_asc   = p_e[sort_asc]
        om_e_asc  = om_e[sort_asc]
        div_e_asc = div_e[sort_asc]

        # Apply cosine blend to BEACH levels inside the blend zone
        for j in idx_valid:
            p_j = float(p_b[i, j])
            if p_j > p_blend_bot:
                continue  # below blend zone — keep raw BEACH

            # ERA5 interpolated to this BEACH pressure level
            om_era5_j  = float(np.interp(p_j, p_e_asc, om_e_asc))
            div_era5_j = float(np.interp(p_j, p_e_asc, div_e_asc))

            # frac=0 at p_blend_bot (pure BEACH), frac=1 at p_top (pure ERA5)
            denom = max(p_blend_bot - p_top, 1.0)
            frac  = (p_blend_bot - p_j) / denom
            w     = 0.5 * (1.0 + np.cos(np.pi * frac))

            omega_ext[i, j]    = w * omega_b[i, j] + (1.0 - w) * om_era5_j
            div_era5_ext[i, j] = w * div_b[i, j]   + (1.0 - w) * div_era5_j

        # Stitch pure ERA5 above the BEACH top (no gap)
        above = p_e < p_top
        if above.sum() == 0:
            continue

        om_add  = om_e[above]
        p_add   = p_e[above]
        t_add   = t_e[above]
        div_add = div_e[above]
        n_add   = len(om_add)
        T_top   = float(T_b[i, idx_top])
        z_top   = float(alt[idx_top])

        z_add = np.array([
            z_top + (RD * 0.5 * (T_top + float(t_add[k]))
                     * np.log(p_top / float(p_add[k]))) / G
            for k in range(n_add)
        ])

        n_fill = min(n_add, n_era5_max)
        omega_ext[i,    nalt:nalt + n_fill] = om_add[:n_fill]
        p_ext[i,        nalt:nalt + n_fill] = p_add[:n_fill]
        alt_ext[i,      nalt:nalt + n_fill] = z_add[:n_fill]
        ta_era5_ext[i,  nalt:nalt + n_fill] = t_add[:n_fill]
        div_era5_ext[i, nalt:nalt + n_fill] = div_add[:n_fill]
        era5_n[i]                            = n_fill

    # Sort by descending pressure per circle
    for i in range(ncircle):
        finite = np.isfinite(p_ext[i])
        if finite.sum() < 2:
            continue
        idx_f = np.where(finite)[0]
        order = idx_f[np.argsort(p_ext[i, idx_f])[::-1]]
        n_f   = len(order)
        for arr in (omega_ext, p_ext, alt_ext, ta_era5_ext, div_era5_ext):
            buf = np.full(n_ext, np.nan)
            buf[:n_f] = arr[i, order]
            arr[i]    = buf

    ds_ext = ds_beach.assign({
        'omega_ext': xr.DataArray(
            omega_ext, dims=('circle', 'ext_level'),
            attrs={'units': 'Pa s-1',
                   'long_name': 'omega: cosine-blended BEACH→ERA5 (M4)'}),
        'p_ext': xr.DataArray(
            p_ext, dims=('circle', 'ext_level'),
            attrs={'units': 'Pa'}),
        'alt_ext': xr.DataArray(
            alt_ext, dims=('circle', 'ext_level'),
            attrs={'units': 'm'}),
        'ta_era5_ext': xr.DataArray(
            ta_era5_ext, dims=('circle', 'ext_level'),
            attrs={'units': 'K',
                   'long_name': 'temperature: BEACH below, ERA5 above'}),
        'div_era5_ext': xr.DataArray(
            div_era5_ext, dims=('circle', 'ext_level'),
            attrs={'units': 's-1',
                   'long_name': 'div: cosine-blended near top, ERA5 above'}),
        'era5_n_levels': xr.DataArray(
            era5_n, dims='circle',
            attrs={'long_name': 'ERA5 levels added above BEACH top'}),
    })
    ds_ext.attrs.update({
        'blend_width_pa': str(blend_width_pa),
        'p_stitch_pa':    str(p_stitch_pa),
        'method':         'M4_cosine_blend',
    })
    return ds_ext


# ===========================================================================
# Pipeline wrappers — Methods 3 and 4
# ===========================================================================

def compute_budget_m3(ds_beach, era5_path=None, era5_ds=None, p_stitch_pa=15000.0):
    """
    Full Method 3 pipeline: ERA5-anchored O'Brien ramp → stitch → budget.

    Steps:
        1.  apply_era5_anchored_correction — linear ramp corrects BEACH omega
            so that omega_beach_top ≈ omega_era5 at the junction pressure.
            Updates div consistently throughout the BEACH column.
        2.  stitch_beach_era5 — appends ERA5 levels above BEACH top.
            With the ramp applied first, the junction is continuous.
        3.  compute_budget_ext — MSE budget on the extended column.

    The O'Brien ramp distorts the entire BEACH column (every level gets a
    small correction), but ensures a smooth BEACH→ERA5 transition.

    Parameters
    ----------
    ds_beach     : xr.Dataset  BEACH L4
    era5_path    : str or None  path to ERA5 NetCDF (used if era5_ds is None)
    era5_ds      : xr.Dataset or None  pre-loaded ERA5 (avoids triple load)
    p_stitch_pa  : float [Pa]  skip circle if BEACH top > this. Default 150 hPa.

    Returns
    -------
    budget     : xr.Dataset  MSE budget (same variables as compute_budget)
    delta_div  : (ncircle,) ndarray [s⁻¹]  div correction applied per circle
    ds_ext     : xr.Dataset  stitched extended dataset (for diagnostics)
    """
    era5 = _get_era5_ds(era5_ds, era5_path)
    ds_corr, delta_div = apply_era5_anchored_correction(ds_beach, era5_ds=era5)
    ds_ext = stitch_beach_era5(ds_corr, era5_ds=era5, p_stitch_pa=p_stitch_pa)
    budget = compute_budget_ext(ds_ext, recompute_div=True)
    return budget, delta_div, ds_ext


def compute_budget_m4(ds_beach, era5_path=None, era5_ds=None,
                      blend_width_pa=5000.0, p_stitch_pa=15000.0):
    """
    Full Method 4 pipeline: cosine blend near BEACH top → stitch → budget.

    Steps:
        1.  blend_beach_era5 — cosine taper from BEACH→ERA5 in the top
            blend_width_pa Pa of the profile.  BEACH unchanged below.
        2.  compute_budget_ext — MSE budget on the blended + stitched column.

    Unlike Method 3, no global correction is applied; only the topmost
    ~50 hPa (default blend_width_pa=5000 Pa) are modified.

    Parameters
    ----------
    ds_beach        : xr.Dataset  BEACH L4
    era5_path       : str or None  path to ERA5 NetCDF (used if era5_ds is None)
    era5_ds         : xr.Dataset or None  pre-loaded ERA5
    blend_width_pa  : float [Pa]  blend zone width. Default 5000 Pa (50 hPa).
    p_stitch_pa     : float [Pa]  skip circle if BEACH top > this. Default 150 hPa.

    Returns
    -------
    budget  : xr.Dataset  MSE budget (same variables as compute_budget)
    ds_ext  : xr.Dataset  blended extended dataset (for diagnostics / omega plots)
    """
    era5 = _get_era5_ds(era5_ds, era5_path)
    ds_ext = blend_beach_era5(ds_beach, era5_ds=era5,
                              blend_width_pa=blend_width_pa,
                              p_stitch_pa=p_stitch_pa)
    budget = compute_budget_ext(ds_ext, recompute_div=True)
    return budget, ds_ext


# ===========================================================================
# Self-test
# ===========================================================================

if __name__ == '__main__':
    import pathlib, sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

    path = _default_era5_omega_path()
    print(f'ERA5 omega path: {path}')

    if not pathlib.Path(path).exists():
        print('ERA5 file not found — run notebooks/download_era5.ipynb first.')
        sys.exit(0)

    ds_e = load_era5_omega(path)
    print(f'ERA5 loaded — time steps: {ds_e.sizes["time"]}  '
          f'levels: {ds_e.sizes["pressure_level"]}  '
          f'lat×lon: {ds_e.sizes["latitude"]}×{ds_e.sizes["longitude"]}')

    from scripts.mse_budget import load_dataset
    ds_b   = load_dataset()
    ds_ext = stitch_beach_era5(ds_b, path)
    n      = ds_ext['era5_n_levels'].values
    print(f'Stitch OK — ERA5 levels added: mean={n.mean():.1f}  '
          f'min={n.min()}  max={n.max()}')
    budget = compute_budget_ext(ds_ext)
    print(f'Budget OK — vert_adv mean: {float(budget["vert_adv"].mean()):.1f} W/m²')
