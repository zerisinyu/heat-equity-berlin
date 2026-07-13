# 柏林热浪不平等地图 / Heat Equity Berlin

一张街区级（Planungsraum，542 个规划空间）的柏林高温脆弱性地图：
分级填色显示综合脆弱性指数，叠加可开关的降温点图层（饮水台、公园绿地），
点击任一街区可见指数拆解——是因为太热、住得脆弱，还是无处可躲。

这张图想回答两个问题：**哪里的人在高温下最需要优先关照**，以及
**他们最近的降温点在哪**。它的目标用户是社区照护者、邻里互助网络和
基层机构——热浪来临前就知道该去敲哪几扇门。

## 复现

```bash
uv sync
make pipeline   # fetch → process → export，全自动，原始数据缓存于 data/raw
make serve      # 打开 http://localhost:8000
```

单步调试：`uv run python run.py <step>`，step ∈ fetch / geo_base / exposure /
indicators / index / refuges / export。

## 指数如何构造

公共卫生地理学的标准框架把热脆弱性拆成三个维度：

| 维度 | 含义 | 底层指标（数据年份） |
|---|---|---|
| 暴露 | 这里有多热 | PET 14:00、UTCI 14:00、夜间降温幅度（Klimaanalysekarten 2022，Siedlungsflächen 街区块面积加权聚合） |
| 敏感 | 谁更容易被击垮 | 65+ 占比、0–6 岁占比（2025）；转移支付、儿童贫困、单亲家庭儿童（MSS 2023） |
| 缺乏应对能力 | 能不能躲 | 行道树密度、公共绿地覆盖率、到最近饮水台距离（2025 现势） |

合成方法：每个底层指标在 542 个 Planungsraum 间做**百分位归一化**到 [0,1]
（1 = 最脆弱方向），维度内加权平均得维度分，三维度加权合成总指数
（默认等权）。全部权重在 [config/indicators.yaml](config/indicators.yaml)，
改配置即可重算。

**缺失值纪律**：缺失保持 NaN，权重在非缺失指标间重归一，绝不填零。
三个维度分不齐全、或常住人口 < 100 的街区不参与排名（地图上显示为
"数据不足"）——货运场站和森林没有"脆弱性"可言。

## 权重是价值判断，不是客观事实

默认三维度等权是一种**取舍**而非真相。我们跑了 4 组权重情景
（等权 / 暴露加重 / 敏感加重 / 应对加重）做敏感性检验：前 20 名重叠
15–17/20，**11 个街区在全部情景下都进入最需关照的前 20**（名单见
[NOTES.md](NOTES.md)）。地图上可勾选单独标出这批街区——只有这个
子集的结论是对权重选择稳健的，其余排名请当作参考而非定论。

## 如何不该解读这张地图

- **街区平均值 ≠ 个体命运**。气候块聚合到 Planungsraum 抹掉了内部差异，
  一个街区的平均 PET 掩盖了里面最热的那栋顶层老楼（生态谬误）。
- **这不是"问题街区"名单**。指数标示的是高温下需要优先送达帮助的地方，
  不是社区的缺陷评分。任何把它用于房价、保险或污名化的解读都是误用。
- **数据年份不齐**：气候 2022、社会监测 2023、人口 2025、绿化 2025。
  它们不是同一时点的快照。
- **已知缺口**：80+ 高龄占比因统计局网站改版暂缺（用 65+ 代替，权重
  已调整）；空调普及率无直接数据，未纳入；室内避暑点（图书馆等）
  暂未纳入降温点图层。详见 [NOTES.md](NOTES.md) 待办。
- 指数构造中的每一步（归一化方式、权重、最低人口门槛）都可质疑、
  可复算——这正是把它全部开源的原因。

## 数据来源与授权

全部来自柏林官方开放数据（[gdi.berlin.de](https://gdi.berlin.de) WFS /
[daten.berlin.de](https://daten.berlin.de)），逐图层端点、字段与年份见
[config/indicators.yaml](config/indicators.yaml) 与 [NOTES.md](NOTES.md)：

- LOR Planungsräume 2021 — CC-BY-3.0-DE
- Klimaanalysekarten 2022（Umweltatlas）— dl-de/by-2-0
- Monitoring Soziale Stadtentwicklung 2023 — dl-de/by-2-0
- Baumbestand（Straßenbäume）、Grünanlagen — dl-de/by-2-0
- Trinkwasserbrunnen（Berliner Wasserbetriebe）— dl-de/zero-2-0
- 人口：Amt für Statistik Berlin-Brandenburg，SB A I 16 hj（31.12.2025）— CC-BY

基础底图 © OpenStreetMap 贡献者 © CARTO。

## 结构

```
src/            管线各步骤（fetch → geo_base → exposure → indicators → index → refuges → export）
config/         数据源、字段映射、全部权重
web/            单页地图（MapLibre GL JS）
data/raw        原始抓取缓存（不进 git）
data/processed  中间产物与检查图
NOTES.md        抓取记录、数据怪癖、敏感性检验结论
```
