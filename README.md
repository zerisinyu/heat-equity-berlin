# 柏林热浪不平等地图 / Heat Equity Berlin

一张街区级（Planungsraum，542 个规划空间）的柏林高温脆弱性地图：
分级填色显示综合脆弱性指数（暴露 × 敏感 × 缺乏应对能力），
叠加可开关的降温点图层（饮水台、公园、图书馆），点击街区可见指数拆解。

**状态：阶段 0（脚手架）。** 方法说明、数据年份、权重选择与局限声明将在阶段 8 补全。

## 复现

```bash
uv sync
make pipeline   # fetch → process → export，中间结果缓存于 data/raw
make serve      # 本地打开 http://localhost:8000
```

## 结构

- `config/indicators.yaml` — 数据源、字段映射、维度权重（所有价值判断集中于此）
- `src/` — 管线各步骤模块
- `run.py` — 编排入口
- `NOTES.md` — 抓取记录与数据怪癖

## 数据来源

全部来自柏林官方开放数据（daten.berlin.de / gdi.berlin.de），
授权 CC-BY / dl-de 系，逐图层的来源与年份见 `config/indicators.yaml` 与阶段 8 的方法说明。

## 如何不该解读这张地图（先行声明）

- 街区平均值 ≠ 个体命运：块级聚合抹掉了内部差异（生态谬误）。
- 指数权重是可质疑的价值判断，不是客观真相；权重全部公开可调。
- 措辞聚焦"高温下需要优先关照"，而非给社区贴"问题街区"标签。
