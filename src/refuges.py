"""阶段 6：降温点图层。

- 饮水台（Trinkbrunnen）：类型、无障碍标记（Bituma 型）、运行季节 5–10 月
- 公共绿地（Grünanlagen）：取质心作"荫凉点"，附面积；只保留 ≥1 ha 的
  （太小的街角绿地谈不上避暑）
输出 data/processed/refuges.geojson（EPSG:4326，前端直用）。
"""

import geopandas as gpd
import pandas as pd

from common import DATA_PROCESSED, DATA_RAW

OUT = DATA_PROCESSED / "refuges.geojson"

MIN_PARK_HA = 1.0


def load_fountains(cfg: dict, working: str) -> gpd.GeoDataFrame:
    fm = cfg["sources"]["trinkbrunnen"]["field_map"]
    g = gpd.read_file(DATA_RAW / "trinkbrunnen.geojson")
    g = g.set_crs(working) if g.crs is None else g.to_crs(working)
    kind = g[fm["kind"]].astype(str)
    out = gpd.GeoDataFrame({
        "type": "fountain",
        "name": g[fm["location"]].astype(str),
        "detail": kind,
        # Bituma 型为无障碍饮水台，单独打标
        "accessible": kind.str.contains("bituma", case=False, na=False),
        "note": g[fm["restrictions"]].fillna("").astype(str),
        "season": "5–10 月",
    }, geometry=g.geometry)
    return out


def load_parks(cfg: dict, working: str) -> gpd.GeoDataFrame:
    fm = cfg["sources"]["gruenanlagen"]["field_map"]
    g = gpd.read_file(DATA_RAW / "gruenanlagen.geojson")
    g = g.set_crs(working) if g.crs is None else g.to_crs(working)
    bad = ~g.geometry.is_valid
    if bad.any():
        g.loc[bad, "geometry"] = g.loc[bad, "geometry"].make_valid()
    area_ha = g.geometry.area / 1e4
    g = g[area_ha >= MIN_PARK_HA]
    out = gpd.GeoDataFrame({
        "type": "park",
        "name": g[fm["name"]].fillna("Grünanlage").astype(str),
        "detail": (g.geometry.area / 1e4).round(1).astype(str) + " ha",
        # 公园无"无障碍"数据，用 False 而非 NA：混入 NA 会让整列被
        # 序列化成字符串 'True'/'False'，前端布尔判断悄悄失效
        "accessible": False,
        "note": "",
        "season": "全年",
    }, geometry=g.geometry.representative_point())
    return out


def run(cfg: dict) -> None:
    working = cfg["crs"]["working"]
    output = cfg["crs"]["output"]

    fountains = load_fountains(cfg, working)
    parks = load_parks(cfg, working)
    print(f"    饮水台 {len(fountains)}（无障碍 {int(fountains['accessible'].sum())}），"
          f"公园（≥{MIN_PARK_HA} ha）{len(parks)}")

    refuges = pd.concat([fountains, parks], ignore_index=True)
    refuges = gpd.GeoDataFrame(refuges, geometry="geometry", crs=working).to_crs(output)
    refuges.to_file(OUT, driver="GeoJSON")
    print(f"    → {OUT.name}（EPSG:4326）")
