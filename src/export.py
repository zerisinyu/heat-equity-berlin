"""阶段 7 前置：导出前端 GeoJSON。

- web/data/plr.geojson：Planungsraum 多边形 + 总指数/维度分/底层指标（4326，
  坐标量化到 5 位小数控制体积）
- web/data/refuges.geojson：降温点（由 refuges.py 产出，这里拷贝）
"""

import json
import shutil

import geopandas as gpd
import pandas as pd

from common import DATA_PROCESSED, WEB_DIR

WEB_DATA = WEB_DIR / "data"

# 前端需要的列（底层指标原值 + 归一化维度分 + 总指数）
EXPORT_COLS = [
    "plr_name", "pop_total",
    "pet_day", "utci_day", "night_cooling",
    "share_65plus", "share_0to6", "transfer_income", "child_poverty",
    "single_parent_children", "unemployment",
    "street_tree_density", "green_share", "dist_to_fountain",
    "dim_exposure", "dim_sensitivity", "dim_adaptive_capacity_lack",
    "heat_vulnerability", "stable_high_risk",
]


def run(cfg: dict) -> None:
    WEB_DATA.mkdir(exist_ok=True)

    plr = gpd.read_parquet(DATA_PROCESSED / "plr_base.parquet")
    idx = pd.read_parquet(DATA_PROCESSED / "plr_index.parquet")
    merged = plr.merge(idx.drop(columns=["plr_name"], errors="ignore"), on="plr_id")

    cols = ["plr_id"] + [c for c in EXPORT_COLS if c in merged.columns]
    out = merged[cols + ["geometry"]].to_crs(cfg["crs"]["output"])

    # 数值列压到合理精度，几何简化 + 5 位小数（约 1m），控制文件体积
    out.geometry = out.geometry.simplify(0.00005)
    for c in out.columns:
        if out[c].dtype == "float64":
            out[c] = out[c].round(4)

    path = WEB_DATA / "plr.geojson"
    out.to_file(path, driver="GeoJSON", COORDINATE_PRECISION=5)
    size_mb = path.stat().st_size / 1e6
    print(f"    plr.geojson: {len(out)} 要素, {size_mb:.1f} MB")

    refuges_src = DATA_PROCESSED / "refuges.geojson"
    if refuges_src.exists():
        shutil.copy(refuges_src, WEB_DATA / "refuges.geojson")
        with open(refuges_src, encoding="utf-8") as f:
            n = len(json.load(f)["features"])
        print(f"    refuges.geojson: {n} 个降温点")
    else:
        print("    refuges.geojson 尚未生成（先跑 refuges 步骤）")
