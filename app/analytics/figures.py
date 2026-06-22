"""Render publication-style figures (PNG) from already-computed analysis results.

Consistent with the platform's core principle, this module does NOT compute any
statistic — it only visualises numbers produced by the deterministic engine.
Figures are saved to disk and the file paths are returned so the document
generator can embed them and the API can serve them.
"""
from __future__ import annotations

import os
import uuid

import matplotlib

matplotlib.use("Agg")  # headless / server-safe
import matplotlib.pyplot as plt  # noqa: E402

# A restrained, academic palette.
_PRIMARY = "#2563eb"
_ACCENT = "#0ea5e9"
_GREY = "#94a3b8"
plt.rcParams.update(
    {
        "figure.dpi": 150,
        "savefig.dpi": 150,
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
    }
)


def _new_path(out_dir: str, stub: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, f"{stub}_{uuid.uuid4().hex[:8]}.{_EXT}")


def _save(fig, path: str) -> str:
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white", dpi=_DPI)
    plt.close(fig)
    return path


# Current export format/resolution, switched by export_figures(). PNG at screen
# resolution by default; raised to publication quality (or vector) on export.
_EXT = "png"
_DPI = 150


def export_figures(
    analysis_type: str, results: dict, out_dir: str, fmt: str = "png", dpi: int = 300
) -> list[dict]:
    """Render figures in a publication-grade format (png at high DPI, or svg/pdf).

    Reuses the same chart builders as on-screen figures so what users export
    matches what they reviewed. Returns the same [{path, caption, kind}] shape.
    """
    global _EXT, _DPI
    fmt = (fmt or "png").lower()
    if fmt not in {"png", "svg", "pdf"}:
        fmt = "png"
    prev_ext, prev_dpi = _EXT, _DPI
    _EXT, _DPI = fmt, int(dpi)
    try:
        return figures_for(analysis_type, results, out_dir)
    finally:
        _EXT, _DPI = prev_ext, prev_dpi


def figures_for(analysis_type: str, results: dict, out_dir: str) -> list[dict]:
    """Dispatch to the right chart(s) for an analysis type.

    Returns a list of {"path", "caption", "kind"} describing each saved figure.
    Never raises on bad input — returns [] so report generation can't break.
    """
    try:
        if analysis_type == "frequency":
            return _frequency_charts(results, out_dir)
        if analysis_type == "descriptive":
            return _descriptive_chart(results, out_dir)
        if analysis_type == "correlation":
            return _correlation_heatmap(results, out_dir)
        if analysis_type == "regression":
            return _regression_chart(results, out_dir)
        if analysis_type == "anova":
            return _anova_chart(results, out_dir)
        if analysis_type == "plspm":
            return _plspm_figures(results, out_dir)
        if analysis_type == "likert":
            return _likert_stacked(results, out_dir)
        if analysis_type == "thematic":
            return _thematic_figures(results, out_dir)
    except Exception:
        return []
    return []


def _frequency_charts(results: dict, out_dir: str) -> list[dict]:
    figs = []
    for var, payload in (results.get("variables") or {}).items():
        chart = payload.get("chart") or {}
        labels = [str(x) for x in chart.get("labels", [])]
        values = chart.get("values", [])
        if not labels or not values:
            continue
        fig, ax = plt.subplots(figsize=(6, 3.6))
        ax.bar(labels, values, color=_PRIMARY)
        ax.set_title(f"Distribution of {var}")
        ax.set_ylabel("Frequency")
        if max((len(l) for l in labels), default=0) > 6 or len(labels) > 5:
            plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        path = _save(fig, _new_path(out_dir, f"freq_{var}"))
        figs.append({"path": path, "caption": f"Figure: Frequency distribution of {var}.", "kind": "bar"})
    return figs


def _descriptive_chart(results: dict, out_dir: str) -> list[dict]:
    variables = results.get("variables") or {}
    names = list(variables.keys())
    means = [variables[n].get("mean") for n in names]
    stds = [variables[n].get("std") or 0 for n in names]
    pairs = [(n, m, s) for n, m, s in zip(names, means, stds) if m is not None]
    if not pairs:
        return []
    names, means, stds = zip(*pairs)
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.bar(names, means, yerr=stds, capsize=4, color=_ACCENT, ecolor=_GREY)
    ax.set_title("Variable means (±1 SD)")
    ax.set_ylabel("Mean score")
    if len(names) > 4:
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    path = _save(fig, _new_path(out_dir, "descriptive_means"))
    return [{"path": path, "caption": "Figure: Mean values of study variables with standard-deviation bars.", "kind": "bar"}]


def _correlation_heatmap(results: dict, out_dir: str) -> list[dict]:
    matrix = results.get("matrix") or {}
    cols = matrix.get("columns") or []
    values = matrix.get("values") or []
    if len(cols) < 2 or not values:
        return []
    fig, ax = plt.subplots(figsize=(0.9 * len(cols) + 2, 0.9 * len(cols) + 1.5))
    im = ax.imshow(values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(cols)))
    ax.set_yticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=40, ha="right")
    ax.set_yticklabels(cols)
    for i in range(len(cols)):
        for j in range(len(cols)):
            ax.text(j, i, f"{values[i][j]:.2f}", ha="center", va="center",
                    color="white" if abs(values[i][j]) > 0.5 else "black", fontsize=8)
    ax.set_title("Correlation matrix")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.grid(False)
    path = _save(fig, _new_path(out_dir, "corr_heatmap"))
    return [{"path": path, "caption": "Figure: Correlation matrix of study variables.", "kind": "heatmap"}]


def _regression_chart(results: dict, out_dir: str) -> list[dict]:
    coeffs = [c for c in (results.get("coefficients") or []) if c.get("term") != "intercept"]
    betas = [(c["term"], c.get("std_beta")) for c in coeffs if c.get("std_beta") is not None]
    if not betas:
        return []
    names, vals = zip(*betas)
    colors = [_PRIMARY if v >= 0 else "#ef4444" for v in vals]
    fig, ax = plt.subplots(figsize=(6.2, 0.6 * len(names) + 1.5))
    ax.barh(names, vals, color=colors)
    ax.axvline(0, color=_GREY, linewidth=0.8)
    ax.set_title("Standardised regression coefficients (β)")
    ax.set_xlabel("β")
    path = _save(fig, _new_path(out_dir, "regression_betas"))
    return [{"path": path, "caption": "Figure: Standardised coefficients showing each predictor's relative contribution.", "kind": "bar"}]


def _anova_chart(results: dict, out_dir: str) -> list[dict]:
    chart = results.get("chart") or {}
    labels = [str(x) for x in chart.get("labels", [])]
    means = chart.get("means", [])
    errors = chart.get("errors", [])
    if not labels or not means:
        return []
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    ax.bar(labels, means, yerr=errors or None, capsize=4, color=_PRIMARY, ecolor=_GREY)
    ax.set_title(f"Group means: {results.get('dependent', 'outcome')}")
    ax.set_ylabel("Mean")
    if len(labels) > 4:
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    path = _save(fig, _new_path(out_dir, "anova_means"))
    return [{"path": path, "caption": f"Figure: Mean {results.get('dependent','outcome')} by group (±1 SD).", "kind": "bar"}]


# ---------------------------------------------------------------------------
# PLS-PM figures
# ---------------------------------------------------------------------------
_POS = "#2563eb"   # positive path (blue)
_NEG = "#dc2626"   # negative path (red)


def _plspm_figures(results: dict, out_dir: str) -> list[dict]:
    figs: list[dict] = []
    p = _plspm_path_diagram(results, out_dir)
    if p:
        figs.append(p)
    figs.extend(_plspm_loadings(results, out_dir))
    return figs


def _plspm_path_diagram(results: dict, out_dir: str) -> dict | None:
    import numpy as np
    inner = results.get("inner_model") or {}
    latents = results.get("latents") or []
    if not inner or not latents:
        return None

    # endogenous (have predictors) on the right; predictors on the left
    endog = list(inner.keys())
    predictors = [lv for lv in latents if lv not in endog]
    pos = {}
    for i, lv in enumerate(predictors):
        y = 1 - (i + 0.5) / max(len(predictors), 1)
        pos[lv] = (0.08, y)
    for i, lv in enumerate(endog):
        y = 1 - (i + 0.5) / max(len(endog), 1)
        pos[lv] = (0.92, y)

    fig, ax = plt.subplots(figsize=(8.4, 0.9 * max(len(predictors), len(endog)) + 1.5))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    # edges
    for outcome, info in inner.items():
        x2, y2 = pos[outcome]
        for pred, pinfo in (info.get("predictors") or {}).items():
            if pred not in pos:
                continue
            x1, y1 = pos[pred]
            beta = pinfo.get("path_coefficient", 0.0)
            sig = pinfo.get("significant", False)
            color = _POS if beta >= 0 else _NEG
            lw = 0.8 + 4.5 * min(abs(beta), 1.0)
            ax.annotate(
                "", xy=(x2 - 0.10, y2), xytext=(x1 + 0.10, y1),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                alpha=0.9 if sig else 0.45),
            )
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2 + 0.02
            label = f"{beta:+.2f}" + ("*" if sig else "")
            ax.text(mx, my, label, fontsize=9, color=color, ha="center",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))

    # nodes
    for lv, (x, y) in pos.items():
        is_out = lv in endog
        r2 = inner.get(lv, {}).get("r_squared")
        node_label = lv if not is_out else f"{lv}\nR2={r2:.2f}" if r2 is not None else lv
        ax.add_patch(plt.matplotlib.patches.FancyBboxPatch(
            (x - 0.085, y - 0.055), 0.17, 0.11,
            boxstyle="round,pad=0.02", fc="#eef2ff" if is_out else "#f8fafc",
            ec=_PRIMARY if is_out else _GREY, lw=1.6))
        ax.text(x, y, node_label, ha="center", va="center", fontsize=9, wrap=True)

    ax.set_title("PLS-PM structural model (path coefficients; * p < .05)")
    path = _new_path(out_dir, "plspm_path")
    return {"path": _save(fig, path),
            "caption": "Figure: PLS-PM structural model showing path coefficients between latent constructs (blue = positive, red = negative; * significant at p < .05).",
            "kind": "path_diagram"}


def _plspm_loadings(results: dict, out_dir: str) -> list[dict]:
    outer = results.get("outer_model") or {}
    if not outer:
        return []
    constructs = list(outer.items())
    n = len(constructs)
    ncol = min(3, n)
    nrow = (n + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.6 * ncol, 2.6 * nrow), squeeze=False)
    for ax in axes.flat:
        ax.axis("off")
    for idx, (lv, items) in enumerate(constructs):
        ax = axes[idx // ncol][idx % ncol]
        ax.axis("on")
        names = [it["indicator"] for it in items]
        loads = [it["loading"] for it in items]
        colors = [_POS if v >= 0 else _NEG for v in loads]
        ax.barh(range(len(names)), loads, color=colors, alpha=0.85)
        ax.set_yticks(range(len(names))); ax.set_yticklabels(names, fontsize=8)
        ax.set_xlim(-1, 1); ax.axvline(0, color=_GREY, lw=0.8)
        ax.set_title(lv, fontsize=10)
        ax.invert_yaxis()
    fig.suptitle("PLS-PM outer model: indicator loadings", fontsize=11)
    path = _new_path(out_dir, "plspm_loadings")
    return [{"path": _save(fig, path),
             "caption": "Figure: Outer-model loadings linking each latent construct to its manifest indicators.",
             "kind": "loadings"}]


# ---------------------------------------------------------------------------
# Likert stacked proportions (one row per item)
# ---------------------------------------------------------------------------
_LIKERT_COLORS = ["#15803d", "#86efac", "#fde68a", "#f59e0b", "#dc2626"]  # SA..SD
_LIKERT_LABELS = ["Strongly Agree", "Agree", "Neutral", "Disagree", "Strongly Disagree"]


def _likert_stacked(results: dict, out_dir: str) -> list[dict]:
    items = results.get("items") or {}
    if not items:
        return []
    labels = list(items.keys())
    # each item -> ordered proportions for points 5..1 (SA..SD)
    import numpy as np
    mat = []
    for it in labels:
        counts = items[it]  # dict like {"5":n,...} or list ordered 1..5
        if isinstance(counts, dict):
            vals = [counts.get(str(k), counts.get(k, 0)) for k in [5, 4, 3, 2, 1]]
        else:
            vals = list(reversed(list(counts)))  # assume ascending 1..5
        total = sum(vals) or 1
        mat.append([v / total * 100 for v in vals])
    mat = np.array(mat)

    fig, ax = plt.subplots(figsize=(8.6, 0.42 * len(labels) + 1.6))
    left = np.zeros(len(labels))
    for s in range(mat.shape[1]):
        ax.barh(labels, mat[:, s], left=left, color=_LIKERT_COLORS[s],
                label=_LIKERT_LABELS[s], edgecolor="white", linewidth=0.5)
        left += mat[:, s]
    ax.set_xlim(0, 100); ax.set_xlabel("Percentage of respondents")
    ax.invert_yaxis()
    ax.legend(ncol=5, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.12), frameon=False)
    ax.set_title(results.get("title", "Distribution of responses"))
    path = _new_path(out_dir, "likert")
    return [{"path": _save(fig, path),
             "caption": "Figure: Stacked distribution of responses across items.",
             "kind": "likert"}]


# ---------------------------------------------------------------------------
# Thematic analysis figures
# ---------------------------------------------------------------------------
def _thematic_figures(results: dict, out_dir: str) -> list[dict]:
    themes = results.get("themes") or []
    if not themes:
        return []
    figs = []
    p = _thematic_prevalence(themes, out_dir)
    if p:
        figs.append(p)
    return figs


def _thematic_prevalence(themes: list[dict], out_dir: str) -> dict | None:
    rows = [(t.get("name", ""), t.get("prevalence", 0) * 100) for t in themes]
    rows = [r for r in rows if r[0]]
    if not rows:
        return None
    rows.sort(key=lambda r: r[1])
    names = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    fig, ax = plt.subplots(figsize=(8.2, 0.5 * len(names) + 1.4))
    ax.barh(names, vals, color=_PRIMARY, alpha=0.85)
    for i, v in enumerate(vals):
        ax.text(v + 1, i, f"{v:.0f}%", va="center", fontsize=9, color=_GREY)
    ax.set_xlim(0, max(100, max(vals) + 8))
    ax.set_xlabel("Prevalence (% of responses mentioning the theme)")
    ax.set_title("Themes by prevalence")
    path = _new_path(out_dir, "thematic_prevalence")
    return {"path": _save(fig, path),
            "caption": "Figure: Themes identified through thematic analysis, ranked by the share of responses in which each appeared.",
            "kind": "thematic"}
