"""
Main science figure for RQ2: GMS_adv by convective category.

Two panels:
  Left  — Violin + scatter of GMS_adv, grouped by category, with bootstrap 95% CI
  Right — Scatter of vert_adv vs vert_adv_dse coloured by category

Usage:
    python scripts/plot_gms_science_figure.py [--no-mc] [--out PATH]

Defaults to mass_correct=True and saves to /g/data/k10/zr7147/figures/gms_science_figure.png
"""

import argparse
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Allow running from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.mse_budget import compute_budget, DEFAULT_ZARR

# ── colours ────────────────────────────────────────────────────────────────
COLOR = {"Top-Heavy": "#d62728", "Bottom-Heavy": "#1f77b4"}
DEFAULT_OUT = "/g/data/k10/zr7147/figures/gms_science_figure.png"
N_BOOT = 10_000
RNG = np.random.default_rng(42)


def bootstrap_gms(va, vd, n=N_BOOT):
    """Bootstrap 95% CI for ratio-of-means GMS_adv = mean(va)/mean(vd)."""
    n_obs = len(va)
    gms_boot = np.empty(n)
    for i in range(n):
        idx = RNG.integers(0, n_obs, size=n_obs)
        gms_boot[i] = va[idx].mean() / vd[idx].mean()
    return np.percentile(gms_boot, [2.5, 97.5])


def group_gms(budget, cat):
    cats = budget["category_avg"].values
    mask = np.array([cat in str(c) for c in cats])
    va = budget["vert_adv"].values[mask]
    vd = budget["vert_adv_dse"].values[mask]
    # drop NaNs
    ok = np.isfinite(va) & np.isfinite(vd)
    va, vd = va[ok], vd[ok]
    gms_mean = va.mean() / vd.mean()
    ci = bootstrap_gms(va, vd)
    return va, vd, gms_mean, ci


def per_circle_gms(va, vd, threshold=10.0):
    """Per-circle GMS (for scatter only — not used for group stats)."""
    gms = np.where(np.abs(vd) > threshold, va / vd, np.nan)
    return gms


def make_figure(budget, out_path):
    categories = ["Top-Heavy", "Bottom-Heavy"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    fig.suptitle(
        "Gross Moist Stability by Convective Category\n"
        "ORCESTRA BEACH L4 · Method 1 (GMS$_\\mathrm{adv}$) · Mass-corrected",
        fontsize=13, fontweight="bold"
    )

    # ── Left panel: violin + scatter + group CI ────────────────────────────
    ax = axes[0]
    positions = [1, 2]
    stats_rows = []

    for pos, cat in zip(positions, categories):
        va, vd, gms_mean, ci = group_gms(budget, cat)
        gms_circ = per_circle_gms(va, vd)
        n_circ = np.sum(np.isfinite(gms_circ))
        color = COLOR[cat]

        # violin
        vp = ax.violinplot([gms_circ[np.isfinite(gms_circ)]], positions=[pos],
                           widths=0.5, showmeans=False, showmedians=False,
                           showextrema=False)
        for body in vp["bodies"]:
            body.set_facecolor(color)
            body.set_alpha(0.35)
            body.set_edgecolor(color)

        # per-circle scatter (jittered)
        jitter = RNG.uniform(-0.08, 0.08, size=n_circ)
        ax.scatter(pos + jitter, gms_circ[np.isfinite(gms_circ)],
                   color=color, s=22, alpha=0.7, zorder=3)

        # group mean + CI
        ax.errorbar(pos, gms_mean, yerr=[[gms_mean - ci[0]], [ci[1] - gms_mean]],
                    fmt="D", color=color, markersize=9, linewidth=2.5,
                    capsize=6, zorder=5, label=f"{cat}\nGMS={gms_mean:.3f} [{ci[0]:.3f}, {ci[1]:.3f}]")

        stats_rows.append((cat, n_circ, gms_mean, ci[0], ci[1]))

    ax.axhline(0, color="k", linewidth=0.8, linestyle="--", alpha=0.6)
    ax.set_xticks(positions)
    ax.set_xticklabels(categories, fontsize=11)
    ax.set_ylabel("GMS$_\\mathrm{adv}$ (dimensionless)", fontsize=11)
    ax.set_title("GMS$_\\mathrm{adv}$ = $\\langle\\omega\\,\\partial h/\\partial p\\rangle$ / $\\langle\\omega\\,\\partial s/\\partial p\\rangle$",
                 fontsize=10)
    ax.legend(fontsize=9, loc="upper right")
    ax.grid(axis="y", alpha=0.3)

    # ── Right panel: vert_adv vs vert_adv_dse scatter ─────────────────────
    ax2 = axes[1]
    for cat in categories:
        cats = budget["category_avg"].values
        mask = np.array([cat in str(c) for c in cats])
        va_all = budget["vert_adv"].values[mask]
        vd_all = budget["vert_adv_dse"].values[mask]
        ok = np.isfinite(va_all) & np.isfinite(vd_all)
        ax2.scatter(vd_all[ok], va_all[ok], color=COLOR[cat], s=30,
                    alpha=0.75, label=cat)

    # reference slope lines
    xlim_ref = np.array([-60, 60])
    for slope, ls, lw in [(0, "k", 0.8), (0.32, "#d62728", 0.8), (-0.34, "#1f77b4", 0.8)]:
        label = f"GMS = {slope:+.2f}" if slope != 0 else "GMS = 0"
        ax2.plot(xlim_ref, slope * xlim_ref, linestyle="--", color="gray" if slope == 0 else "gray",
                 linewidth=lw, alpha=0.5)
        ax2.text(xlim_ref[1], slope * xlim_ref[1], label, fontsize=8,
                 va="bottom", ha="right", color="gray")

    ax2.set_xlabel("$\\langle\\omega\\,\\partial s/\\partial p\\rangle$ (W m$^{-2}$)", fontsize=11)
    ax2.set_ylabel("$\\langle\\omega\\,\\partial h/\\partial p\\rangle$ (W m$^{-2}$)", fontsize=11)
    ax2.set_title("Vertical MSE vs DSE advection by circle", fontsize=10)
    patches = [mpatches.Patch(color=COLOR[c], label=c) for c in categories]
    ax2.legend(handles=patches, fontsize=9)
    ax2.axhline(0, color="k", linewidth=0.5, alpha=0.4)
    ax2.axvline(0, color="k", linewidth=0.5, alpha=0.4)
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Figure saved → {out_path}")

    # ── Text summary ───────────────────────────────────────────────────────
    print("\n── GMS_adv Summary (mass-corrected, group means) ──────────────────")
    for cat, n, gms, lo, hi in stats_rows:
        print(f"  {cat:<15}  n={n:2d}  GMS_adv = {gms:+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]")
    print("─" * 60)


def main():
    parser = argparse.ArgumentParser(description="GMS_adv science figure")
    parser.add_argument("--no-mc", action="store_true", help="Skip mass correction")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output path for PNG")
    args = parser.parse_args()

    print("Loading BEACH L4 dataset and computing budget …")
    budget = compute_budget(mass_correct=not args.no_mc)
    print(f"  Circles loaded: {budget.sizes['circle']}")
    print(f"  Mass correction: {'ON' if not args.no_mc else 'OFF'}")

    make_figure(budget, args.out)


if __name__ == "__main__":
    main()
