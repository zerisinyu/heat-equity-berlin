"""阶段 3：暴露维度 — 气候街区块面积加权聚合到 Planungsraum。

气候数据是 Siedlungsflächen 街区块级（16217 块），社会数据是 PLR 级。
用 overlay(intersection) 在 EPSG:25833 里切割，按相交面积加权求 PLR 均值。
纯绿地/森林 PLR 可能没有 Siedlung 块 → 指标保持 NaN，绝不填零。

输出 data/processed/exposure.parquet（plr_id + 各暴露指标）。
"""

import geopandas as gpd
import pandas as pd

from common import DATA_PROCESSED, DATA_RAW

OUT = DATA_PROCESSED / "exposure.parquet"

# 暴露指标 → (raw 文件, 值字段)
LAYERS = {
    "pet_day": ("klima_pet", "pet14h"),
    "utci_day": ("klima_utci", "utci14h"),
    "night_cooling": ("klima_abkuehl", "abkuehlmea"),
}


def aggregate_layer(plr: gpd.GeoDataFrame, raw_key: str, value_col: str,
                    working_crs: str) -> pd.Series:
    """一个气候图层按面积加权聚合到 PLR，返回以 plr_id 为索引的 Series。"""
    blocks = gpd.read_file(DATA_RAW / f"{raw_key}.geojson")
    if blocks.crs is None:
        blocks = blocks.set_crs(working_crs)
    blocks = blocks.to_crs(working_crs)[[value_col, "geometry"]]
    blocks = blocks[blocks[value_col].notna()]

    # 无效几何修复后做交集切割
    bad = ~blocks.geometry.is_valid
    if bad.any():
        blocks.loc[bad, "geometry"] = blocks.loc[bad, "geometry"].make_valid()

    inter = gpd.overlay(blocks, plr[["plr_id", "geometry"]],
                        how="intersection", keep_geom_type=True)
    inter["_area"] = inter.geometry.area
    inter = inter[inter["_area"] > 0]

    weighted = (
        inter.assign(_wv=inter[value_col] * inter["_area"])
        .groupby("plr_id")[["_wv", "_area"]].sum()
    )
    return weighted["_wv"] / weighted["_area"]


def run(cfg: dict) -> None:
    working = cfg["crs"]["working"]
    plr = gpd.read_parquet(DATA_PROCESSED / "plr_base.parquet")

    out = plr[["plr_id"]].set_index("plr_id")
    for indicator, (raw_key, value_col) in LAYERS.items():
        print(f"    聚合 {indicator} ← {raw_key}.{value_col} …")
        out[indicator] = aggregate_layer(plr, raw_key, value_col, working)
        s = out[indicator]
        print(f"      覆盖 {s.notna().sum()}/{len(s)} 个 PLR，"
              f"范围 [{s.min():.2f}, {s.max():.2f}]，中位 {s.median():.2f}")

    out.reset_index().to_parquet(OUT)
    print(f"    → {OUT.name}")

    # 肉眼检查图：PET 分级填色（checkpoint 要求最热落在市中心密集建成区）
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        merged = plr.merge(out.reset_index(), on="plr_id")
        ax = merged.plot(column="pet_day", cmap="YlOrRd", legend=True,
                         figsize=(12, 9), missing_kwds={"color": "lightgrey"})
        ax.set_title("PET 14:00, flaechengewichtetes Mittel (Siedlungsflaechen, 2022)")
        ax.set_axis_off()
        fig_path = DATA_PROCESSED / "check_pet.png"
        plt.savefig(fig_path, dpi=120, bbox_inches="tight")
        plt.close()
        print(f"    检查图 → {fig_path.name}")
    except ImportError:
        print("    （matplotlib 不可用，跳过检查图）")
