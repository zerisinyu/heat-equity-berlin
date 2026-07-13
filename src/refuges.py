"""阶段 6：降温点图层（四类）。

- fountain  饮水台（BWB，5–10 月运行；Bituma 型无障碍）
- park      公共绿地 ≥1 ha（质心作荫凉点）
- library   公共图书馆（OSM amenity=library，ODbL — 官方无此数据集）
- cool_room 官方避暑室内场所（Kühle Räume/Hitzeschutz：教堂、社区中心等，
            含开放时间与轮椅无障碍标记）

输出 data/processed/refuges.geojson（EPSG:4326，前端直用）。
"""

import geopandas as gpd
import pandas as pd

from common import DATA_PROCESSED, DATA_RAW

OUT = DATA_PROCESSED / "refuges.geojson"

MIN_PARK_HA = 1.0

COLS = ["type", "name", "detail", "accessible", "note", "season", "geometry"]


def load_fountains(cfg: dict, working: str) -> gpd.GeoDataFrame:
    fm = cfg["sources"]["trinkbrunnen"]["field_map"]
    g = gpd.read_file(DATA_RAW / "trinkbrunnen.geojson")
    g = g.set_crs(working) if g.crs is None else g.to_crs(working)
    kind = g[fm["kind"]].astype(str)
    return gpd.GeoDataFrame({
        "type": "fountain",
        "name": g[fm["location"]].astype(str),
        "detail": kind,
        # Bituma 型为无障碍饮水台，单独打标
        "accessible": kind.str.contains("bituma", case=False, na=False),
        "note": g[fm["restrictions"]].fillna("").astype(str),
        "season": "May–Oct",
    }, geometry=g.geometry)


def load_parks(cfg: dict, working: str) -> gpd.GeoDataFrame:
    fm = cfg["sources"]["gruenanlagen"]["field_map"]
    g = gpd.read_file(DATA_RAW / "gruenanlagen.geojson")
    g = g.set_crs(working) if g.crs is None else g.to_crs(working)
    bad = ~g.geometry.is_valid
    if bad.any():
        g.loc[bad, "geometry"] = g.loc[bad, "geometry"].make_valid()
    area_ha = g.geometry.area / 1e4
    g = g[area_ha >= MIN_PARK_HA]
    return gpd.GeoDataFrame({
        "type": "park",
        "name": g[fm["name"]].fillna("Grünanlage").astype(str),
        "detail": (g.geometry.area / 1e4).round(1).astype(str) + " ha",
        # 公园无"无障碍"数据，用 False 而非 NA：混入 NA 会让整列被
        # 序列化成字符串 'True'/'False'，前端布尔判断悄悄失效
        "accessible": False,
        "note": "",
        "season": "Year-round",
    }, geometry=g.geometry.representative_point())


def load_libraries(working: str) -> gpd.GeoDataFrame:
    g = gpd.read_file(DATA_RAW / "bibliotheken_osm.geojson")  # OSM → 4326
    g = g.to_crs(working)
    wheel = g.get("wheelchair", pd.Series("", index=g.index)).fillna("")
    return gpd.GeoDataFrame({
        "type": "library",
        "name": g.get("name", pd.Series(index=g.index)).fillna("Bibliothek").astype(str),
        "detail": "Public library",
        "accessible": wheel.str.lower().eq("yes"),
        "note": g.get("opening_hours", pd.Series("", index=g.index)).fillna("").astype(str),
        "season": "Year-round",
    }, geometry=g.geometry)


def load_cool_rooms(cfg: dict, working: str) -> gpd.GeoDataFrame:
    fm = cfg["sources"]["kuehle_raeume"]["field_map"]
    g = gpd.read_file(DATA_RAW / "kuehle_raeume.geojson")
    g = g.set_crs(working) if g.crs is None else g.to_crs(working)
    wheel = g[fm["wheelchair"]].fillna("").astype(str).str.lower()
    hours = g[fm["hours"]].fillna("").astype(str)
    note = g[fm["note"]].fillna("").astype(str)
    return gpd.GeoDataFrame({
        "type": "cool_room",
        "name": g[fm["name"]].astype(str),
        "detail": g[fm["address"]].fillna("").astype(str),
        # "nicht rollstuhlgerecht" 也含 "rollstuhlgerecht"，须排除否定式
        "accessible": wheel.str.contains("rollstuhlgerecht") & ~wheel.str.contains("nicht"),
        "note": (hours + ((" · " + note).where(note != "", ""))).str.strip(" ·"),
        "season": "Heat days",
    }, geometry=g.geometry)


def run(cfg: dict) -> None:
    working = cfg["crs"]["working"]
    output = cfg["crs"]["output"]

    parts = [load_fountains(cfg, working), load_parks(cfg, working)]
    if (DATA_RAW / "bibliotheken_osm.geojson").exists():
        parts.append(load_libraries(working))
    else:
        print("    图书馆缓存缺席，跳过（见 NOTES）")
    if (DATA_RAW / "kuehle_raeume.geojson").exists():
        parts.append(load_cool_rooms(cfg, working))

    for p in parts:
        t = p["type"].iloc[0]
        print(f"    {t}: {len(p)}（无障碍 {int(p['accessible'].sum())}）")

    refuges = pd.concat([p[COLS] for p in parts], ignore_index=True)
    refuges = gpd.GeoDataFrame(refuges, geometry="geometry", crs=working).to_crs(output)
    refuges.to_file(OUT, driver="GeoJSON")
    print(f"    → {OUT.name}（EPSG:4326，共 {len(refuges)} 点）")
