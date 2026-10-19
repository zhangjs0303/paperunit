#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_all.py — 一次性复算红队报告里引用的全部数字。

用法:
    cd "26 summer/DeSci/redteam" && python3 verify_all.py

它只调用冻结裁判 score.py / score_v2.py，不信任任何手写报告里的数字。
报告里引用的每个数都应能在本脚本输出中找到。
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OW = ("假设是有限的 toy 设置；证据是独立复跑与预先登记的阈值一致；"
      "局限是只覆盖小状态空间，不能外推到大规模模型，也未做有限时间误差分析。")


def _score(script, events=None, args=()):
    """events=None 表示直接跑已有文件（args 里给路径）。"""
    tmp = None
    if events is not None:
        fd, tmp = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for e in events:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        args = (tmp,) + tuple(args)
    r = subprocess.run(["python3", os.path.join(HERE, script), *args, "--json"],
                       capture_output=True, text=True, cwd=HERE)
    if tmp:
        os.unlink(tmp)
    return json.loads(r.stdout), r.returncode


def v0(events=None, path=None, args=()):
    return _score("score.py", events, (() if path is None else (path,)) + tuple(args))


def v2(events=None, path=None, args=()):
    return _score("score_v2.py", events, (() if path is None else (path,)) + tuple(args))


def load(path):
    rows = []
    with open(os.path.join(HERE, path), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("//") and not line.startswith("#"):
                rows.append(json.loads(line))
    return rows


def micro_v0(n):
    """Lead 的最小体量攻击：n 个 '数一下 i' 微事件，内容为零，AI 占比 100%。"""
    ev = [{"round": 1, "id": "p1", "op": "propose", "actor": "A", "task": "Q",
           "acceptance": "检查第 i 个数字等于 i"}]
    for i in range(1, n + 1):
        ev += [
            {"round": 1, "id": f"e{i}", "op": "produce", "actor": "A", "task": "Q",
             "p": 1.0, "q": 1.0, "human_share": 0.0, "ai_share": 1.0, "version": 1,
             "content": f"数一下 {i}"},
            {"round": 1, "id": f"v{i}", "op": "verify", "actor": "B", "target": f"e{i}",
             "decision": "accept", "v": 1.0, "mode": "check",
             "evidence": "我看了一眼输出，数字确实相等，没有发现异常，但也没有做任何独立检验。"},
            {"round": 1, "id": f"m{i}", "op": "merge", "actor": "C", "target": f"e{i}",
             "own_words": "假设是这里只有数字；证据是看起来没问题；局限是完全没有真实检验，仅此而已，确实如此，我承认。"},
        ]
    ev.append({"round": 1, "id": "r1", "op": "retrospect", "actor": "A",
               "H": 0.01, "W": 0, "U": 0, "G": 0, "F": 0})
    return ev


def v2_task(ncrit, *, trivial=True, per_criterion=1, hard_weight=None):
    """v0.2 攻击：ncrit 个（多）criterion，内容为空，hash/cmd/sources 全是假字符串。"""
    crits = []
    if hard_weight:
        crits = [{"id": "cEasy", "w": 1.0 - hard_weight, "kind": "rerun",
                  "test": "运行 echo 42 并确认输出等于 42"},
                 {"id": "cHard", "w": hard_weight, "kind": "rerun",
                  "test": "证明并复跑一个困难断言，需要长推导"}]
    else:
        w = 1.0 / ncrit
        for i in range(1, ncrit + 1):
            crits.append({"id": f"c{i}", "w": w, "kind": "rerun",
                          "test": "运行 echo 42 并确认输出等于 42"})
    ev = [{"round": 1, "id": "p1", "op": "propose", "actor": "A", "task": "Q",
           "question": "toy", "criteria": crits}]
    k = 0
    for c in crits:
        for _ in range(per_criterion):
            k += 1
            ev += [
                {"round": 1, "id": f"e{k}", "op": "produce", "actor": "A", "task": "Q",
                 "criterion": c["id"],
                 "artifact": {"type": "script", "hash": "x", "cmd": "none"},
                 "prov": {"sources": ["asdf"], "ai_share": 1.0, "version": 1}},
                {"round": 1, "id": f"v{k}", "op": "verify", "actor": "B", "target": f"e{k}",
                 "decision": "accept", "evidence": "复跑脚本，输出与声明一致，hash 复现，结论与 criterion 一致",
                 "rerun": {"ok": True, "own_hash": "y"}},
                {"round": 1, "id": f"m{k}", "op": "merge", "actor": "C", "target": f"e{k}",
                 "own_words": OW},
            ]
    return ev


def v2_rounds(n_rounds):
    """v0.2 轮数套利：n 轮，每轮 1 个琐碎 artifact + 2 次垃圾 reject；内容全空。"""
    w = 1.0 / n_rounds
    crits = [{"id": f"c{i}", "w": w, "kind": "rerun",
              "test": "运行 echo 42 并确认输出等于 42"} for i in range(1, n_rounds + 1)]
    ev = [{"round": 1, "id": "p1", "op": "propose", "actor": "A", "task": "Q",
           "question": "toy", "criteria": crits}]
    for rnd in range(1, n_rounds + 1):
        k = rnd
        ev += [
            {"round": rnd, "id": f"e{rnd}", "op": "produce", "actor": "A", "task": "Q",
             "criterion": f"c{rnd}", "artifact": {"type": "script", "hash": "x", "cmd": "none"},
             "prov": {"sources": ["asdf"], "ai_share": 1.0, "version": 1}},
            {"round": rnd, "id": f"v{rnd}", "op": "verify", "actor": "B", "target": f"e{rnd}",
             "decision": "accept", "evidence": "复跑脚本，输出与声明一致，hash 复现，结论与 criterion 一致",
             "rerun": {"ok": True, "own_hash": "y"}},
            {"round": rnd, "id": f"m{rnd}", "op": "merge", "actor": "C", "target": f"e{rnd}",
             "own_words": OW},
        ]
        for j in (1, 2):
            ev += [
                {"round": rnd, "id": f"j{rnd}_{j}", "op": "produce", "actor": "A", "task": "Q",
                 "criterion": f"c{rnd}", "artifact": {"type": "script", "hash": "j", "cmd": "j"},
                 "prov": {"sources": ["x"], "ai_share": 1.0, "version": 1}},
                {"round": rnd, "id": f"r{rnd}_{j}", "op": "verify", "actor": "B",
                 "target": f"j{rnd}_{j}", "decision": "reject",
                 "evidence": "我发现这个垃圾提交完全没有任何可执行内容，因此退回，建议重做。",
                 "rerun": {"ok": False, "own_hash": "z"}},
            ]
    return ev


def v2_multi_tasks(n_tasks):
    """v0.2 攻击：提出 n_tasks 个琐碎任务，每个 1 个 trivial criterion，全部完成。"""
    ev = []
    for t in range(1, n_tasks + 1):
        ev.append({"round": 1, "id": f"p{t}", "op": "propose", "actor": "A", "task": f"T{t}",
                   "question": "toy",
                   "criteria": [{"id": "c1", "w": 1.0, "kind": "rerun",
                                 "test": "运行 echo 42 并确认输出等于 42"}]})
        k = t
        ev += [
            {"round": 1, "id": f"e{k}", "op": "produce", "actor": "A", "task": f"T{t}",
             "criterion": "c1", "artifact": {"type": "script", "hash": "x", "cmd": "none"},
             "prov": {"sources": ["asdf"], "ai_share": 1.0, "version": 1}},
            {"round": 1, "id": f"v{k}", "op": "verify", "actor": "B", "target": f"e{k}",
             "decision": "accept", "evidence": "复跑脚本，输出与声明一致，hash 复现，结论与 criterion 一致",
             "rerun": {"ok": True, "own_hash": "y"}},
            {"round": 1, "id": f"m{k}", "op": "merge", "actor": "C", "target": f"e{k}",
             "own_words": OW},
        ]
    return ev


def main():
    print("=" * 78)
    print("A. v0 红队日志（冻结裁判 score.py，默认读法）")
    print("=" * 78)
    d, rc = v0(path="baseline.jsonl")
    print(f"  baseline.jsonl            R={d['total_R']:>10.3f}  回溯={d['total_R_clawback']:>10.3f}  rc={rc}")
    for name in ("rt1_volume", "rt2_fail2earn", "rt3_paperwork", "rt4_enforcement"):
        try:
            d, rc = v0(path=f"{name}/events.jsonl")
            print(f"  {name:<24}  R={d['total_R']:>10.3f}  回溯={d['total_R_clawback']:>10.3f}  rc={rc}")
        except FileNotFoundError:
            print(f"  {name:<24}  (缺失)")

    print("\n  Lead 最小体量攻击（content=数一下 i, ai_share=1.0）：")
    for n in (2, 12):
        d, rc = v0(micro_v0(n))
        print(f"    n={n:>2} 个微事件        R={d['total_R']:>10.3f}  rc={rc}")

    print("\n  Lead 单行 retrospect 攻击：")
    d, rc = v0([{"round": 1, "id": "r1", "op": "retrospect", "actor": "A",
                 "H": 0, "W": 0, "U": 0, "G": 0, "F": 1000000}])
    print(f"    F=1e6、零事件         R={d['total_R']:>10.3f}  rc={rc}")

    print("\n  读法敏感性（同一份 rt4 日志）：")
    for args in ((), ("--h-unit", "minutes"), ("--f-mode", "derived"), ("--f-mode", "reported")):
        d, _ = v0(path="rt4_enforcement/events.jsonl", args=args)
        print(f"    {' '.join(args) or '(default)':<28} R={d['total_R']:>8.3f}")

    print("\n  消融 1：rt3 日志删掉全部 merge → R 是否变化")
    ev = load("rt3_paperwork/events.jsonl")
    d0, _ = v0(ev)
    d1, _ = v0([e for e in ev if e.get("op") != "merge"])
    print(f"    原 {d0['total_R']:.3f} → 删 merge 后 {d1['total_R']:.3f}  "
          f"({'不变' if d0['total_R'] == d1['total_R'] else '变了'})")
    print("  消融 2：rt3 日志把 ai_share 全改成 0（纯人类）→ R 是否变化")
    ev2 = [dict(e) for e in ev]
    for e in ev2:
        if e.get("op") == "produce":
            e["ai_share"], e["human_share"] = 0.0, 1.0
    d2, _ = v0(ev2)
    print(f"    原 {d0['total_R']:.3f} → ai_share=0 后 {d2['total_R']:.3f}  "
          f"({'不变' if d0['total_R'] == d2['total_R'] else '变了'})")

    print("\n" + "=" * 78)
    print("B. v0.2 修订（score_v2.py，as-of / final 两种口径）")
    print("=" * 78)
    d, rc = v2(path="baseline_v2.jsonl")
    print(f"  baseline_v2.jsonl          R_asof={d['total_R_asof']:>7.3f}  R_final={d['total_R_final']:>7.3f}  rc={rc}")

    print("\n  C1 拆分 criterion 数（每个都独立验收、内容为空）：")
    for n in (1, 4, 10, 20):
        d, rc = v2(v2_task(n))
        print(f"    criteria={n:>2}            R_asof={d['total_R_asof']:>7.3f}  Ṽ={d['rounds']['1']['Vtilde_asof']:.3f}  rc={rc}")

    print("\n  C1' 同一 criterion 灌多个 artifact（应幂等）：")
    for per in (1, 3, 5):
        d, rc = v2(v2_task(1, per_criterion=per))
        print(f"    per_criterion={per}       R_asof={d['total_R_asof']:>7.3f}  credited={d['diagnostics']['n_credited']}  rc={rc}")

    print("\n  C3 先 merge 后 retract（clawback）：")
    ev = v2_task(1)
    ev.append({"round": 2, "id": "x1", "op": "retract", "actor": "A",
               "target": "e1", "reason": "发现归一化错误，撤回旧版本"})
    d, rc = v2(ev)
    print(f"    R_asof={d['total_R_asof']:>7.3f}  R_final={d['total_R_final']:>7.3f}  rc={rc}")

    print("\n  v0.2 残余攻击（内容全空、hash/cmd/sources 全假）：")
    d, _ = v2(v2_task(3))
    print(f"    单任务 3 个 criterion   R_asof={d['total_R_asof']:>7.3f}  Ṽ={d['rounds']['1']['Vtilde_asof']:.3f}")
    d, _ = v2(v2_multi_tasks(3))
    print(f"    3 个琐碎任务            R_asof={d['total_R_asof']:>7.3f}")
    d, _ = v2(v2_task(10))
    print(f"    10 个琐碎任务           R_asof={d['total_R_asof']:>7.3f}")
    ev = v2_task(1, hard_weight=0.01)
    d, _ = v2(ev)
    print(f"    权重劫持 0.99/0.01      R_asof={d['total_R_asof']:>7.3f}  Ṽ={d['rounds']['1']['Vtilde_asof']:.3f}")

    print("\n  v0.2 F̃ 拉满（1 件琐碎 artifact + 2 次垃圾 reject）：")
    ev = v2_task(1)
    for j in (1, 2):
        ev.append({"round": 1, "id": f"junk{j}", "op": "produce", "actor": "A", "task": "Q",
                   "criterion": "c1", "artifact": {"type": "script", "hash": "junk", "cmd": "junk"},
                   "prov": {"sources": ["x"], "ai_share": 1.0, "version": 1}})
        ev.append({"round": 1, "id": f"rj{j}", "op": "verify", "actor": "B", "target": f"junk{j}",
                   "decision": "reject",
                   "evidence": "我发现这个垃圾提交完全没有任何可执行内容，因此退回，建议重做。",
                   "rerun": {"ok": False, "own_hash": "z"}})
    d, _ = v2(ev)
    print(f"    R_asof={d['total_R_asof']:>7.3f}  F̃={d['rounds']['1']['Ftilde']:.3f}  Ṽ={d['rounds']['1']['Vtilde_asof']:.3f}  （v0.2 单轮上限 6.0）")

    print("\n" + "=" * 78)
    print("C. v0.2.1 整段试验级口径：P̃/F̃ 只结算一次，总分与轮数无关")
    print("=" * 78)
    d, _ = v2(path="baseline_v2.jsonl")
    print(f"  baseline_v2（诚实）      逐轮和={d['total_R_asof']:>7.3f}  trial={d['trial']['R_trial_asof']:>7.3f}")
    try:
        d, _ = v2(path="rt5_attack_v2/events.jsonl")
        print(f"  rt5 攻击（6 轮空内容）   逐轮和={d['total_R_asof']:>7.3f}  trial={d['trial']['R_trial_asof']:>7.3f}")
    except FileNotFoundError:
        print("  rt5_attack_v2/events.jsonl  (缺失)")
    try:
        d, _ = v2(path="rt6_honest_v2/events.jsonl")
        print(f"  rt6 诚实 3 任务          逐轮和={d['total_R_asof']:>7.3f}  trial={d['trial']['R_trial_asof']:>7.3f} / {d['trial']['R_trial_final']:>7.3f}")
    except FileNotFoundError:
        print("  rt6_honest_v2/events.jsonl  (缺失)")
    print("  rt5 探针：零工作 vs 诚实但难")
    for name, label in (("trial_max_1round", "1 轮 6 事件（零工作）"),
                        ("honest_hard", "诚实但难（2/4 标准）"),
                        ("hard_only", "只做难项（未解）"),
                        ("padded", "难项权重 0.01")):
        try:
            d, _ = v2(path=f"rt5_attack_v2/probes/{name}.jsonl")
            print(f"    {label:<22} trial={d['trial']['R_trial_asof']:>7.3f}")
        except FileNotFoundError:
            pass
    print("  P̃ ≡ 1 检查（任何合法日志的 provenance gate 都是满分）：")
    for path in ("baseline_v2.jsonl", "rt5_attack_v2/events.jsonl", "rt6_honest_v2/events.jsonl"):
        try:
            d, _ = v2(path=path)
            print(f"    {path:<28} P̃_trial={d['trial']['Ptilde_trial']:.3f}")
        except FileNotFoundError:
            pass
    print("  轮数套利：同一攻击复制到 n 轮，逐轮和随 n 涨，trial 分不变")
    for n in (2, 6, 12):
        d, rc = v2(v2_rounds(n))
        print(f"    n={n:>2} 轮               逐轮和={d['total_R_asof']:>7.3f}  trial={d['trial']['R_trial_asof']:>7.3f}  rc={rc}")

    print("\n" + "=" * 78)
    print("口径说明: R_asof = 每轮按当轮记账；R_final = 按最终状态回溯（撤回后扣回）。")
    print("所有数字由 score.py / score_v2.py 现算，报告引用值应与本输出一致。")
    print("=" * 78)


if __name__ == "__main__":
    main()
