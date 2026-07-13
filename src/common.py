"""共享工具：配置加载、路径、日志式打印。"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
CONFIG_PATH = ROOT / "config" / "indicators.yaml"
WEB_DIR = ROOT / "web"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def inspect_gdf(gdf, name: str, n: int = 3) -> None:
    """打印要素数量、字段列表、坐标系和前几行 — 阶段 1 的人工核对入口。"""
    print(f"--- {name} ---")
    print(f"  要素数: {len(gdf)}")
    print(f"  CRS: {gdf.crs}")
    print(f"  字段: {list(gdf.columns)}")
    print(gdf.head(n).to_string())
    print()
