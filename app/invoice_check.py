"""供应商发票号码批次查重核心（纯函数，不依赖数据库）。

规则（固定且可复算）：

1. 每个字段先做 **Unicode NFKC 规范化**，再去除首尾空白，最后按大小写折叠
   （``str.casefold()``），得到用于比较的规范化值。
2. 仅在 **同一供应商**（按规范化后的供应商编号分组）内识别重复：
   规范化后相同的发票号码出现 2 次及以上即构成一个重复组。
3. 校验失败抛 ``ValueError``（API 层统一映射为 422）：

   * 原始发票号码为空（去除首尾空白后为空）；
   * 原始发票号码超过 100 个 Unicode 字符（按原始值计）；
   * 供应商编号为空（去除首尾空白后为空）。

4. 重复组按其在输入中的 **首次出现顺序** 返回；组内位置（1 起始）按输入
   顺序升序，原始值保持提交时的原样；未重复的号码不出现在结果中。
"""

from __future__ import annotations

import unicodedata
from typing import Any

MAX_INVOICE_NUMBER_CHARS = 100


def normalize_field(value: str) -> str:
    """字段规范化：Unicode NFKC -> 去除首尾空白 -> 大小写折叠。"""

    return unicodedata.normalize("NFKC", value).strip().casefold()


def find_duplicate_invoice_numbers(
    items: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    """在 ``(供应商编号, 发票号码)`` 批次中识别同一供应商内的重复号码。

    返回重复组列表，每组::

        {
            "supplier_code": <规范化供应商编号>,
            "invoice_number": <规范化发票号码>,
            "occurrences": [
                {"position": <1 起始的输入位置>, "raw_value": <原始发票号码>},
                ...
            ],
        }

    组顺序为各组在输入中的首次出现顺序；未重复号码不列出。
    任一记录校验失败抛 ``ValueError``（含 1 起始位置，API 层映射为 422）。
    """

    # 组键：(规范化供应商编号, 规范化发票号码)；dict 保持插入顺序，
    # 即各组按首次出现顺序排列
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for position, (supplier_code, invoice_number) in enumerate(items, start=1):
        if not supplier_code.strip():
            raise ValueError(f"第 {position} 条记录的供应商编号为空")
        if not invoice_number.strip():
            raise ValueError(f"第 {position} 条记录的发票号码为空")
        if len(invoice_number) > MAX_INVOICE_NUMBER_CHARS:
            raise ValueError(
                f"第 {position} 条记录的发票号码超过 "
                f"{MAX_INVOICE_NUMBER_CHARS} 个 Unicode 字符"
                f"（实际 {len(invoice_number)} 个）"
            )

        key = (normalize_field(supplier_code), normalize_field(invoice_number))
        group = groups.get(key)
        if group is None:
            group = {
                "supplier_code": key[0],
                "invoice_number": key[1],
                "occurrences": [],
            }
            groups[key] = group
        group["occurrences"].append(
            {"position": position, "raw_value": invoice_number}
        )

    return [g for g in groups.values() if len(g["occurrences"]) > 1]
