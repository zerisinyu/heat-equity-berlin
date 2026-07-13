"""阶段 5：归一化、加权合成、敏感性检验。

- 每个底层指标在 542 个 PLR 间做百分位归一化（rank / n，NaN 排除在排名外）
- direction: lower_is_worse 的指标先取反（1 - pct）
- 维度分 = 维度内指标的加权平均（权重对缺失指标重归一，缺失不当零）
- 总指数 = 三维度加权平均
- 敏感性检验：多组权重重算，取最脆弱前 N 名，输出交集与稳定名单

输出 data/processed/plr_index.parquet + NOTES 用敏感性文本。
"""

import pandas as pd

from common import DATA_PROCESSED

OUT = DATA_PROCESSED / "plr_index.parquet"
MIN_POP = 100  # 人口低于此的 PLR 不参与排名（统计噪声）


def percentile_normalize(s: pd.Series, direction: str) -> pd.Series:
    """百分位归一化到 [0,1]，1 = 最脆弱。NaN 保持 NaN。"""
    pct = s.rank(pct=True, na_option="keep")
    if direction == "lower_is_worse":
        pct = 1.0 - pct
    return pct


def weighted_mean_renormalized(df: pd.DataFrame, weights: dict) -> pd.Series:
    """按权重加权平均；某行有缺失指标时，权重在非缺失指标间重归一。
    这样缺失不会被当成 0 拉低分数。"""
    w = pd.Series(weights)
    values = df[w.index]
    mask = values.notna()
    weighted = (values * w).sum(axis=1, skipna=True)
    effective_w = (mask * w).sum(axis=1)
    return weighted / effective_w.where(effective_w > 0)


def build_index(cfg: dict, indicators: pd.DataFrame,
                dim_weights: dict) -> pd.DataFrame:
    indicators_pop = indicators
    out = pd.DataFrame(index=indicators.index)
    dim_scores = {}
    for dim, inds in cfg["indicators"].items():
        norm_cols = {}
        for name, spec in inds.items():
            if name not in indicators.columns:
                continue  # 配置里有但数据缺席的指标（如 80+）直接跳过
            norm = percentile_normalize(indicators[name], spec["direction"])
            out[f"n_{name}"] = norm
            norm_cols[f"n_{name}"] = spec["weight"]
        dim_scores[dim] = weighted_mean_renormalized(out, norm_cols)
        out[f"dim_{dim}"] = dim_scores[dim]
    dims = pd.DataFrame(dim_scores)
    hv = weighted_mean_renormalized(dims, dim_weights)

    # 最低数据要求：三个维度分齐全，且人口 ≥ MIN_POP。
    # 否则总指数 = NaN（"数据不足"），防止无人 PLR（货运场站、森林）
    # 靠一两个维度的重归一权重登顶 —— 这不是脆弱，是噪声。
    complete = dims.notna().all(axis=1)
    if "pop_total" in indicators_pop.columns:
        complete &= indicators_pop["pop_total"].fillna(0) >= MIN_POP
    out["heat_vulnerability"] = hv.where(complete)
    return out


def sensitivity_check(cfg: dict, indicators: pd.DataFrame,
                      names: pd.Series) -> str:
    sa = cfg["sensitivity_analysis"]
    top_n = sa["top_n"]
    tops = {}
    for scen, w in sa["weight_scenarios"].items():
        idx = build_index(cfg, indicators, w)["heat_vulnerability"]
        tops[scen] = set(idx.nlargest(top_n).index)

    stable = set.intersection(*tops.values())
    lines = [f"敏感性检验（各情景最脆弱前 {top_n} 名）："]
    base = tops["equal"]
    for scen, s in tops.items():
        lines.append(f"  {scen}: 与 equal 重叠 {len(s & base)}/{top_n}")
    lines.append(f"  全部 {len(tops)} 组情景交集（稳定高危）: {len(stable)} 个")
    for plr_id in sorted(stable):
        lines.append(f"    - {plr_id} {names.get(plr_id, '?')}")
    return "\n".join(lines), stable


def run(cfg: dict) -> None:
    import geopandas as gpd
    indicators = pd.read_parquet(DATA_PROCESSED / "indicators.parquet").set_index("plr_id")
    plr = gpd.read_parquet(DATA_PROCESSED / "plr_base.parquet")
    names = plr.set_index("plr_id")["plr_name"]
    exposure = pd.read_parquet(DATA_PROCESSED / "exposure.parquet").set_index("plr_id")
    indicators = indicators.join(exposure)

    out = build_index(cfg, indicators, cfg["weights"])
    report, stable = sensitivity_check(cfg, indicators, names)
    out["stable_high_risk"] = out.index.isin(stable)

    merged = indicators.join(out)
    merged.reset_index().to_parquet(OUT)

    hv = out["heat_vulnerability"]
    print(f"    总指数覆盖 {hv.notna().sum()}/{len(hv)}，范围 [{hv.min():.3f}, {hv.max():.3f}]")
    print("    最脆弱前 10：")
    for pid in hv.nlargest(10).index:
        print(f"      {pid} {names[pid]}: {hv[pid]:.3f}")
    print()
    print("    " + report.replace("\n", "\n    "))
    print(f"    → {OUT.name}")

    # 敏感性检验结果落盘，阶段 8 引用
    (DATA_PROCESSED / "sensitivity_report.txt").write_text(report, encoding="utf-8")
