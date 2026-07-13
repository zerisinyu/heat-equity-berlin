# NOTES — 抓取记录、数据怪癖、待办

## 待办
- [ ] **share_80plus 暂缺（已决策：MVP 弃用）**。EWR 矩阵 CSV（单岁年龄）在
      统计局 2026 网站改版（Scrivito SPA）后不可达：`/opendata/*.csv` 对任意
      路径返回 SPA 首页；Wayback 2025-03 快照本身就是改版后的软 404。
      现用 `population_age.xlsx`（SB_A01-16-00_2025h02，T2：<6 与 65+，
      31.12.2025 时点），敏感维度权重已重分配（65+ 0.30）。
      `indicators.py:population_from_csv` 已就位——若 CSV 恢复，放进
      `data/raw/population_age.csv` 即自动优先使用并恢复 80+。
- [ ] 图书馆：无官方 WFS（2026-07 检索确认）。MVP 降温点 = 饮水台 + 绿地；
      可选阶段用 OSM Overpass 补图书馆（amenity=library，注意 ODbL 授权注明）。
- [ ] 空调普及率无直接数据 — MVP 留空，README 注明。

## 数据源核对记录（2026-07-13，全部经 GetCapabilities + resultType=hits 验证）

| key | 服务/图层 | 要素数 | CRS | 关键字段 | 年份 |
|---|---|---|---|---|---|
| lor_planungsraum | lor_2021 / a_lor_plr_2021 | 542 ✓ | 25833 | plr_id, plr_name | 2021 |
| klima_pet | ua_klimaanalyse_2022 / pa_ua_pet_siedlg_2022 | 16217 | 25833 | schl5, pet14h | 2022 |
| klima_utci | ua_klimaanalyse_2022 / ra_ua_utci_siedlg_2022 | 16217 | 25833 | schl5, utci14h | 2022 |
| klima_abkuehl | ua_klimaanalyse_2022 / na_ua_abkuehl_siedlg_2022 | 16217 | 25833 | schl5, abkuehlmea | 2022 |
| mss | mss_2023 / mss2023_indexind_542 | 542 ✓ | 25833 | plr_id, s1..s4 | 2023 |
| strassenbaeume | baumbestand / strassenbaeume | 434765 ✓ | 25833 | (点位, bezirk) | 2025 |
| gruenanlagen | gruenanlagen / gruenanlagen | 2563 ✓ | 25833 | namenr, katasterfl | 2025 |
| trinkbrunnen | trinkwasserbrunnen / trinkwasserbrunnen | 242 ✓ | 25833 | trinkbrunnenart, standort | 2025 |

### 怪癖与决策
- **气候图层按用地类型分三组**（Siedlung / Verkehr / Grün-Freiflächen）。暴露聚合
  只用 `_siedlg_`（人住在居住区块）。纯绿地/森林 PLR 可能无 Siedlung 块 → 暴露缺失，
  保持 NaN 不填零。
- **MSS 字段**：s1–s4 = Status（比例 %），d1–d4 = Dynamik（两年变化）。排序按
  2023 报告：s1 失业、s2 单亲家庭儿童（2023 新增，替代长期失业）、s3 转移支付、
  s4 儿童贫困（U15 SGB II）。已用数值范围抽样验证（s2≈20-24% 符合单亲儿童占比，
  不可能是长期失业率）。
- **Pflege-Kernindikatoren 弃用**：只有 Bezirk 级粒度（12 区），对 542 个 PLR
  无增量信息；首要风险人群由 65+/80+ 占比覆盖。
- **Baumbestand 有两层**：strassenbaeume（43.5 万）+ anlagenbaeume（52.8 万，
  公园树）。MVP 按规格只用行道树；anlagenbaeume 可作后续扩展。
- **WFS 翻页**：gdi.berlin.de 接受 COUNT=10000 + STARTINDEX，未见截断；
  抓完与 numberMatched 核对一致。
- **饮水台字段** `trinkbrunnenart` 含型号（Bituma = 无障碍型），`einschraenkungen`
  含限制说明；运行季节 5–10 月。
- **年份不齐**：气候 2022、MSS 2023、人口 2024（Wayback）/2025（xlsx）、
  树木/绿地/饮水台 2025 现势。README 方法说明需逐层注明。

## 已知约束
- FIS-Broker / gdi.berlin.de 的 WFS 不能直接喂前端，须离线转 GeoJSON
- 缺失值策略：保留 NaN，归一化时排除，绝不静默填零

## 敏感性检验结论（阶段 5，2026-07-13）

敏感性检验（各情景最脆弱前 20 名）：
  equal: 与 equal 重叠 20/20
  exposure_heavy: 与 equal 重叠 17/20
  sensitivity_heavy: 与 equal 重叠 17/20
  capacity_heavy: 与 equal 重叠 16/20
  全部 4 组情景交集（稳定高危）: 11 个
    - 05200421 Spandauer Straße
    - 07501133 Fritz-Werner-Straße
    - 07601236 Marienfelder Allee Nordwest
    - 07601238 Marienfelde Nordost
    - 07601443 Töpchiner Weg
    - 08200833 Buckow Ost
    - 08401138 Goldhähnchenweg
    - 08401139 Vogelviertel Süd
    - 11200410 Malchower Weg
    - 11200411 Hauptstraße
    - 12200307 Reinickes Hof
解读：四组权重情景下前 20 名重叠 15–17/20，11 个 PLR 进入全情景交集，
结论对权重选择相对稳健。稳定高危街区集中在外环南部/东部（Marienfelde、
Buckow、Rudow、Spandau、Hohenschönhausen 边缘），共同特征是 PET 高
（开阔无遮荫建成区）、老龄占比高、行道树密度低 —— 而非市中心贫困街区，
这与"热浪脆弱 ≠ 社会脆弱地图的简单复刻"的预期一致。
无人/数据不足 PLR（人口<100 或缺维度）不参与排名，共 6 个。
