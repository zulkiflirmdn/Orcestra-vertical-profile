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
# Stitching
# ===========================================================================

def stitch_beach_era5(ds_beach, era5_path=None, p_stitch_pa=15000.0):
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

    era5_ds = load_era5_omega(era5_path)

    alt     = ds_beach['altitude'].values          # (nalt,) metres, uniform 10 m
    omega_b = ds_beach['omega'].values.astype(float)
    p_b     = ds_beach['p_mean'].values.astype(float)
    T_b     = ds_beach['ta_mean'].values
    q_b     = ds_beach['q_mean'].values
    ncircle = ds_beach.sizes['circle']
    nalt    = ds_beach.sizes['altitude']
    h_prof  = _mse(T_b, alt[np.newaxis, :], q_b)

    # Max number of ERA5 levels that could be added
    era5_p_all  = era5_ds['pressure_level_pa'].values
    n_era5_max  = int((era5_p_all < p_stitch_pa).sum())
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

        above = p_e < p_stitch_pa
        if above.sum() == 0:
            continue

        om_add  = om_e[above]
        p_add   = p_e[above]
        t_add   = t_e[above]
        div_add = div_e[above]
        n_add   = len(om_add)

        # Find top of BEACH valid data for this circle
        valid_b = (np.isfinite(omega_b[i]) & np.isfinite(p_b[i])
                   & np.isfinite(h_prof[i]))
        if valid_b.sum() < 3:
            continue
        idx_top = np.where(valid_b)[0][-1]
        z_top   = float(alt[idx_top])
        p_top   = float(p_b[i, idx_top])
        T_top   = float(T_b[i, idx_top])

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

def compute_budget_ext(ds_ext, mass_correct=False):
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
    ds_ext       : xr.Dataset  returned by stitch_beach_era5()
    mass_correct : bool  passed through to compute_budget()
    """
    from scripts.mse_budget import compute_budget

    nalt_orig = ds_ext.sizes['altitude']
    n_ext     = ds_ext.sizes['ext_level']
    n_pad     = n_ext - nalt_orig

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
    # ta_era5_ext already has BEACH T in the BEACH positions and ERA5 T in
    # the ERA5 positions, so it is the complete extended temperature array.
    ta_ext = ds_ext['ta_era5_ext'].values   # (circle, ext_level)

    # q_mean: BEACH q below, 0 above tropopause (ERA5 levels are dry)
    q_ext  = _pad_zero(ds_ext['q_mean'].values)

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
            # div_era5_ext already has BEACH div in BEACH positions and
            # ERA5 div (= -∂ω/∂p) in ERA5 positions — use it directly.
            'div':      _da(ds_ext['div_era5_ext'].values),
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
