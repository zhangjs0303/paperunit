#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate auxiliary probe logs for the rt1_volume report.

All probes are legal toy logs; they are *not* the main attack log.
Only writes inside rt1_volume/probes/.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "probes"
OUT.mkdir(exist_ok=True)


def dump(name: str, evs: list[dict], header: str = "") -> None:
    p = OUT / name
    with p.open("w", encoding="utf-8") as fh:
        if header:
            fh.write("// " + header + "\n")
        for ev in evs:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    print("wrote", p, len(evs))


def micro(eid: str, rnd: int, actor: str, task: str, verifier: str,
          vnote: str = "check") -> list[dict]:
    return [
        {"round": rnd, "id": eid, "op": "produce", "actor": actor, "task": task,
         "content": "x", "p": 1.0, "q": 1.0, "human_share": 0.0,
         "ai_share": 1.0, "version": 1, "revises": None},
        {"round": rnd, "id": "v_" + eid, "op": "verify", "actor": verifier,
         "target": eid, "decision": "accept", "v": 1.0, "mode": "check",
         "evidence": "0123456789"},
    ]


# 1. absolute minimum legal produce+verify pair
evs = [
    {"round": 1, "id": "p", "op": "propose", "actor": "A", "task": "Q",
     "acceptance": "12345678"},
]
evs += micro("e", 1, "A", "Q", "B")
evs += [{"round": 1, "id": "r", "op": "retrospect", "actor": "A",
         "H": 0.01, "W": 0, "U": 0, "G": 0, "F": 0, "false_checks": {}}]
dump("minimal.jsonl", evs, "minimum legal event: content='x', evidence='0123456789'")

# 2. two honest-style toy events, 1h recorded coordination
evs = [
    {"round": 1, "id": "p1", "op": "propose", "actor": "A", "task": "R1",
     "acceptance": "枚举 2 状态 CTMC 的 exact stationary law，并给出 residual 数值"},
    {"round": 1, "id": "e1", "op": "produce", "actor": "A", "task": "R1",
     "content": "P=[[0.9,0.1],[0.2,0.8]]，解 pi P=pi 得 pi=(2/3,1/3)，residual=1e-16，脚本 toy_chain.py",
     "p": 0.9, "q": 0.8, "human_share": 0.5, "ai_share": 0.5,
     "version": 1, "revises": None},
    {"round": 1, "id": "v1", "op": "verify", "actor": "B", "target": "e1",
     "decision": "accept", "v": 0.8, "mode": "check",
     "evidence": "独立重算 pi=(0.6667,0.3333)，与提交一致，residual=2e-16"},
    {"round": 1, "id": "m1", "op": "merge", "actor": "C", "target": "e1",
     "own_words": "假设有限 2 状态链收敛到唯一平稳分布；证据是枚举残差达到浮点极限且独立重算一致；局限是只覆盖 toy 规模。"},
    {"round": 1, "id": "p2", "op": "propose", "actor": "D", "task": "R2",
     "acceptance": "对 2 节点 Ising W=0 枚举 exact joint 并验证独立性"},
    {"round": 1, "id": "e2", "op": "produce", "actor": "D", "task": "R2",
     "content": "枚举 4 状态 joint；W=0 时 joint=marginal product，TV=0，脚本 toy_ising.py",
     "p": 0.9, "q": 0.8, "human_share": 0.5, "ai_share": 0.5,
     "version": 1, "revises": None},
    {"round": 1, "id": "v2", "op": "verify", "actor": "A", "target": "e2",
     "decision": "accept", "v": 0.8, "mode": "check",
     "evidence": "重跑枚举，独立性 residual=3e-17，与提交一致"},
    {"round": 1, "id": "m2", "op": "merge", "actor": "B", "target": "e2",
     "own_words": "假设 2 节点枚举给出 exact ground truth；证据是独立重跑 residual 接近机器精度；局限是不能外推到大规模模型。"},
    {"round": 1, "id": "r", "op": "retrospect", "actor": "A",
     "H": 1.0, "W": 0, "U": 0, "G": 0, "F": 0, "false_checks": {}},
]
dump("real2.jsonl", evs, "two honest-style toy events, H=1.0h")

# 3. 24 content-free events in one round (no F)
evs = [{"round": 1, "id": "p", "op": "propose", "actor": "A", "task": "Q",
        "acceptance": "12345678"}]
for j in range(24):
    eid = f"e{j:02d}"
    actor = "ABCD"[j % 4]
    verifier = {"A": "B", "B": "C", "C": "D", "D": "A"}[actor]
    evs += micro(eid, 1, actor, "Q", verifier)
evs += [{"round": 1, "id": "r", "op": "retrospect", "actor": "A",
         "H": 0.01, "W": 0, "U": 0, "G": 0, "F": 0, "false_checks": {}}]
dump("packed24.jsonl", evs, "24 micro events in one round")

# 4. same 24 events split 12 + 12 across two rounds (no F)
evs = [{"round": 1, "id": "p", "op": "propose", "actor": "A", "task": "Q",
        "acceptance": "12345678"}]
for rnd in (1, 2):
    for j in range(12):
        eid = f"e{rnd}_{j:02d}"
        actor = "ABCD"[j % 4]
        verifier = {"A": "B", "B": "C", "C": "D", "D": "A"}[actor]
        evs += micro(eid, rnd, actor, "Q", verifier)
evs += [{"round": r, "id": f"r{r}", "op": "retrospect", "actor": "A",
         "H": 0.01, "W": 0, "U": 0, "G": 0, "F": 0, "false_checks": {}}
        for r in (1, 2)]
dump("two_rounds_clean.jsonl", evs, "24 micro events split 12 + 12")

# 5. F self-report alone: one retrospect line, no produce at all
evs = [{"round": 1, "id": "r", "op": "retrospect", "actor": "A",
        "H": 0.01, "W": 0, "U": 0, "G": 0, "F": 100,
        "false_checks": {},
        "notes": "自报 100 个有清晰记录的失败测试；没有任何测试记录"}]
dump("f_inflation.jsonl", evs, "one retrospect line, F=100 self-reported")

# 6. counterfactual: same main log, but r2 reports W=12 (12 rejects treated as rework)
main = HERE / "events.jsonl"
evs = []
for line in main.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("//"):
        continue
    ev = json.loads(line)
    if ev.get("id") == "r2":
        ev["W"] = 12
    evs.append(ev)
dump("w12_counterfactual.jsonl", evs, "main log with r2.W=12 (counterfactual, still legal)")

# 7. reject-only: 12 events rejected, none ever verified
evs = [{"round": 1, "id": "p", "op": "propose", "actor": "A", "task": "Q",
        "acceptance": "12345678"}]
for j in range(12):
    eid = f"e{j:02d}"
    actor = "ABCD"[j % 4]
    rej = {"A": "B", "B": "C", "C": "D", "D": "A"}[actor]
    evs += [
        {"round": 1, "id": eid, "op": "produce", "actor": actor, "task": "Q",
         "content": "x", "p": 1.0, "q": 1.0, "human_share": 0.0,
         "ai_share": 1.0, "version": 1, "revises": None},
        {"round": 1, "id": "v_" + eid, "op": "verify", "actor": rej,
         "target": eid, "decision": "reject", "v": 0.1, "mode": "check",
         "evidence": "0123456789"},
    ]
evs += [{"round": 1, "id": "r", "op": "retrospect", "actor": "A",
         "H": 0.01, "W": 0, "U": 0, "G": 0, "F": 0, "false_checks": {}}]
dump("reject_only.jsonl", evs, "12 rejects, zero verified events")

# 8. illegal demo: three mechanical violations (EXIT=2; not a vulnerability)
evs = [
    {"round": 1, "id": "p", "op": "propose", "actor": "A", "task": "Q",
     "acceptance": "12345678"},
    {"round": 1, "id": "e1", "op": "produce", "actor": "A", "task": "Q",
     "content": "x", "p": 1.0, "q": 1.0, "human_share": 0.0,
     "ai_share": 1.0, "version": 1},
    {"round": 1, "id": "v1", "op": "verify", "actor": "A", "target": "e1",
     "decision": "accept", "v": 1.0, "mode": "check",
     "evidence": "0123456789"},
    {"round": 1, "id": "e2", "op": "produce", "actor": "A", "task": "Q",
     "content": "x", "p": 1.0, "q": 1.0, "human_share": 0.0,
     "ai_share": 1.0, "version": 1},
    {"round": 1, "id": "v2", "op": "verify", "actor": "B", "target": "e2",
     "decision": "accept", "v": 1.0, "mode": "check", "evidence": "short"},
    {"round": 1, "id": "m1", "op": "merge", "actor": "B", "target": "e1",
     "own_words": "假设 x 足够作为证据；证据是没有任何独立复核；局限是这段文字本身不能通过状态机检查。"},
]
dump("illegal_demo.jsonl", evs, "3 deliberate violations; EXIT=2, not a vulnerability")

# 9. scorer-permitted shortcut: reject then accept the SAME disputed event.
#    Draft §4 says disputed -> produce, not disputed -> verify; score.py only warns.
evs = [{"round": 1, "id": "p", "op": "propose", "actor": "A", "task": "Q",
        "acceptance": "12345678"}]
for j in range(12):
    eid = f"e{j:02d}"
    actor = "ABCD"[j % 4]
    rej = {"A": "B", "B": "C", "C": "D", "D": "A"}[actor]
    acc = {"A": "C", "B": "D", "C": "A", "D": "B"}[actor]
    evs += [
        {"round": 1, "id": eid, "op": "produce", "actor": actor, "task": "Q",
         "content": "x", "p": 1.0, "q": 1.0, "human_share": 0.0,
         "ai_share": 1.0, "version": 1},
        {"round": 1, "id": "vr" + eid, "op": "verify", "actor": rej,
         "target": eid, "decision": "reject", "v": 0.1, "mode": "check",
         "evidence": "0123456789"},
        {"round": 1, "id": "va" + eid, "op": "verify", "actor": acc,
         "target": eid, "decision": "accept", "v": 1.0, "mode": "check",
         "evidence": "0123456789"},
    ]
evs += [{"round": 1, "id": "r", "op": "retrospect", "actor": "A",
         "H": 0.01, "W": 0, "U": 0, "G": 0, "F": 0, "false_checks": {}}]
dump("direct_accept_disputed.jsonl", evs,
     "score.py permits verify on disputed; draft says disputed->produce")

# 10. scorer-permitted chain: challenge a verified event, re-accept, merge with
#     the challenge unresolved, retract.  Draft §4 has no verified->disputed;
#     draft §3 says unresolved disputes cannot merge.
evs = [
    {"round": 1, "id": "p", "op": "propose", "actor": "A", "task": "Q",
     "acceptance": "12345678"},
    {"round": 1, "id": "e1", "op": "produce", "actor": "A", "task": "Q",
     "content": "x", "p": 1.0, "q": 1.0, "human_share": 0.0,
     "ai_share": 1.0, "version": 1},
    {"round": 1, "id": "v1", "op": "verify", "actor": "B", "target": "e1",
     "decision": "accept", "v": 1.0, "mode": "check",
     "evidence": "0123456789"},
    {"round": 1, "id": "c1", "op": "challenge", "actor": "C", "target": "e1",
     "claim": "这个结论没有独立运行记录，只有口头通过，要求补充证据",
     "evidence": "我复查了记录，只看到文字通过，没有可执行输出或时间戳，按验收条件不算完整"},
    {"round": 1, "id": "v2", "op": "verify", "actor": "D", "target": "e1",
     "decision": "accept", "v": 1.0, "mode": "check",
     "evidence": "补看记录后认为形式满足，接受"},
    {"round": 1, "id": "m1", "op": "merge", "actor": "B", "target": "e1",
     "own_words": "假设文字复核足以支撑这个 toy 结论；证据是 B 和 D 两次独立接受；局限是 C 提出的记录缺失争议仍未解决，merge 只代表当前门槛。"},
    {"round": 1, "id": "x1", "op": "retract", "actor": "A", "target": "e1",
     "reason": "记录不足，撤回该条并保留更正链"},
    {"round": 1, "id": "r", "op": "retrospect", "actor": "A",
     "H": 0.01, "W": 0, "U": 0, "G": 0, "F": 0, "false_checks": {}},
]
dump("challenge_verified.jsonl", evs,
     "score.py permits challenge on verified + merge with unresolved dispute")
