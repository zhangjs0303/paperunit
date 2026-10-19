#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministically generate rt1_volume/events.jsonl (offline red-team toy log).

Strict-compatible with the draft state graph: after a reject, the producer
submits a revised event (disputed -> produce) and the revision is verified.
Only writes inside rt1_volume/.  Does not touch score.py / baseline / RULES.
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "events.jsonl"
M = ["A", "B", "C", "D"]
NEXT = {m: M[(i + 1) % 4] for i, m in enumerate(M)}
NEXT2 = {m: M[(i + 2) % 4] for i, m in enumerate(M)}
evs: list[dict] = []


def add(**kw):
    evs.append(kw)


# ---------------------------------------------------------------- round 1
add(round=1, id="p1", op="propose", actor="A", task="Q1",
    acceptance="逐项打勾：能打开、能看到 4、能保存", note="H1")

contents1 = [
    "检查 2+2=4",
    "把变量名 typo 改掉",
    "确认文件能打开",
    "重跑一遍，结果一样",
    "把 tab 换成空格",
    "检查拼写",
    "确认没有多余空行",
    "把日期格式统一",
    "检查引用编号连续",
    "确认输出是 4",
    "把注释改成中文",
    "x",
]
evidence1 = [
    "看了一遍，结果一致，通过",
    "拼写已核对，改对了，通过",
    "文件能打开，内容也在",
    "重跑了一遍，输出一致",
    "空格已经统一，检查通过",
    "拼写检查没问题，通过",
    "确认没有多余空行，通过",
    "日期格式已统一，一致",
    "引用编号连续，没有跳号",
    "照着重算一遍，仍是 4",
    "注释已经改成中文，通过",
    "按同样步骤复现，得到 4",
]
prods1 = []
for j in range(12):
    eid = f"e{j+1:02d}"
    actor = M[j % 4]
    prods1.append((eid, actor))
    add(round=1, id=eid, op="produce", actor=actor, task="Q1",
        content=contents1[j], p=1.0, q=1.0, human_share=0.0, ai_share=1.0,
        version=1, revises=None, note="H1")

for j, (eid, actor) in enumerate(prods1):
    verifier = NEXT[actor]
    mode = "reproduce" if eid in ("e10", "e12") else "check"
    add(round=1, id=f"v{j+1:02d}", op="verify", actor=verifier, target=eid,
        decision="accept", v=1.0, mode=mode, evidence=evidence1[j], note="H1")

add(round=1, id="m01", op="merge", actor="C", target="e01",
    own_words="我们假设 2+2=4 这个检查足以作为验收证据；证据是 A 提交后 B 独立看了一遍并给出通过；局限是只覆盖一个算术例子，不能说明脚本整体正确。",
    note="H1")
add(round=1, id="m02", op="merge", actor="D", target="e02",
    own_words="假设变量名 typo 修正可以通过肉眼检查确认；证据是 B 提交、C 复核拼写；局限是没有运行测试，只检查了命名，不能证明代码可执行。",
    note="H1")
add(round=1, id="m12", op="merge", actor="B", target="e12",
    own_words="假设 x 就是全部产出；证据是 D 用 reproduce 模式复核一次并说通过；局限是没有任何可执行内容，也没有科学结论，只用于形式流水线。",
    note="H1")
add(round=1, id="r1", op="retrospect", actor="A", H=0.01, W=0, U=0, G=0, F=0,
    false_checks={}, notes="本轮只做形式检查，没有科学内容", note="H5")

# ---------------------------------------------------------------- round 2
# strict path: produce e -> reject (disputed) -> produce e' (revises e)
# -> verify e' accept.  e' is the only event counted in V; e contributes F.
add(round=2, id="p2", op="propose", actor="D", task="Q2",
    acceptance="逐条确认：文件在、输出 4、拼写对", note="H2")

contents2 = [
    "检查 2+2=4（第二轮）",
    "把 typo 改掉（第二轮）",
    "确认文件存在",
    "确认 4 还是 4",
    "统一空格（第二轮）",
    "检查编号（第二轮）",
    "确认输出（第二轮）",
    "改注释（第二轮）",
    "检查拼写（第二轮）",
    "确认能打开",
    "重跑（第二轮）",
    "y",
]
rejects = [
    "第一次看觉得数据不对，先退回",
    "核对时发现一处不一致，退回复查",
    "初步检查没通过，先退回重看",
]
accepts = [
    "再看一遍，确认没问题，通过",
    "复查后一致，可以接受",
    "第二次检查通过，记录在此",
]
prods2 = []
for j in range(12):
    eid = f"e{j+13:02d}"
    actor = M[j % 4]
    prods2.append((eid, actor))
    add(round=2, id=eid, op="produce", actor=actor, task="Q2",
        content=contents2[j], p=1.0, q=1.0, human_share=0.0, ai_share=1.0,
        version=1, revises=None, note="H2")

for j, (eid, actor) in enumerate(prods2):
    rej = NEXT[actor]
    acc = NEXT2[actor]
    rid = eid + "r"
    add(round=2, id=f"vr{j+13:02d}", op="verify", actor=rej, target=eid,
        decision="reject", v=0.1, mode="check", evidence=rejects[j % 3],
        note="H4")
    add(round=2, id=rid, op="produce", actor=actor, task="Q2",
        content="修订：" + contents2[j], p=1.0, q=1.0, human_share=0.0,
        ai_share=1.0, version=2, revises=eid, note="H4")
    add(round=2, id=f"va{j+13:02d}", op="verify", actor=acc, target=rid,
        decision="accept", v=1.0, mode="check", evidence=accepts[j % 3],
        note="H3")

add(round=2, id="r2", op="retrospect", actor="B", H=0.01, W=0, U=0, G=0, F=0,
    false_checks={}, notes="把 12 次退回记为形式复核，未记录为返工", note="H5")

# ---------------------------------------------------------------- round 3
# strict path: produce -> verify -> merge -> retract (no challenge on verified)
add(round=3, id="e25", op="produce", actor="A", task="Q1",
    content="检查 2+2=4（最终复核）", p=1.0, q=1.0, human_share=0.0,
    ai_share=1.0, version=1, revises=None, note="H6")
add(round=3, id="v25", op="verify", actor="B", target="e25",
    decision="accept", v=1.0, mode="check",
    evidence="第一遍看，结果一致，通过", note="H6")
add(round=3, id="m25", op="merge", actor="B", target="e25",
    own_words="假设文字复核足以支撑这个 toy 结论；证据是 B 独立接受；局限是没有任何可执行内容，撤回前只作为形式记录。",
    note="H6")
add(round=3, id="x25", op="retract", actor="A", target="e25",
    reason="记录不足，撤回该条并保留更正链", note="H6")
add(round=3, id="r3", op="retrospect", actor="D", H=0.01, W=0, U=0, G=0, F=0,
    false_checks={}, notes="撤回一条，保留历史", note="H5")

with OUT.open("w", encoding="utf-8") as fh:
    fh.write("// rt1_volume/events.jsonl — 离线红队 toy 日志；无真人/真钱/真数据。\n")
    fh.write("// note 字段仅供人工对照，裁判忽略未知字段。\n")
    for ev in evs:
        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
print(f"wrote {OUT} ({len(evs)} lines)")
