import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import numpy as np
import xarray as xr

CHECK_FILE = '/g/data/k10/zr7147/ERA5/PBL/era5_project.nc'
ds = xr.open_dataset(CHECK_FILE)

# ── 1. Structure ──────────────────────────────────────────────────────────────
print("── Structure ──")
assert ds.dims['time']      == 22752
assert ds.dims['level']     == 16
assert ds.dims['latitude']  == 101
assert ds.dims['longitude'] == 181
assert list(ds.data_vars)   == ['t', 'q', 'u', 'v', 'z', 'z_height']
print(f"  dims OK: {dict(ds.dims)}")
print(f"  vars OK: {list(ds.data_vars)}")

# ── 2. Time range ─────────────────────────────────────────────────────────────
print("\n── Time range ──")
print(f"  {ds.time.values[0]} → {ds.time.values[-1]}")
assert str(ds.time.values[0])[:10]  == '2010-01-01'
assert str(ds.time.values[-1])[:10] == '2025-02-28'
print("  OK ✓")

# ── 3. Physical range check ───────────────────────────────────────────────────
print("\n── Physical ranges (first 4 timesteps) ──")
checks = {
    't':        (180,  320),
    'q':        (0,    0.03),
    'u':        (-80,  80),
    'v':        (-80,  80),
    'z':        (0,    2e5),
    'z_height': (0,    20000),
}
all_ok = True
for var, (lo, hi) in checks.items():
    s = ds[var].isel(time=slice(0, 4)).values
    nan_frac = np.isnan(s).mean()
    vmin, vmax = float(np.nanmin(s)), float(np.nanmax(s))
    ok = nan_frac == 0 and lo <= vmin and vmax <= hi
    all_ok = all_ok and ok
    flag = "✓" if ok else "✗ PROBLEM"
    print(f"  {var:8s}  [{vmin:10.4f}, {vmax:10.4f}]  NaN={nan_frac:.2%}  {flag}")

# ── 4. Six-panel plot ─────────────────────────────────────────────────────────
print("\n── Generating 6-panel check plot ──")
mask = (ds.time.dt.year == 2018) & (ds.time.dt.month == 1)

panels = [
    ('t',        850, 'RdBu_r',  'T (K)'),
    ('q',        850, 'Blues',   'q (kg/kg)'),
    ('u',        850, 'RdBu_r',  'u (m/s)'),
    ('v',        850, 'RdBu_r',  'v (m/s)'),
    ('z_height', 850, 'viridis', 'z height (m)'),
    ('t',        500, 'RdBu_r',  'T 500 hPa (K)'),
]

fig, axes = plt.subplots(2, 3, figsize=(16, 8),
                          subplot_kw={'projection': ccrs.PlateCarree()})
for ax, (var, lev, cmap, label) in zip(axes.flat, panels):
    data = ds[var].sel(level=lev).isel(time=mask).mean('time')
    data.plot(ax=ax, transform=ccrs.PlateCarree(), cmap=cmap,
              cbar_kwargs={'label': label, 'shrink': 0.7})
    ax.add_feature(cfeature.LAND, facecolor='lightgray', zorder=3)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, zorder=4)
    ax.gridlines(alpha=0.3)
    ax.set_title(f'{var} @ {lev} hPa — Jan 2018')

plt.suptitle('ERA5 integrity check — Jan 2018 mean', fontsize=13)
plt.tight_layout()
out = '/g/data/k10/zr7147/ERA5/PBL/era5_integrity_check.png'
plt.savefig(out, dpi=100, bbox_inches='tight')
plt.close()
print(f"  Saved → {out}")

print("\n" + "=" * 50)
print("ALL CHECKS PASSED ✓" if all_ok else "⚠ SOME CHECKS FAILED — review above")
print("=" * 50)
ds.close()
