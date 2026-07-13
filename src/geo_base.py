"""阶段 2：LOR Planungsraum 地理底座。

载入 542 个规划空间，统一 EPSG:25833，校验并修复无效几何，
确认 plr_id 唯一、无缺失。输出 data/processed/plr_base.parquet。
"""

import geopandas as gpd

from common import DATA_PROCESSED, DATA_RAW, inspect_gdf

OUT = DATA_PROCESSED / "plr_base.parquet"


def load_plr(cfg: dict) -> gpd.GeoDataFrame:
    src = cfg["sources"]["lor_planungsraum"]
    gdf = gpd.read_file(DATA_RAW / "lor_planungsraum.geojson")
    working = cfg["crs"]["working"]
    if gdf.crs is None:
        gdf = gdf.set_crs(working)  # gdi.berlin.de GeoJSON 自带 25833 声明，保险起见
    gdf = gdf.to_crs(working)

    id_col = src["field_map"]["id"]
    name_col = src["field_map"]["name"]
    gdf = gdf[[id_col, name_col, "geometry"]].rename(
        columns={id_col: "plr_id", name_col: "plr_name"})
    gdf["plr_id"] = gdf["plr_id"].astype(str).str.zfill(8)

    # 几何校验与修复
    invalid = ~gdf.geometry.is_valid
    if invalid.any():
        print(f"    修复 {invalid.sum()} 个无效几何（make_valid）")
        gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].make_valid()

    expected = src["expected_count"]
    assert len(gdf) == expected, f"期望 {expected} 个 PLR，实际 {len(gdf)}"
    assert gdf["plr_id"].is_unique, "plr_id 有重复"
    assert gdf.geometry.notna().all() and (~gdf.geometry.is_empty).all()
    return gdf


def run(cfg: dict) -> None:
    gdf = load_plr(cfg)
    inspect_gdf(gdf, "Planungsraum 底座")
    total_km2 = gdf.geometry.area.sum() / 1e6
    print(f"    总面积 {total_km2:.0f} km²（柏林约 891 km²）")
    gdf.to_parquet(OUT)
    print(f"    → {OUT.relative_to(OUT.parent.parent.parent)}")
