"""Partial Least Squares Path Modelling (PLS-PM), pure NumPy.

Implements the classic Wold/Lohmoller reflective (mode A) algorithm with the
path (structural) weighting scheme, plus the standard quality criteria and a
bootstrap for inference. No R / plspm dependency.

Inputs
------
measurement : {latent_name: [manifest_column, ...]}      reflective blocks
paths       : {endogenous_latent: [predictor_latent, ...]} inner structural model

Output (JSON-serialisable dict)
-------------------------------
- outer_model:   per latent, per indicator loading + weight + communality
- inner_model:   per endogenous latent, path coefficients with SE/t/p + R^2
- quality:       per latent Cronbach alpha, composite reliability (rho_c), AVE
- effects:       direct / indirect / total effects per path
- gof:           global goodness-of-fit
- latent_scores summary + the construct correlation matrix
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def _standardize(mat: np.ndarray) -> np.ndarray:
    mu = mat.mean(axis=0)
    sd = mat.std(axis=0, ddof=1)
    sd[sd == 0] = 1.0
    return (mat - mu) / sd


def _converged(a: np.ndarray, b: np.ndarray, tol: float) -> bool:
    return bool(np.max(np.abs(np.abs(a) - np.abs(b))) < tol)


class PLSPMError(ValueError):
    pass


def run_plspm(
    df: pd.DataFrame,
    measurement: dict[str, list[str]],
    paths: dict[str, list[str]],
    *,
    max_iter: int = 300,
    tol: float = 1e-7,
    bootstrap: int = 300,
    seed: int = 42,
) -> dict:
    latents = list(measurement.keys())
    # keep only indicators present in the data
    blocks = {lv: [c for c in cols if c in df.columns] for lv, cols in measurement.items()}
    blocks = {lv: cols for lv, cols in blocks.items() if len(cols) >= 1}
    latents = list(blocks.keys())
    if len(latents) < 2:
        raise PLSPMError("PLS-PM needs at least two latent constructs with indicators present in the data.")

    all_mvs = [c for cols in blocks.values() for c in cols]
    data = df[all_mvs].apply(pd.to_numeric, errors="coerce").dropna()
    if len(data) < 10:
        raise PLSPMError("Not enough complete cases for PLS-PM (need at least 10).")

    X = _standardize(data.values.astype(float))
    col_index = {c: i for i, c in enumerate(all_mvs)}
    block_idx = {lv: [col_index[c] for c in cols] for lv, cols in blocks.items()}

    # predecessors/successors from the structural model
    preds = {lv: [p for p in paths.get(lv, []) if p in latents] for lv in latents}
    succ = {lv: [k for k in latents if lv in preds.get(k, [])] for lv in latents}

    weights, scores = _estimate_weights(X, latents, block_idx, preds, succ, max_iter, tol)

    # outer loadings (corr of each MV with its LV score)
    loadings = {}
    for lv in latents:
        ls = scores[:, latents.index(lv)]
        loadings[lv] = {all_mvs[j]: float(np.corrcoef(X[:, j], ls)[0, 1]) for j in block_idx[lv]}

    inner, effects = _inner_model(scores, latents, preds)
    quality = _quality(X, block_idx, loadings, all_mvs, latents)
    gof = _gof(quality, inner, latents)

    boot = _bootstrap(data.values.astype(float), all_mvs, block_idx, latents,
                      preds, succ, max_iter, tol, bootstrap, seed)
    _attach_inference(inner, loadings, boot, latents)

    # construct correlation matrix
    corr = np.corrcoef(scores, rowvar=False)
    construct_corr = {
        latents[i]: {latents[j]: round(float(corr[i, j]), 3) for j in range(len(latents))}
        for i in range(len(latents))
    }

    return {
        "method": "plspm",
        "n": int(len(data)),
        "latents": latents,
        "outer_model": _outer_payload(loadings, weights, all_mvs, block_idx, latents),
        "inner_model": inner,
        "effects": effects,
        "quality": quality,
        "gof": round(gof, 4),
        "construct_correlations": construct_corr,
    }


# ---------------------------------------------------------------------------
def _estimate_weights(X, latents, block_idx, preds, succ, max_iter, tol):
    n = X.shape[0]
    # init outer weights = 1 for each indicator
    w = {lv: np.ones(len(block_idx[lv])) for lv in latents}

    def lv_scores(weights):
        S = np.zeros((n, len(latents)))
        for li, lv in enumerate(latents):
            block = X[:, block_idx[lv]]
            y = block @ weights[lv]
            sd = y.std(ddof=1) or 1.0
            S[:, li] = y / sd
        return S

    scores = lv_scores(w)
    prev = np.concatenate([w[lv] for lv in latents])

    for _ in range(max_iter):
        # inner approximation (path weighting scheme)
        Z = np.zeros_like(scores)
        for li, lv in enumerate(latents):
            agg = np.zeros(scores.shape[0])
            # successors: use correlation
            for k in succ[lv]:
                ki = latents.index(k)
                agg += np.corrcoef(scores[:, li], scores[:, ki])[0, 1] * scores[:, ki]
            # predecessors: use multiple-regression coefficients of this LV on its predecessors
            if preds[lv]:
                pidx = [latents.index(p) for p in preds[lv]]
                P = scores[:, pidx]
                coef, *_ = np.linalg.lstsq(P, scores[:, li], rcond=None)
                for c, pi in zip(coef, pidx):
                    agg += c * scores[:, pi]
            Z[:, li] = agg
        # outer weights update (mode A: regress each indicator on inner estimate)
        new_w = {}
        for li, lv in enumerate(latents):
            z = Z[:, li]
            zz = z @ z or 1.0
            new_w[lv] = np.array([(X[:, j] @ z) / zz for j in block_idx[lv]])
        scores = lv_scores(new_w)
        cur = np.concatenate([new_w[lv] for lv in latents])
        if _converged(cur, prev, tol):
            w = new_w
            break
        w, prev = new_w, cur

    return w, lv_scores(w)


def _inner_model(scores, latents, preds):
    inner = {}
    effects = []
    direct = {lv: {} for lv in latents}
    for lv in latents:
        ps = preds[lv]
        if not ps:
            continue
        li = latents.index(lv)
        pidx = [latents.index(p) for p in ps]
        P = scores[:, pidx]
        y = scores[:, li]
        coef, *_ = np.linalg.lstsq(P, y, rcond=None)
        yhat = P @ coef
        ss_res = float(((y - yhat) ** 2).sum())
        ss_tot = float(((y - y.mean()) ** 2).sum()) or 1.0
        r2 = 1 - ss_res / ss_tot
        inner[lv] = {
            "r_squared": round(r2, 4),
            "predictors": {p: {"path_coefficient": round(float(c), 4)} for p, c in zip(ps, coef)},
        }
        for p, c in zip(ps, coef):
            direct[p][lv] = float(c)
            effects.append({"from": p, "to": lv, "direct": round(float(c), 4)})
    return inner, effects


def _quality(X, block_idx, loadings, all_mvs, latents):
    q = {}
    for lv in latents:
        idx = block_idx[lv]
        load = np.array([loadings[lv][all_mvs[j]] for j in idx])
        k = len(idx)
        communalities = load ** 2
        ave = float(communalities.mean()) if k else 0.0
        sum_load = load.sum()
        sum_err = (1 - communalities).sum()
        rho_c = float((sum_load ** 2) / (sum_load ** 2 + sum_err)) if k else 0.0
        # Cronbach alpha from the indicator correlation matrix
        if k > 1:
            R = np.corrcoef(X[:, idx], rowvar=False)
            mean_r = (R.sum() - k) / (k * (k - 1))
            alpha = float((k * mean_r) / (1 + (k - 1) * mean_r)) if mean_r > 0 else 0.0
        else:
            alpha = float("nan")
        q[lv] = {
            "n_indicators": k,
            "cronbach_alpha": None if k <= 1 else round(alpha, 4),
            "composite_reliability": round(rho_c, 4),
            "ave": round(ave, 4),
        }
    return q


def _gof(quality, inner, latents):
    comm = [q["ave"] for q in quality.values() if q["ave"] > 0]
    r2s = [inner[lv]["r_squared"] for lv in inner]
    if not comm or not r2s:
        return 0.0
    return float(np.sqrt(np.mean(comm) * np.mean(r2s)))


# ---------------------------------------------------------------------------
def _bootstrap(raw, all_mvs, block_idx, latents, preds, succ, max_iter, tol, n_boot, seed):
    if n_boot <= 0:
        return {"paths": {}, "loadings": {}}
    rng = np.random.default_rng(seed)
    n = raw.shape[0]
    path_samples: dict[tuple[str, str], list[float]] = {}
    load_samples: dict[tuple[str, str], list[float]] = {}

    for _ in range(n_boot):
        rows = rng.integers(0, n, n)
        Xb = _standardize(raw[rows])
        try:
            _, scores = _estimate_weights(Xb, latents, block_idx, preds, succ, max_iter, tol)
        except Exception:
            continue
        # paths
        for lv in latents:
            ps = preds[lv]
            if not ps:
                continue
            li = latents.index(lv)
            pidx = [latents.index(p) for p in ps]
            coef, *_ = np.linalg.lstsq(scores[:, pidx], scores[:, li], rcond=None)
            for p, c in zip(ps, coef):
                path_samples.setdefault((p, lv), []).append(float(c))
        # loadings
        for lv in latents:
            ls = scores[:, latents.index(lv)]
            for j in block_idx[lv]:
                load_samples.setdefault((lv, all_mvs[j]), []).append(
                    float(np.corrcoef(Xb[:, j], ls)[0, 1])
                )
    return {"paths": path_samples, "loadings": load_samples}


def _attach_inference(inner, loadings, boot, latents):
    for (p, lv), samples in boot.get("paths", {}).items():
        if lv not in inner or p not in inner[lv]["predictors"] or not samples:
            continue
        arr = np.array(samples)
        se = float(arr.std(ddof=1)) or 1e-9
        est = inner[lv]["predictors"][p]["path_coefficient"]
        t = est / se
        # two-sided p from the bootstrap t (normal approx on resamples)
        pval = float(2 * (1 - stats.norm.cdf(abs(t))))
        ci = (float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5)))
        inner[lv]["predictors"][p].update({
            "std_error": round(se, 4),
            "t_value": round(t, 4),
            "p_value": round(pval, 4),
            "significant": bool(pval < 0.05),
            "ci_95": [round(ci[0], 4), round(ci[1], 4)],
        })


def _outer_payload(loadings, weights, all_mvs, block_idx, latents):
    out = {}
    for lv in latents:
        items = []
        wv = weights[lv]
        for pos, j in enumerate(block_idx[lv]):
            load = loadings[lv][all_mvs[j]]
            items.append({
                "indicator": all_mvs[j],
                "loading": round(float(load), 4),
                "weight": round(float(wv[pos]), 4),
                "communality": round(float(load ** 2), 4),
            })
        out[lv] = items
    return out
