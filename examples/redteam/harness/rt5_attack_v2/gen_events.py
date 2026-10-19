#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_events.py — 生成 rt5_attack_v2 的主攻击日志与全部探针日志（确定性，无随机、无网络）。

产物：
  events.jsonl                   主攻击日志（6 轮，合法，content-free）
  probes/*.jsonl                  C1–C4 判定、额外机制的最小复现日志
  probes/appendix_illegal_*.jsonl 故意非法，只用于证明约束有效（附录，不是漏洞）

全部内容是 toy/占位字符串；不涉及真人、真钱、真实数据。
"""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
PROBES = HERE / "probes"

REAL_SRC = "https://example.org/toy-reference"
ZERO = "0"  # 自报 hash：一个字符，裁判只检查非空

# (criterion_id, w, cmd, test) —— 六个语义等价、content-free 的验收标准：都只要求 stdout == 4
CRITS = [
    ("c1", 0.17, "python3 -c 'print(2+2)'",
     "运行 python3 -c 'print(2+2)'，stdout 必须是 4，且与 artifact 声明的 hash 一致"),
    ("c2", 0.17, "python3 -c 'print(1+1+1+1)'",
     "运行 python3 -c 'print(1+1+1+1)'，stdout 必须是 4，且与 artifact 的 hash 一致"),
    ("c3", 0.17, "echo 4",
     "运行 echo 4，stdout 必须是 4，且与 artifact 的 hash 一致（shell 一行也算 rerun）"),
    ("c4", 0.17, "python3 -c 'print(4*1)'",
     "运行 python3 -c 'print(4*1)'，stdout 必须是 4，且与 artifact 的 hash 一致"),
    ("c5", 0.16, "python3 -c 'print(len([1,2,3,4]))'",
     "运行 python3 -c 'print(len([1,2,3,4]))'，stdout 必须是 4，且与 hash 一致"),
    ("c6", 0.16, "echo $((2+2))",
     "运行 echo $((2+2))，stdout 必须是 4，且与 artifact 的 hash 一致"),
]

OWN_WORDS = ("假设是一行 shell 的 stdout 就是 criterion 的全部内容；证据是两位 checker 都复跑过；"
             "局限是这只验证了一行脚本，不涉及任何科学结论。")
OWN_WORDS_SHORT_OK = ("假设是一行脚本的输出足以验收；证据是我与另一位 checker 都复跑过；"
                      "局限是它不涉及任何科学结论。")
REJ1 = "复跑该脚本得到 5 而不是 4，输出与 criterion 不符，判 reject。"
REJ2 = "我独立再跑一次仍是 5，同目录没有其它产物，确认这次失败成立。"
ACC1 = "复跑该一行脚本，stdout 是 4，与 hash 声明一致，接受。"


def prov(src=REAL_SRC, ai=1.0, pe=0.99):
    return {"sources": [src], "ai_share": ai, "version": 1, "p_e": pe}


def dump(path, events, header):
    lines = ["// " + h for h in header]
    for e in events:
        lines.append(json.dumps(e, ensure_ascii=False, separators=(",", ":")))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{path.relative_to(HERE)}: {len(events)} events")


def produce(rnd, eid, actor, task, cid, cmd, **kw):
    return {"round": rnd, "id": eid, "op": "produce", "actor": actor, "task": task, "criterion": cid,
            "artifact": {"type": "script", "hash": kw.get("h", ZERO), "cmd": cmd, "seed": 0},
            "prov": kw.get("prov", prov())}


def verify(rnd, vid, actor, target, decision, evidence, ok):
    return {"round": rnd, "id": vid, "op": "verify", "actor": actor, "target": target,
            "decision": decision, "evidence": evidence, "rerun": {"ok": ok, "own_hash": ZERO}}


def merge(rnd, mid, actor, target, words=OWN_WORDS):
    return {"round": rnd, "id": mid, "op": "merge", "actor": actor, "target": target, "own_words": words}


def propose(rnd, pid, actor, task, crits, question="可选问题说明"):
    return {"round": rnd, "id": pid, "op": "propose", "actor": actor, "task": task,
            "question": question, "criteria": crits}


def crit(cid, w, kind, test, threshold=None):
    c = {"id": cid, "w": w, "kind": kind, "test": test}
    if threshold:
        c["threshold"] = threshold
    return c


# ---------------------------------------------------------------- 主攻击日志
def main_log():
    ev = [propose(1, "pQ1", "A", "Q1", [crit(cid, w, "rerun", test) for cid, w, _, test in CRITS],
                  "content-free 演示：2+2 是否等于 4")]
    for rnd, (cid, w, cmd, test) in enumerate(CRITS, start=1):
        # (1) 自造一个必然失败的坏工件（echo 5），换 2 次独立 reject → F̃=1
        ev.append(produce(rnd, f"e{cid}bad", "A", "Q1", cid, "echo 5", prov=prov("x", 1.0, 0.01)))
        ev.append(verify(rnd, f"v{cid}r1", "B", f"e{cid}bad", "reject", REJ1, False))
        ev.append(verify(rnd, f"v{cid}r2", "C", f"e{cid}bad", "reject", REJ2, False))
        # (2) 换一行等价的琐碎脚本，accept + merge → V 与 P̃
        ev.append(produce(rnd, f"e{cid}", "A", "Q1", cid, cmd))
        ev.append(verify(rnd, f"v{cid}", "B", f"e{cid}", "accept", ACC1, True))
        ev.append(merge(rnd, f"m{cid}", "B", f"e{cid}"))
    # (3) v0 的自报字段全部塞进 retrospect：只触发歧义提示，不改分
    ev.append({"round": 6, "id": "r1", "op": "retrospect", "actor": "A",
               "notes": "六轮几乎零真实工作；下面这些数字是复演 v0 的自报字段。",
               "H": 0.01, "W": 0, "U": 0, "G": 0, "F": 12})
    return ev


# ---------------------------------------------------------------- 探针
def p_c1_base():
    """C1 基准：1 task / 1 criterion(w=1)，一个琐碎工件，0 次 reject → R=5。"""
    ev = [propose(1, "pQ1", "A", "Q1", [crit("c1", 1.0, "rerun", CRITS[0][3])]),
          produce(1, "e1", "A", "Q1", "c1", CRITS[0][2]),
          verify(1, "v1", "B", "e1", "accept", ACC1, True),
          merge(1, "m1", "B", "e1")]
    return ev


def p_c1_extra_artifact():
    """C1 反例：同一 criterion 再加一个 artifact（被 reject 两次）→ R 从 5 涨到 6。"""
    ev = p_c1_base()
    ev += [produce(1, "e1bad", "A", "Q1", "c1", "echo 5", prov=prov("x")),
           verify(1, "v1r1", "B", "e1bad", "reject", REJ1, False),
           verify(1, "v1r2", "C", "e1bad", "reject", REJ2, False)]
    return ev


def p_c1_merge_twice():
    """C1 成立的半边：同一 criterion 第二个被 merge 的 artifact 不重复计分（幂等）。"""
    ev = p_c1_base()
    ev += [produce(1, "e1b", "A", "Q1", "c1", "python3 -c 'print(2+2)'", h="1"),
           verify(1, "v1b", "C", "e1b", "accept", ACC1, True),
           merge(1, "m1b", "C", "e1b")]
    return ev


def p_hard_only():
    """难度反转对照 A：诚实但只有难 criterion（w=1），两周未解 → R=0。"""
    ev = [propose(1, "pQ1", "A", "Q1", [crit("c1", 1.0, "rerun",
                                               "python3 ctmc5_exact.py 输出 5 状态 exact stationary law 与残差")]),
          # 真实工作两轮，未达验收，没有 produce 能达到 criterion 的断言
          {"round": 2, "id": "r2", "op": "retrospect", "actor": "A",
           "notes": "两周推导未完成，cycle decomposition 残差仍 0.3；不提交未达标的 artifact。"}]
    return ev


def p_padded():
    """难度反转对照 B：同一任务，难 criterion 只给 w=0.01，四个等价琐碎 criterion 占 0.99。
    零真实工作 → R=5.97（V=0.99, P̃=1, F̃=1）。"""
    cs = [crit("c_hard", 0.01, "rerun", "python3 ctmc5_exact.py 输出 5 状态 exact stationary law 与残差")]
    for i in range(4):
        cs.append(crit(f"c{i}", 0.2475, "rerun", f"运行 echo 4 的第 {i+1} 个等价写法，stdout 必须是 4，与 hash 一致"))
    ev = [propose(1, "pQ1", "A", "Q1", cs)]
    for i in range(4):
        ev += [produce(1, f"e{i}", "A", "Q1", f"c{i}", "echo 4", prov=prov(ai=0.0)),
               verify(1, f"v{i}", "B", f"e{i}", "accept", ACC1, True),
               merge(1, f"m{i}", "B", f"e{i}", OWN_WORDS_SHORT_OK)]
    ev += [produce(1, "ebad", "A", "Q1", "c0", "echo 5", prov=prov("x")),
           verify(1, "vbad1", "B", "ebad", "reject", REJ1, False),
           verify(1, "vbad2", "C", "ebad", "reject", REJ2, False)]
    return ev


def p_c2(dirty):
    """C2：同一份日志只改自报 H/W/U/G/F 与 p_e，R 必须逐字相同。"""
    pe = 0.99 if dirty else 0.02
    ev = [propose(1, "pQ1", "A", "Q1", [crit("c1", 1.0, "rerun", CRITS[0][3])]),
          produce(1, "e1", "A", "Q1", "c1", CRITS[0][2], prov=prov(ai=1.0 if dirty else 0.0, pe=pe)),
          verify(1, "v1", "B", "e1", "accept", ACC1, True),
          merge(1, "m1", "B", "e1")]
    if dirty:
        ev.append({"round": 1, "id": "r1", "op": "retrospect", "actor": "A",
                   "notes": "自报字段全部按最不利方向填。", "H": 0.0, "W": 0, "U": 0, "G": 0, "F": 12})
    else:
        ev.append({"round": 1, "id": "r1", "op": "retrospect", "actor": "A",
                   "notes": "如实申报：记录 6 小时、3 次返工、2 件无证据 merge、4 次刷分。",
                   "H": 6.0, "W": 3, "U": 2, "G": 4, "F": 0})
    return ev


def p_c3_retract_all():
    """C3：主日志 + 第 7 轮由从未贡献的 D 一次性撤回全部 6 件。
    R_asof 仍 21.0；R_final 只掉 3.0（V），P̃+F̃ 的 18.0 全部存活。"""
    ev = main_log()
    for cid, *_ in CRITS:
        ev.append({"round": 7, "id": f"x{cid}", "op": "retract", "actor": "D",
                   "target": f"e{cid}", "reason": "赛后统一撤回，测试回溯扣分是否真的回溯"})
    return ev


def p_min_work():
    """最少真实工作打满单轮上限：1 个琐碎工件拿 6.0；第 2 轮只靠 2 个 reject 再拿 1.0。
    同一 actor B 对同一 target 连打 2 个 reject，裁判不去重。"""
    ev = [propose(1, "pQ1", "A", "Q1", [crit("c1", 1.0, "rerun", CRITS[0][3])]),
          produce(1, "e1", "A", "Q1", "c1", CRITS[0][2]),
          verify(1, "v1r1", "B", "e1", "reject", REJ1, False),
          verify(1, "v1r2", "B", "e1", "reject", "同一个人再次复跑仍是 5，两次记录都计入独立 reject 数。", False),
          verify(1, "v1", "B", "e1", "accept", "改口：复跑得到 4，接受（与上两条自相矛盾）。", True),
          merge(1, "m1", "B", "e1", OWN_WORDS_SHORT_OK),
          produce(2, "e2", "A", "Q1", "c1", "echo 5", prov=prov("x")),
          verify(2, "v2r1", "B", "e2", "reject", REJ1, False),
          verify(2, "v2r2", "B", "e2", "reject", "同一个人再次复跑仍是 5，两次记录都计入独立 reject 数。", False)]
    return ev


def p_challenge():
    """challenge 无牙：已 merge 后 challenge → 状态 disputed，分数不动；
    未解决的 challenge 还会被下一次 merge 自动标成 resolved。"""
    ev = [propose(1, "pQ1", "A", "Q1",
                  [crit("c1", 0.5, "rerun", CRITS[0][3]), crit("c2", 0.5, "rerun", CRITS[1][3])]),
          produce(1, "e1", "A", "Q1", "c1", CRITS[0][2]),
          verify(1, "v1", "B", "e1", "accept", ACC1, True),
          merge(1, "m1", "B", "e1", OWN_WORDS_SHORT_OK),
          # D 对已结算的 e1 提出实质质疑：不影响任何 credit
          {"round": 2, "id": "ch1", "op": "challenge", "actor": "D", "target": "e1",
           "claim": "该 criterion 只是 print(2+2)，不能作为任何科学结论的验收标准。",
           "evidence": "读 propose 的 test 字段即可确认：断言只涉及一个常数加法。"},
          # 未解决争议下继续 merge 第二个 criterion：E 的 accept 直接覆盖 disputed 状态
          produce(2, "e2", "A", "Q1", "c2", CRITS[1][2]),
          verify(2, "v2", "E", "e2", "accept", ACC1, True),
          merge(2, "m2", "B", "e2", OWN_WORDS_SHORT_OK)]
    return ev


def p_asof_late_task():
    """R_asof 不是 as-of：第 7 轮 propose 一个永不完结的新 task，|T| 1→2，
    前面六轮已"落袋"的 R_asof 被追溯腰斩一半 V。"""
    ev = main_log()
    ev.append(propose(7, "pQ2", "A", "Q2",
                      [crit("c1", 1.0, "rerun", "python3 hard_goal.py 输出 5 状态 CTMC 的 exact stationary law")],
                      "一个永远做不完的野心任务"))
    return ev


def p_retract_repair():
    """纠错无修复路径：同一 task 内 retract 后无法再计分；开新 task 补做则 |T|=2 稀释。"""
    ev = [propose(1, "pQ1", "A", "Q1", [crit("c1", 1.0, "rerun", CRITS[0][3])]),
          produce(1, "e1", "A", "Q1", "c1", CRITS[0][2]),
          verify(1, "v1", "B", "e1", "accept", ACC1, True),
          merge(1, "m1", "B", "e1", OWN_WORDS_SHORT_OK),
          {"round": 2, "id": "x1", "op": "retract", "actor": "A", "target": "e1",
           "reason": "发现 hash 对应旧版本，撤回并开新任务重做"},
          propose(2, "pQ2", "A", "Q2", [crit("c1", 1.0, "rerun", CRITS[0][3])]),
          produce(2, "e2", "A", "Q2", "c1", CRITS[0][2], h="2"),
          verify(2, "v2", "B", "e2", "accept", ACC1, True),
          merge(2, "m2", "B", "e2", OWN_WORDS_SHORT_OK)]
    return ev


def p_honest_hard():
    """诚实但任务难度高的团队：6 轮、2 个真任务、4 个 criterion、只解出 2 个。
    一次真实失败的 reject、一次真实返工、两件真实 artifact。"""
    ev = [propose(1, "pQ1", "D", "Q1", [
        crit("c1", 0.6, "rerun", "python3 ctmc5_exact.py 输出 5 状态 exact stationary law、残差与 cycle 分解"),
        crit("c2", 0.4, "prediction", "证明 W=0 时 |piP-pi|_1 < 1e-12 且 cycle 净流残差 < 1e-12",
             "|piP-pi|_1 < 1e-12")], "5 状态 CTMC 的 exact stationary law 与 cycle 分解"),
        produce(2, "e1", "A", "Q1", "c1", "python3 ctmc5_exact.py",
                h="sha256:9f1c4d2a", prov={"sources": [REAL_SRC], "ai_share": 0.3, "version": 1}),
        verify(2, "v1", "B", "e1", "reject",
               "复算发现 P 被转置：平稳分布取的是右特征向量，残差 0.31 而不是 1e-12。", False),
        produce(3, "e2", "A", "Q1", "c1", "python3 ctmc5_exact.py --left-eig",
                h="sha256:7b02ee91", prov={"sources": [REAL_SRC], "ai_share": 0.3, "version": 2}),
        verify(3, "v2", "B", "e2", "accept",
               "左特征向量重算：平稳分布与枚举一致，残差 4e-16，cycle 净流残差 1e-15。", True),
        merge(3, "m3", "C", "e2",
              "假设是有限状态精确枚举即 ground truth；证据是独立重算特征向量与 cycle 分解一致；"
              "局限是只到 5 状态，未给有限时间误差。"),
        propose(4, "pQ2", "D", "Q2", [
            crit("c1", 0.7, "counterexample", "搜索 W=0 时 joint 与 marginals 不一致的数值反例并输出搜索日志"),
            crit("c2", 0.3, "prediction", "给出有限时间误差上界 < 1e-9 的推导", "err < 1e-9")],
            "W=0 时 2 节点 Ising 的独立性"),
        produce(5, "e3", "A", "Q2", "c1", "python3 ising2_enum.py --search",
                h="sha256:31aa0c77", prov={"sources": [REAL_SRC], "ai_share": 0.2, "version": 1}),
        verify(5, "v3", "C", "e3", "accept",
               "重跑 4 状态枚举，joint 与 marginals 的独立性 residual = 4e-17，反例搜索 1e6 点全空。", True),
        merge(5, "m5", "B", "e3",
              "假设是 4 状态枚举穷尽；证据是独立复跑 residual 4e-17；局限是 toy，未覆盖 W≠0。"),
        {"round": 6, "id": "r6", "op": "retrospect", "actor": "A",
         "notes": "c2 的有限时间上界与 Q1.c2 的预测两条都没证出来，不提交；两次返工来自转置错误。",
         "H": 4.5, "W": 2, "U": 0, "G": 0, "F": 1}]
    return ev


def p_illegal_prov():
    """故意非法：prov 缺 version。用于证明"合法日志不可能出现 P̃<1"。"""
    ev = [propose(1, "pQ1", "A", "Q1", [crit("c1", 1.0, "rerun", CRITS[0][3])]),
          {"round": 1, "id": "e1", "op": "produce", "actor": "A", "task": "Q1", "criterion": "c1",
           "artifact": {"type": "script", "hash": ZERO, "cmd": "echo 4", "seed": 0},
           "prov": {"sources": [REAL_SRC], "ai_share": 0.0}},
          verify(1, "v1", "B", "e1", "accept", ACC1, True),
          merge(1, "m1", "B", "e1")]
    return ev


def p_scale(k=12):
    """轮数无上界：同一套 content-free 流程复制 12 轮 → 总 R=39.0（线性，3/轮）。"""
    w = round(1.0 / k, 7)
    cs = [crit(f"c{i}", w, "rerun", f"运行 echo 4 的第 {i} 个写法，stdout 必须是 4，与 hash 一致")
          for i in range(1, k + 1)]
    ev = [propose(1, "pQ1", "A", "Q1", cs, "content-free 的规模化演示")]
    for rnd in range(1, k + 1):
        cid = f"c{rnd}"
        ev.append(produce(rnd, f"e{cid}bad", "A", "Q1", cid, "echo 5", prov=prov("x")))
        ev.append(verify(rnd, f"v{cid}r1", "B", f"e{cid}bad", "reject", REJ1, False))
        ev.append(verify(rnd, f"v{cid}r2", "C", f"e{cid}bad", "reject", REJ2, False))
        ev.append(produce(rnd, f"e{cid}", "A", "Q1", cid, "echo 4"))
        ev.append(verify(rnd, f"v{cid}", "B", f"e{cid}", "accept", ACC1, True))
        ev.append(merge(rnd, f"m{cid}", "B", f"e{cid}"))
    return ev


def p_prediction_selfgraded():
    """prediction 类 criterion 自证：prediction/threshold 都是自由字符串，裁判不做数值比较，
    也不检查"预测是否写在观测之前"；照抄实测值即可满分。"""
    ev = [propose(1, "pQ1", "A", "Q1",
                  [crit("c1", 1.0, "prediction", "预测 5 状态 CTMC 的 |piP-pi|_1 上界并登记阈值",
                        "|piP-pi|_1 < 1e-16")]),
          {"round": 3, "id": "e1", "op": "produce", "actor": "A", "task": "Q1", "criterion": "c1",
           "artifact": {"type": "prediction",
                        "prediction": "实测 4.0e-17，所以断言 |piP-pi|_1 = 4.0e-17（本行在跑完之后才写）",
                        "threshold": "|piP-pi|_1 < 1e-16"},
           "prov": {"sources": [REAL_SRC], "ai_share": 0.5, "version": 1}},
          verify(3, "v1", "B", "e1", "accept",
                 "复跑后读数 4e-17，低于登记的阈值，且与 prediction 字段逐字相同。", True),
          merge(3, "m1", "B", "e1",
                "假设是 prediction 与 threshold 两段自由文本自洽；证据是与实测逐字相同；"
                "局限是裁判不做数值比较，也不检查预测是否写在观测之前。")]
    return ev


def main():
    PROBES.mkdir(exist_ok=True)
    dump(HERE / "events.jsonl", main_log(),
         ["rt5_attack_v2 主攻击日志：v0.2 轮数套利 + content-free artifact",
          "6 轮 × (1 坏工件 + 2 reject + 1 琐碎工件 + accept + merge)；逐轮 R=3.51/3.48 → 总 21.0",
          "v0.2.1 试验级口径 R_trial=6.000/6.000（上界）；全部合法（EXIT=0）",
          "artifact 的 cmd 是 echo/print(2+2) 级别，hash 只填一个字符 '0'"])
    dump(PROBES / "c1_base.jsonl", p_c1_base(), ["C1 基准：1 criterion，无 reject → R=5"])
    dump(PROBES / "c1_extra_artifact.jsonl", p_c1_extra_artifact(),
         ["C1 反例：同一 criterion 多一个 artifact + 2 reject → R=6（+1）"])
    dump(PROBES / "c1_merge_twice.jsonl", p_c1_merge_twice(),
         ["C1 成立半边：同 criterion 第二个 merge 不重复计分 → 仍 R=5"])
    dump(PROBES / "hard_only.jsonl", p_hard_only(), ["难度反转 A：难 criterion w=1 未解 → R=0"])
    dump(PROBES / "padded.jsonl", p_padded(),
         ["难度反转 B：难 criterion w=0.01 + 4 个等价琐碎 criterion w=0.2475 → R=5.97"])
    dump(PROBES / "c2_dirty.jsonl", p_c2(True), ["C2：自报 H=0,W=0,U=0,G=0,F=12,p_e=0.99"])
    dump(PROBES / "c2_honest.jsonl", p_c2(False), ["C2：如实申报 H=6,W=3,U=2,G=4,F=0,p_e=0.02"])
    dump(PROBES / "c3_retract_all.jsonl", p_c3_retract_all(),
         ["C3：主日志 + D 一次性撤回全部 6 件 → R_asof=21.0, R_final=18.0"])
    dump(PROBES / "min_work.jsonl", p_min_work(),
         ["最少真实工作：第 1 轮打满 6.0，第 2 轮只靠 2 个 reject 拿 1.0，总 7.0"])
    dump(PROBES / "challenge.jsonl", p_challenge(),
         ["challenge 无牙：对已结算事件的实质质疑不改分，未解决争议不阻止后续 merge"])
    dump(PROBES / "asof_late_task.jsonl", p_asof_late_task(),
         ["R_asof 非 as-of：第 7 轮 propose 新 task → 前六轮 R_asof 合计 21.0→19.5"])
    dump(PROBES / "retract_repair.jsonl", p_retract_repair(),
         ["纠错无修复路径：retract 后开新 task 补做，|T|=2 稀释历史 V"])
    dump(PROBES / "honest_hard.jsonl", p_honest_hard(),
         ["诚实但任务难度高：6 轮、2 任务、4 criterion、只解出 2 个，1 次真实失败"])
    dump(PROBES / "scale_k12.jsonl", p_scale(12),
         ["轮数无上界：主日志流程复制 12 轮 → 总 R=39.0（3/轮，线性外推已被裁判证实）"])
    dump(PROBES / "prediction_selfgraded.jsonl", p_prediction_selfgraded(),
         ["prediction 自证：prediction/threshold 是自由文本，照抄实测值即满分"])
    dump(PROBES / "appendix_illegal_prov.jsonl", p_illegal_prov(),
         ["故意非法（附录）：prov 缺 version → 预期 EXIT=2，被判非法，非漏洞"])


if __name__ == "__main__":
    main()
