# NOTES — 抓取记录、数据怪癖、待办

## 待办
- [ ] 阶段 1：逐个数据源请求 GetCapabilities，填实 config 中 verified: false 的条目
- [ ] Pflege-Kernindikatoren 与人口 CSV 的下载地址待检索
- [ ] 空调普及率无直接数据 — MVP 留空，README 注明

## 数据源核对记录
（阶段 1 起，每个数据源抓通后在此记录：端点、图层名、要素数、坐标系、字段、年份、怪癖）

## 已知约束
- FIS-Broker / gdi.berlin.de 的 WFS 不能直接喂前端，须离线转 GeoJSON
- WFS 分页：单次 GetFeature 可能被截断，需按 startIndex 翻页并核对总数
- 缺失值策略：保留 NaN，归一化时排除，绝不静默填零
