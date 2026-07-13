"""阶段 4：敏感与应对能力维度指标。

敏感：
- 人口年龄结构：优先 EWR 矩阵 CSV（单岁年龄，可算 65+/80+/0-6）；
  CSV 不可用时回退 xlsx 报告表 T2（只有 <6 和 65+，无 80+ — 记录进输出元数据）。
- MSS 2023：s1 失业、s2 单亲家庭儿童、s3 转移支付、s4 儿童贫困（属性表连接）。

应对能力：
- 行道树密度：点 sjoin 计数 / PLR 面积 [棵/km²]
- 绿地覆盖率：Grünanlagen ∩ PLR 面积 / PLR 面积
- 到最近饮水台距离：PLR 质心 → 最近 Trinkbrunnen [m]

缺失值保持 NaN。输出 data/processed/indicators.parquet。
"""

import geopandas as gpd
import pandas as pd

from common import DATA_PROCESSED, DATA_RAW

OUT = DATA_PROCESSED / "indicators.parquet"


# ---------------------------------------------------------------- 人口年龄
def population_from_csv(path) -> pd.DataFrame | None:
    """EWR 矩阵 CSV（单岁年龄列）。结构下载后核实，此处按 EWR Datenpool
    描述预期：RAUMID 8 位 + E_E00_01…E_E95_110 年龄段列。解析失败返回 None。"""
    try:
        df = pd.read_csv(path, sep=";", dtype=str)
    except Exception as e:
        print(f"    人口 CSV 解析失败：{e}")
        return None
    print(f"    人口 CSV 列样本: {list(df.columns)[:12]} … 共 {len(df.columns)} 列，{len(df)} 行")
    id_col = next((c for c in df.columns if c.upper() in ("RAUMID", "RAUM_ID", "PLR_ID")), None)
    if id_col is None:
        print("    找不到 RAUMID 列，放弃 CSV")
        return None

    # 年龄段列形如 E_E00_01（0-1 岁）… E_E95_110；下限取列名第一个数字段
    age_cols = {}
    for c in df.columns:
        parts = c.split("_")
        if len(parts) == 3 and parts[0] == "E" and parts[1].startswith("E") and parts[1][1:].isdigit():
            age_cols[c] = int(parts[1][1:])
    if not age_cols:
        print("    找不到年龄段列，放弃 CSV")
        return None

    num = df[list(age_cols)].apply(pd.to_numeric, errors="coerce")
    total = num.sum(axis=1)
    out = pd.DataFrame({
        "plr_id": df[id_col].str.zfill(8),
        "pop_total": total,
        "share_65plus": num[[c for c, lo in age_cols.items() if lo >= 65]].sum(axis=1) / total,
        "share_80plus": num[[c for c, lo in age_cols.items() if lo >= 80]].sum(axis=1) / total,
        "share_0to6": num[[c for c, lo in age_cols.items() if lo < 6]].sum(axis=1) / total,
    })
    print(f"    人口来源：EWR 矩阵 CSV（31.12.2024，含 80+）")
    return out


def population_from_xlsx(path) -> pd.DataFrame:
    """回退：SB_A01-16-00_2025h02 报告表 T2。键 = BEZ+PGR+BZR+PLR 拼 8 位。
    只有 <6 与 65+，share_80plus 缺失（NaN）。"""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb["T2"]
    rows = []
    for row in ws.iter_rows(min_row=7, values_only=True):
        keys = row[0:4]
        if any(k is None for k in keys):
            continue  # 表头/区级小计/空行
        try:
            plr_id = "".join(str(int(k)).zfill(2) for k in keys)
        except (ValueError, TypeError):
            continue
        total, under6, plus65 = row[4], row[5], row[12]
        if total is None:
            continue
        rows.append((plr_id, float(total), float(under6 or 0), float(plus65 or 0)))
    df = pd.DataFrame(rows, columns=["plr_id", "pop_total", "n_under6", "n_65plus"])
    df["share_65plus"] = df["n_65plus"] / df["pop_total"]
    df["share_0to6"] = df["n_under6"] / df["pop_total"]
    df["share_80plus"] = float("nan")
    print(f"    人口来源：报告表 xlsx T2（31.12.2025，无 80+ 细分 → NaN），{len(df)} 行")
    return df[["plr_id", "pop_total", "share_65plus", "share_80plus", "share_0to6"]]


def load_population() -> pd.DataFrame:
    csv_path = DATA_RAW / "population_age.csv"
    if csv_path.exists():
        df = population_from_csv(csv_path)
        if df is not None:
            return df
    return population_from_xlsx(DATA_RAW / "population_age.xlsx")


# ---------------------------------------------------------------- MSS
def load_mss(cfg) -> pd.DataFrame:
    fm = cfg["sources"]["mss"]["field_map"]
    gdf = gpd.read_file(DATA_RAW / "mss.geojson")
    df = pd.DataFrame({
        "plr_id": gdf[fm["plr_id"]].astype(str).str.zfill(8),
        "unemployment": pd.to_numeric(gdf[fm["unemployment"]], errors="coerce"),
        "single_parent_children": pd.to_numeric(gdf[fm["single_parent_children"]], errors="coerce"),
        "transfer_income": pd.to_numeric(gdf[fm["transfer_income"]], errors="coerce"),
        "child_poverty": pd.to_numeric(gdf[fm["child_poverty"]], errors="coerce"),
    })
    # MSS 用 -9999 标记无值（极小人口/不参与统计的 PLR）→ NaN，绝不当真值
    value_cols = df.columns.drop("plr_id")
    n_sentinel = (df[value_cols] <= -9998).sum().sum()
    if n_sentinel:
        print(f"    MSS: {n_sentinel} 个 -9999 哨兵值 → NaN")
    df[value_cols] = df[value_cols].where(df[value_cols] > -9998)
    return df


# ---------------------------------------------------------------- 应对能力
def tree_density(plr: gpd.GeoDataFrame, working: str) -> pd.Series:
    trees = gpd.read_file(DATA_RAW / "strassenbaeume.geojson")
    trees = trees.set_crs(working) if trees.crs is None else trees.to_crs(working)
    joined = gpd.sjoin(trees[["geometry"]], plr[["plr_id", "geometry"]],
                       how="inner", predicate="within")
    counts = joined.groupby("plr_id").size()
    area_km2 = plr.set_index("plr_id").geometry.area / 1e6
    dens = counts.reindex(area_km2.index).fillna(0) / area_km2
    # 这里 fillna(0) 是语义正确的：没有一棵行道树就是密度 0，不是缺失
    return dens


def green_share(plr: gpd.GeoDataFrame, working: str) -> pd.Series:
    green = gpd.read_file(DATA_RAW / "gruenanlagen.geojson")
    green = green.set_crs(working) if green.crs is None else green.to_crs(working)
    bad = ~green.geometry.is_valid
    if bad.any():
        green.loc[bad, "geometry"] = green.loc[bad, "geometry"].make_valid()
    inter = gpd.overlay(green[["geometry"]], plr[["plr_id", "geometry"]],
                        how="intersection", keep_geom_type=True)
    g_area = inter.assign(_a=inter.geometry.area).groupby("plr_id")["_a"].sum()
    plr_area = plr.set_index("plr_id").geometry.area
    return (g_area.reindex(plr_area.index).fillna(0) / plr_area).clip(upper=1.0)
    # fillna(0)：没有公共绿地相交就是覆盖 0，语义正确


def dist_to_fountain(plr: gpd.GeoDataFrame, working: str) -> pd.Series:
    fountains = gpd.read_file(DATA_RAW / "trinkbrunnen.geojson")
    fountains = fountains.set_crs(working) if fountains.crs is None else fountains.to_crs(working)
    centroids = plr.set_index("plr_id").geometry.centroid
    union = fountains.geometry.union_all()
    return centroids.distance(union)


# ---------------------------------------------------------------- run
def run(cfg: dict) -> None:
    working = cfg["crs"]["working"]
    plr = gpd.read_parquet(DATA_PROCESSED / "plr_base.parquet")
    base = plr[["plr_id"]].set_index("plr_id")

    pop = load_population().set_index("plr_id")
    matched = base.index.isin(pop.index).sum()
    print(f"    人口键匹配: {matched}/542")
    assert matched >= 540, "人口数据与 LOR 键匹配率异常，检查键构造"

    mss = load_mss(cfg).set_index("plr_id")
    print(f"    MSS 键匹配: {base.index.isin(mss.index).sum()}/542")

    print("    行道树密度 …")
    trees = tree_density(plr, working)
    print("    绿地覆盖率 …")
    green = green_share(plr, working)
    print("    到最近饮水台距离 …")
    dist = dist_to_fountain(plr, working)

    out = base.join([
        pop[["pop_total", "share_65plus", "share_80plus", "share_0to6"]],
        mss,
    ])
    out["street_tree_density"] = trees
    out["green_share"] = green
    out["dist_to_fountain"] = dist

    for col in out.columns:
        s = out[col]
        print(f"      {col}: 缺失 {s.isna().sum()}，范围 [{s.min():.3f}, {s.max():.3f}]，中位 {s.median():.3f}")

    out.reset_index().to_parquet(OUT)
    print(f"    → {OUT.name}")
