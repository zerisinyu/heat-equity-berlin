"""平滑热力表面：把 PLR 指数栅格化并做归一化高斯模糊，输出前端叠加用 PNG。

为什么不用逐多边形填色：街区边界处颜色跳变生硬。这里生成
"柔和热力图"视觉——但值仍严格来自各 PLR 的指数，模糊只做视觉过渡
（sigma ≈ 300 m），不是核密度估计，不改变数据故事。

边界处理用归一化卷积：blur(value·mask) / blur(mask)，再用模糊后的
mask 当 alpha，城市边缘自然淡出。未排名 PLR（数据不足）不烧录 → 透明。
"""

import json

import numpy as np
from scipy.ndimage import gaussian_filter

from common import DATA_PROCESSED, WEB_DIR

WEB_DATA = WEB_DIR / "data"

METRICS = ["heat_vulnerability", "dim_exposure", "dim_sensitivity",
           "dim_adaptive_capacity_lack"]

RES = 100      # m / 像素
SIGMA = 3.0    # 模糊半径（像素）≈ 300 m

# 日落-莓果色带（浅→深，明度单调下降）
RAMP = ["#FEF6EC", "#FBCB97", "#F58B76", "#C94F7C", "#7D2E68"]


def _hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def colormap(t: np.ndarray) -> np.ndarray:
    """t ∈ [0,1] → RGB，线性插值 RAMP。"""
    stops = np.array([_hex2rgb(c) for c in RAMP], dtype=float)
    pos = np.linspace(0, 1, len(stops))
    r = np.interp(t, pos, stops[:, 0])
    g = np.interp(t, pos, stops[:, 1])
    b = np.interp(t, pos, stops[:, 2])
    return np.dstack([r, g, b]).astype(np.uint8)


def run(cfg: dict) -> None:
    import geopandas as gpd
    import pandas as pd
    from PIL import Image
    from pyproj import Transformer
    from rasterio.features import rasterize
    from rasterio.transform import from_origin

    WEB_DATA.mkdir(exist_ok=True)
    plr = gpd.read_parquet(DATA_PROCESSED / "plr_base.parquet")
    idx = pd.read_parquet(DATA_PROCESSED / "plr_index.parquet")
    merged = plr.merge(idx.drop(columns=["plr_name"], errors="ignore"), on="plr_id")
    # 只画参与排名的 PLR（数据不足的保持透明）
    merged = merged[merged["heat_vulnerability"].notna()]

    xmin, ymin, xmax, ymax = plr.total_bounds
    w = int(np.ceil((xmax - xmin) / RES))
    h = int(np.ceil((ymax - ymin) / RES))
    transform = from_origin(xmin, ymax, RES, RES)

    mask = rasterize(
        [(geom, 1.0) for geom in merged.geometry],
        out_shape=(h, w), transform=transform, fill=0.0, dtype="float64")
    m_blur = gaussian_filter(mask, SIGMA)

    # 四个角 25833 → 4326（供 MapLibre image source）
    t = Transformer.from_crs(cfg["crs"]["working"], cfg["crs"]["output"], always_xy=True)
    corners = [t.transform(x, y) for x, y in
               [(xmin, ymax), (xmax, ymax), (xmax, ymin), (xmin, ymin)]]

    meta = {"corners": [[round(lng, 6), round(lat, 6)] for lng, lat in corners],
            "metrics": {}}

    for metric in METRICS:
        vals = rasterize(
            [(geom, v) for geom, v in zip(merged.geometry, merged[metric].fillna(0))],
            out_shape=(h, w), transform=transform, fill=0.0, dtype="float64")
        v_blur = gaussian_filter(vals, SIGMA)
        surface = np.divide(v_blur, m_blur, out=np.zeros_like(v_blur),
                            where=m_blur > 1e-3)

        # 指数已是 0-1 百分位，取 2-98 分位拉伸对比度
        inside = surface[m_blur > 0.2]
        lo, hi = np.percentile(inside, [2, 98])
        norm = np.clip((surface - lo) / (hi - lo), 0, 1)

        rgb = colormap(norm)
        alpha = (np.clip(m_blur, 0, 1) ** 0.8 * 255).astype(np.uint8)
        rgba = np.dstack([rgb, alpha])

        out = WEB_DATA / f"surface_{metric}.png"
        Image.fromarray(rgba, "RGBA").save(out, optimize=True)
        meta["metrics"][metric] = {"lo": round(float(lo), 3), "hi": round(float(hi), 3)}
        print(f"    {metric}: {w}x{h}px, {out.stat().st_size // 1024} KB")

    (WEB_DATA / "surfaces.json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"    → surfaces.json（角点 + 值域）")
