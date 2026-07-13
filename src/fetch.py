"""阶段 1：抓取与缓存。

WFS 抓取纪律：
- 按 startIndex 翻页（gdi.berlin.de 单次上限保守取 10000），抓完与
  resultType=hits 的 numberMatched 核对，数量对不上就报错，绝不静默截断。
- 原样存 data/raw/<key>.geojson，已存在且数量正确则跳过（缓存）。
"""

import json
from urllib.parse import urlencode

import requests

from common import DATA_RAW

PAGE_SIZE = 10000
TIMEOUT = 300


def _wfs_url(base: str, service: str, params: dict) -> str:
    return f"{base}/{service}?{urlencode(params)}"


def wfs_hits(base: str, service: str, layer: str) -> int:
    url = _wfs_url(base, service, {
        "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
        "TYPENAMES": layer, "RESULTTYPE": "hits",
    })
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    import re
    m = re.search(r'numberMatched="(\d+)"', r.text)
    if not m:
        raise RuntimeError(f"{layer}: hits 响应里找不到 numberMatched")
    return int(m.group(1))


def fetch_wfs_layer(base: str, service: str, layer: str,
                    properties: list | None = None) -> dict:
    """翻页抓全一个 WFS 图层，返回合并后的 GeoJSON FeatureCollection。"""
    total = wfs_hits(base, service, layer)
    features, crs = [], None
    start = 0
    while start < total:
        params = {
            "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
            "TYPENAMES": layer, "OUTPUTFORMAT": "application/json",
            "COUNT": PAGE_SIZE, "STARTINDEX": start,
        }
        if properties:
            # 注意：PROPERTYNAME 必须包含几何字段（geom），否则返回空几何
            params["PROPERTYNAME"] = ",".join(properties)
        page = None
        for attempt in range(4):
            try:
                r = requests.get(_wfs_url(base, service, params), timeout=TIMEOUT)
                r.raise_for_status()
                page = r.json()
                break
            except (requests.RequestException, ValueError) as e:
                if attempt == 3:
                    raise
                wait = 10 * (attempt + 1)
                print(f"    {layer}@{start}: {type(e).__name__}，{wait}s 后重试")
                import time
                time.sleep(wait)
        features.extend(page["features"])
        crs = crs or page.get("crs")
        got = len(page["features"])
        print(f"    {layer}: {start + got}/{total}")
        if got == 0:
            raise RuntimeError(f"{layer}: 翻页在 {start} 处返回空页，提前中断")
        start += got

    if len(features) != total:
        raise RuntimeError(f"{layer}: 抓到 {len(features)}，期望 {total} — 不接受截断")
    if not any(f.get("geometry") for f in features[:5]):
        raise RuntimeError(f"{layer}: 要素几何为空 — PROPERTYNAME 是否漏了 geom？")
    if crs is None:
        # 用 PROPERTYNAME 时响应可能不带 crs 声明；所有图层已经
        # GetCapabilities 验证为 25833，显式补上，避免被误读成 4326
        crs = {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::25833"}}
    return {"type": "FeatureCollection", "crs": crs, "features": features}


def fetch_csv(url: str, out_path) -> None:
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    out_path.write_bytes(r.content)


def run(cfg: dict) -> None:
    base = cfg["wfs_base"]
    for key, src in cfg["sources"].items():
        if not src.get("verified"):
            print(f"  {key}: SKIP（未验证）")
            continue

        if src["type"] == "wfs":
            out = DATA_RAW / f"{key}.geojson"
            expected = src.get("expected_count")
            if out.exists():
                with open(out, encoding="utf-8") as f:
                    cached = json.load(f)
                if expected is None or len(cached["features"]) == expected:
                    print(f"  {key}: 缓存命中（{len(cached['features'])} 要素）")
                    continue
                print(f"  {key}: 缓存数量不符，重抓")
            print(f"  {key}: 抓取 {src['layer']} …")
            fc = fetch_wfs_layer(base, src["service"], src["layer"],
                                 properties=src.get("properties"))
            with open(out, "w", encoding="utf-8") as f:
                json.dump(fc, f, ensure_ascii=False)
            print(f"  {key}: 已缓存 {len(fc['features'])} 要素 → {out.name}")

        elif src["type"] == "csv":
            out = DATA_RAW / f"{key}.csv"
            if out.exists():
                print(f"  {key}: 缓存命中（{out.stat().st_size} bytes）")
                continue
            print(f"  {key}: 下载 {src['url']} …")
            fetch_csv(src["url"], out)
            print(f"  {key}: 已缓存 → {out.name}")
