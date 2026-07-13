#!/usr/bin/env python3
"""管线编排：fetch → geo_base → exposure → indicators → index → refuges → export.

各阶段模块逐步填实；尚未实现的步骤打印 SKIP 而不是报错，
保证管线任何时候都能从头跑到底。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from common import load_config  # noqa: E402

STEPS = [
    ("fetch", "抓取与缓存原始数据"),
    ("geo_base", "LOR Planungsraum 地理底座"),
    ("exposure", "暴露维度（气候块聚合）"),
    ("indicators", "敏感与应对能力指标"),
    ("index", "归一化与加权合成指数"),
    ("refuges", "降温点图层"),
    ("export", "导出前端 GeoJSON"),
]


def main() -> int:
    cfg = load_config()
    print(f"配置加载完成：{len(cfg['sources'])} 个数据源，"
          f"{sum(len(v) for v in cfg['indicators'].values())} 个底层指标\n")

    only = sys.argv[1] if len(sys.argv) > 1 else None

    for module_name, desc in STEPS:
        if only and module_name != only:
            continue
        print(f"=== {module_name}: {desc} ===")
        try:
            module = __import__(module_name)
        except ImportError:
            print("    SKIP（模块尚未创建）\n")
            continue
        if not hasattr(module, "run"):
            print("    SKIP（尚未实现 run()）\n")
            continue
        module.run(cfg)
        print()

    print("管线结束。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
