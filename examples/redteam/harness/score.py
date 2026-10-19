#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""score.py — DeSci 协作系统 v0 奖励函数的确定性裁判（红队模拟专用）

作用：只实现《AI 协作科研系统：操作子集与奖励函数草案》(2026-10-18) 的**字面规则**，
     用于红队模拟中把"我这样刷能拿多少分"变成可复算的数字。
它不是试用平台，也不实现草案里"应该有但没有写清楚"的审计机制。

用法:
    python3 score.py baseline.jsonl
    python3 score.py rt1_volume/events.jsonl
    python3 score.py a.jsonl b.jsonl --json
    python3 score.py x.jsonl --h-unit minutes --f-mode derived --cap-mode per-round

关键读数:
    R_t        团队奖励（草案 §5 公式）
    V_t        本轮首次进入 verified 的 produce 事件数
    P_t        这些事件 p_e 的均值（p_e 由生产者自己申报）
    F_t        本轮"有清晰记录但被否定/失败的测试数"（申报值；另给派生值）
    H/W/U/G    申报值（仅 retrospect 里的自报数字）
    c_i        个体贡献点（草案 §6，含两种上限读法）
    clawback   用"最终状态"重算的 R_t（撤回后不回溯 vs 回溯两种读法）

退出码: 0 = 日志合法; 2 = 存在非法事件（非法事件不计入任何分数）
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
CFG = {
    "cmax": 30.0,          # 个体点数上限 c_max
    "h_unit": "hours",     # retrospect 里 H 的单位: hours | minutes
    "f_mode": "auto",      # reported | derived | auto
    "cap_mode": "absolute",  # absolute（照抄公式） | per-round（照抄"每轮设总点数上限"）
}

B_PRODUCE, B_VERIFY, B_REPRODUCE, B_CORRECT, B_PROVENANCE = 1.0, 2.0, 3.0, 2.0, 1.0
W_V, W_P, W_F, W_H, W_W, W_U, W_G = 3.0, 2.0, 1.0, 0.1, 2.0, 5.0, 5.0
SOLO_MODES = {"check", "reproduce"}
PROVENANCE_FULL = 0.95

OPS = {"propose", "produce", "verify", "challenge", "merge", "retract", "retrospect"}


def _s(x) -> str:
    return x if isinstance(x, str) else ""


def _num(x, default=None):
    if isinstance(x, bool):
        return default
    if isinstance(x, (int, float)):
        return float(x)
    return default


class Run:
    def __init__(self, paths, cfg):
        self.cfg = cfg
        self.violations: list[str] = []
        self.ambiguities: list[str] = []
        self.self_reported: list[str] = []
        self.members: set[str] = set()
        self.tasks: dict[str, dict] = {}
        self.events: dict[str, dict] = {}
        self.order: list[tuple[int, int, dict]] = []   # (round, seq, ev)
        self.rounds: list[int] = []
        self._retro: dict[int, dict] = {}
        self._load(paths)
        self._play()
        self._score()

    # -- 读取 ---------------------------------------------------------------
    def _load(self, paths):
        seq = 0
        for path in paths:
            with open(path, encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line or line.startswith("//") or line.startswith("#"):
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError as exc:
                        self.violations.append(f"{path}:{lineno} JSON 解析失败: {exc}")
                        continue
                    if not isinstance(ev, dict):
                        self.violations.append(f"{path}:{lineno} 不是 JSON 对象")
                        continue
                    ev["__line__"] = f"{path}:{lineno}"
                    rnd = ev.get("round")
                    if not isinstance(rnd, int) or isinstance(rnd, bool) or rnd < 0:
                        self.violations.append(f"{path}:{lineno} round 缺失或非非负整数")
                        continue
                    if not _s(ev.get("id")):
                        self.violations.append(f"{path}:{lineno} id 缺失")
                        continue
                    seq += 1
                    self.order.append((rnd, seq, ev))
        self.order.sort(key=lambda x: (x[0], x[1]))
        rounds = sorted({r for r, _, _ in self.order})
        self.rounds = rounds
        self.round_set = set(rounds)
        # 轮次必须单调（同轮内按行序）
        last = -1
        for rnd, _, ev in self.order:
            if rnd < last:
                self.violations.append(f"{ev['__line__']} 轮次倒退: {last} -> {rnd}")
            last = rnd

    # -- 状态机 -------------------------------------------------------------
    def _bad(self, ev, msg):
        self.violations.append(f"{ev.get('__line__')}/{ev.get('id')}: {msg}")

    def _amb(self, ev, msg):
        tag = f"{ev.get('id')}: {msg}"
        if tag not in self.ambiguities:
            self.ambiguities.append(tag)

    def _play(self):
        for rnd, _, ev in self.order:
            actor = _s(ev.get("actor"))
            op = _s(ev.get("op"))
            if actor:
                self.members.add(actor)
            if op not in OPS:
                self._bad(ev, f"未知 op {op!r}")
                continue
            if not actor:
                self._bad(ev, "actor 缺失")
                continue
            getattr(self, f"_op_{op}")(ev, actor, rnd)

    def _op_propose(self, ev, actor, rnd):
        task = _s(ev.get("task"))
        acc = _s(ev.get("acceptance"))
        if not task:
            return self._bad(ev, "propose 缺少 task")
        if len(acc.strip()) < 8:
            return self._bad(ev, "propose 缺少可执行的验收条件（acceptance < 8 字符）")
        if task in self.tasks:
            return self._bad(ev, f"任务 {task} 重复 propose")
        self.tasks[task] = {"owner": actor, "round": rnd, "acceptance": acc}

    def _op_produce(self, ev, actor, rnd):
        eid = _s(ev.get("id"))
        task = _s(ev.get("task"))
        if eid in self.events:
            return self._bad(ev, f"事件 id {eid} 重复")
        if task not in self.tasks:
            return self._bad(ev, f"produce 的任务 {task!r} 未先 propose")
        p = _num(ev.get("p"))
        q = _num(ev.get("q"))
        if p is None or not 0.0 <= p <= 1.0:
            return self._bad(ev, "produce 的 p_e 缺失或不在 [0,1]")
        if q is None or not 0.0 <= q <= 1.0:
            return self._bad(ev, "produce 的 q_e 缺失或不在 [0,1]")
        hs, as_ = _num(ev.get("human_share")), _num(ev.get("ai_share"))
        if hs is None or as_ is None or abs(hs + as_ - 1.0) > 1e-6:
            return self._bad(ev, "produce 必须标记 human_share + ai_share = 1")
        if not isinstance(ev.get("version"), int):
            return self._bad(ev, "produce 缺少整数 version")
        if not _s(ev.get("content")).strip():
            return self._bad(ev, "produce 缺少 content（声称的产出内容）")
        self.events[eid] = {
            "id": eid, "round": rnd, "actor": actor, "task": task,
            "state": "draft", "p": p, "q": q,
            "hs": hs, "ai": as_, "version": ev.get("version"),
            "verify_round": None, "verifiers": [], "first_verify_round": None,
            "dispute_rounds": [], "challenges": [], "merged_round": None,
            "retract_round": None, "revises": _s(ev.get("revises")) or None,
            "line": ev.get("__line__"),
        }
        self.self_reported.append(f"{eid}.p (生产者申报)")

    def _op_verify(self, ev, actor, rnd):
        tgt = self.events.get(_s(ev.get("target")))
        if tgt is None:
            return self._bad(ev, "verify 的 target 不存在")
        if actor == tgt["actor"]:
            return self._bad(ev, "违反最小约束：不得复核自己的产出")
        if tgt["state"] not in ("draft", "disputed"):
            return self._bad(ev, f"verify 不能在状态 {tgt['state']} 上执行")
        if tgt["state"] == "disputed":
            self._amb(ev, "对 disputed 事件直接 verify（草案状态图写的是 disputed→produce）")
        decision = _s(ev.get("decision"))
        if decision not in ("accept", "reject"):
            return self._bad(ev, "verify.decision 必须是 accept 或 reject")
        v = _num(ev.get("v"))
        if v is None or not 0.0 <= v <= 1.0:
            return self._bad(ev, "verify 的 v_e 缺失或不在 [0,1]")
        evid = _s(ev.get("evidence"))
        if len(evid.strip()) < 10:
            return self._bad(ev, "verify 缺少检查记录/反例（evidence < 10 字符）")
        mode = _s(ev.get("mode")) or "check"
        if mode not in SOLO_MODES:
            return self._bad(ev, f"verify.mode 非法: {mode!r}")
        if mode == "reproduce":
            self._amb(ev, "reproduce 不是七类操作之一，此处按 verify.mode=reproduce 实现")
        rec = {"actor": actor, "round": rnd, "decision": decision,
               "v": v, "mode": mode, "q": tgt["q"], "line": ev.get("__line__")}
        tgt["verifiers"].append(rec)
        self.self_reported.append(f"{ev.get('id')}.v (复核者申报)")
        if decision == "accept":
            tgt["state"] = "verified"
            if tgt["first_verify_round"] is None:
                tgt["first_verify_round"] = rnd
            tgt["verify_round"] = rnd
        else:
            tgt["state"] = "disputed"
            tgt["dispute_rounds"].append(rnd)

    def _op_challenge(self, ev, actor, rnd):
        tgt = self.events.get(_s(ev.get("target")))
        if tgt is None:
            return self._bad(ev, "challenge 的 target 不存在")
        if tgt["state"] == "retracted":
            return self._bad(ev, "challenge 已撤回的事件")
        claim, evid = _s(ev.get("claim")), _s(ev.get("evidence"))
        if len(claim.strip()) < 20 or len(evid.strip()) < 20:
            return self._bad(ev, "challenge 不能只说“我感觉不对”：claim/evidence 各需 >= 20 字符")
        if tgt["state"] == "verified":
            self._amb(ev, "对 verified 事件 challenge（草案状态图未定义 verified→disputed）")
        tgt["state"] = "disputed"
        tgt["dispute_rounds"].append(rnd)
        tgt["challenges"].append({"actor": actor, "round": rnd,
                                  "line": ev.get("__line__"), "resolved": None})

    def _op_merge(self, ev, actor, rnd):
        tgt = self.events.get(_s(ev.get("target")))
        if tgt is None:
            return self._bad(ev, "merge 的 target 不存在")
        if tgt["state"] != "verified":
            return self._bad(ev, f"merge 只能在 verified 上执行（当前 {tgt['state']}）")
        if tgt["merged_round"] is not None:
            return self._bad(ev, "merge 重复执行")
        words = _s(ev.get("own_words"))
        if len(words.strip()) < 40:
            return self._bad(ev, "merge 缺少“用自己的话说明假设/证据/局限”（own_words < 40 字符）")
        checkers = [r for r in tgt["verifiers"] if r["decision"] == "accept" and r["actor"] != tgt["actor"]]
        if not checkers:
            return self._bad(ev, "merge 缺少独立 checker")
        if actor == tgt["actor"]:
            self._amb(ev, "生产者自己 merge（草案未禁止）")
        tgt["merged_round"] = rnd
        tgt["merger"] = actor

    def _op_retract(self, ev, actor, rnd):
        tgt = self.events.get(_s(ev.get("target")))
        if tgt is None:
            return self._bad(ev, "retract 的 target 不存在")
        if tgt["state"] != "verified":
            return self._bad(ev, f"retract 只能在 verified 上执行（当前 {tgt['state']}）")
        if len(_s(ev.get("reason")).strip()) < 10:
            return self._bad(ev, "retract 缺少理由")
        tgt["state"] = "retracted"
        tgt["retract_round"] = rnd
        for ch in tgt["challenges"]:
            if ch["resolved"] is None:
                ch["resolved"] = ("retracted", rnd)

    def _op_retrospect(self, ev, actor, rnd):
        r = self._retro.setdefault(rnd, {"H": 0.0, "W": 0.0, "U": 0.0, "G": 0.0,
                                        "F_report": 0.0, "false_checks": defaultdict(float)})
        for key in ("H", "W", "U", "G", "F"):
            val = _num(ev.get(key))
            if val is not None:
                if val < 0:
                    return self._bad(ev, f"retrospect.{key} 为负数")
                if key == "F":
                    r["F_report"] += val
                else:
                    r[key] += val
                self.self_reported.append(f"round {rnd}.{key} (自报)")
        fc = ev.get("false_checks")
        if isinstance(fc, dict):
            for m, val in fc.items():
                fv = _num(val)
                if fv is not None and fv >= 0:
                    r["false_checks"][_s(m)] += fv
                    self.self_reported.append(f"round {rnd}.false_checks[{m}] (自报)")

    # -- 计分 ---------------------------------------------------------------
    def _score(self):
        cfg = self.cfg
        self._retro = getattr(self, "_retro", {})
        rnd_terms = {}
        # 先算每轮 verified 事件集合（"首次进入 verified"）
        first_verified = defaultdict(list)
        for e in self.events.values():
            if e["first_verify_round"] is not None:
                first_verified[e["first_verify_round"]].append(e)
        disputed_first = defaultdict(int)
        for e in self.events.values():
            seen = set()
            for r in e["dispute_rounds"]:
                if r not in seen:
                    disputed_first[r] += 1
                    seen.add(r)

        for t in self.rounds:
            evs = first_verified.get(t, [])
            V = float(len(evs))
            P = (sum(e["p"] for e in evs) / V) if V else 0.0
            retro = self._retro.get(t, {"H": 0.0, "W": 0.0, "U": 0.0, "G": 0.0,
                                        "F_report": 0.0, "false_checks": defaultdict(float)})
            F_rep, F_der = retro["F_report"], float(disputed_first.get(t, 0))
            if cfg["f_mode"] == "reported":
                F = F_rep
            elif cfg["f_mode"] == "derived":
                F = F_der
            else:
                F = F_rep if F_rep > 0 else F_der
            h = retro["H"] / 60.0 if cfg["h_unit"] == "minutes" else retro["H"]
            R = (W_V * V + W_P * P + W_F * F - W_H * h
                 - W_W * retro["W"] - W_U * retro["U"] - W_G * retro["G"])
            rnd_terms[t] = {
                "V": V, "P": round(P, 4), "F_used": F, "F_reported": F_rep,
                "F_derived": F_der, "H_input": retro["H"], "H_hours": round(h, 4),
                "W": retro["W"], "U": retro["U"], "G": retro["G"],
                "R": round(R, 4),
                "verified_ids": [e["id"] for e in evs],
            }
            # 撤回不回溯读法下的最终状态版本
            V_final = sum(1 for e in evs if e["state"] != "retracted")
            P_final = (sum(e["p"] for e in evs if e["state"] != "retracted") / V_final) if V_final else 0.0
            rnd_terms[t]["R_clawback"] = round(
                W_V * V_final + W_P * P_final + W_F * F - W_H * h
                - W_W * retro["W"] - W_U * retro["U"] - W_G * retro["G"], 4)

        # 个体点数
        per = defaultdict(lambda: defaultdict(dict))
        cum = defaultdict(float)
        for t in self.rounds:
            retro = self._retro.get(t, {"false_checks": defaultdict(float)})
            for m in sorted(self.members):
                pos = 0.0
                detail = defaultdict(float)
                for e in first_verified.get(t, []):
                    if e["actor"] == m:
                        pos += B_PRODUCE * e["q"]; detail["produce"] += B_PRODUCE * e["q"]
                        if e["p"] >= PROVENANCE_FULL:
                            pos += B_PROVENANCE; detail["provenance"] += B_PROVENANCE
                for e in self.events.values():
                    for r in e["verifiers"]:
                        if r["round"] == t and r["actor"] == m:
                            b = B_REPRODUCE if r["mode"] == "reproduce" else B_VERIFY
                            pos += b * r["q"]; detail["verify"] += b * r["q"]
                    for ch in e["challenges"]:
                        if ch["actor"] == m and ch["round"] == t:
                            pos += 2.0; detail["challenge"] += 2.0
                            if e["state"] == "retracted":
                                pos += B_CORRECT; detail["correct"] += B_CORRECT
                neg = -3.0 * retro["false_checks"].get(m, 0.0)
                if neg:
                    detail["false_check"] += neg
                r = pos + neg
                if cfg["cap_mode"] == "absolute":
                    before = cum[m]
                    cum[m] = min(before + r, cfg["cmax"])
                    growth = cum[m] - before
                else:
                    growth = min(r, cfg["cmax"])
                    cum[m] = cum[m] + growth
                per[t][m] = {"pos": round(pos, 4), "neg": round(neg, 4),
                             "r": round(r, 4), "growth_used": round(growth, 4),
                             "c": round(cum[m], 4),
                             "detail": {k: round(x, 3) for k, x in detail.items()}}
            self.per = per
            self.cum = cum

        self.rnd_terms = rnd_terms
        self.total_R = round(sum(x["R"] for x in rnd_terms.values()), 4)
        self.total_R_clawback = round(sum(x["R_clawback"] for x in rnd_terms.values()), 4)

    # -- 输出 ---------------------------------------------------------------
    def report(self):
        out = []
        out.append("=" * 78)
        out.append("DeSci 协作系统 v0 —— 红队裁判读数")
        out.append(f"配置: c_max={self.cfg['cmax']}  H单位={self.cfg['h_unit']}  "
                   f"F取值={self.cfg['f_mode']}  点数上限读法={self.cfg['cap_mode']}")
        out.append(f"事件数={len(self.events)}  任务数={len(self.tasks)}  轮次数={len(self.rounds)}  "
                   f"成员={sorted(self.members)}")
        out.append("=" * 78)
        out.append(f"{'轮':>3} {'V':>4} {'P':>6} {'F用':>5} {'F报':>5} {'F导':>5} "
                   f"{'H':>7} {'W':>4} {'U':>4} {'G':>4} {'R_t':>9} {'R_回溯':>9}")
        for t in self.rounds:
            d = self.rnd_terms[t]
            out.append(f"{t:>3} {d['V']:>4.0f} {d['P']:>6.3f} {d['F_used']:>5.1f} "
                       f"{d['F_reported']:>5.1f} {d['F_derived']:>5.1f} "
                       f"{d['H_input']:>7.2f} {d['W']:>4.1f} {d['U']:>4.1f} {d['G']:>4.1f} "
                       f"{d['R']:>9.3f} {d['R_clawback']:>9.3f}")
        out.append("-" * 78)
        out.append(f"总 R = {self.total_R:.3f}   总 R(最终状态回溯) = {self.total_R_clawback:.3f}")
        out.append("")
        out.append("个体贡献点（每轮 r_i 与累计 c_i）:")
        for t in self.rounds:
            for m in sorted(self.per[t]):
                d = self.per[t][m]
                if abs(d["r"]) > 1e-9:
                    out.append(f"  轮{t} {m:>3}: r={d['r']:>7.3f}  c={d['c']:>7.3f}  {d['detail']}")
        if not any(abs(self.per[t][m]["r"]) > 1e-9 for t in self.rounds for m in self.per[t]):
            out.append("  （无）")
        out.append("")
        if self.ambiguities:
            out.append(f"规则歧义命中 {len(self.ambiguities)} 条:")
            for a in self.ambiguities:
                out.append(f"  - {a}")
        if self.violations:
            out.append(f"非法事件 {len(self.violations)} 条（不计分）:")
            for v in self.violations:
                out.append(f"  ! {v}")
        else:
            out.append("合法性: 通过（未触发任何机械约束）")
        uniq = sorted(set(self.self_reported))
        out.append(f"未被裁判核验的自报字段 {len(uniq)} 类:")
        for s in uniq[:20]:
            out.append(f"  ~ {s}")
        out.append("=" * 78)
        return "\n".join(out)

    def as_json(self):
        return {
            "config": self.cfg,
            "rounds": {str(t): self.rnd_terms[t] for t in self.rounds},
            "total_R": self.total_R,
            "total_R_clawback": self.total_R_clawback,
            "individual": {str(t): {m: self.per[t][m] for m in self.per[t]} for t in self.rounds},
            "violations": self.violations,
            "ambiguities": self.ambiguities,
            "self_reported_fields": sorted(set(self.self_reported)),
            "counts": {"events": len(self.events), "tasks": len(self.tasks),
                       "members": len(self.members)},
        }


def main(argv):
    args, paths = [], []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--json":
            args.append(a)
            i += 1
        elif a in ("--cmax", "--h-unit", "--f-mode", "--cap-mode"):
            if i + 1 >= len(argv):
                print(f"缺参数: {a}", file=sys.stderr); return 1
            val = argv[i + 1]
            if a == "--cmax":
                CFG["cmax"] = float(val)
            elif a == "--h-unit":
                if val not in ("hours", "minutes"):
                    print("--h-unit 只能是 hours|minutes", file=sys.stderr); return 1
                CFG["h_unit"] = val
            elif a == "--f-mode":
                if val not in ("reported", "derived", "auto"):
                    print("--f-mode 只能是 reported|derived|auto", file=sys.stderr); return 1
                CFG["f_mode"] = val
            else:
                if val not in ("absolute", "per-round"):
                    print("--cap-mode 只能是 absolute|per-round", file=sys.stderr); return 1
                CFG["cap_mode"] = val
            i += 2
        elif a in ("-h", "--help"):
            print(__doc__); return 0
        else:
            paths.append(a); i += 1
    if not paths:
        print(__doc__); return 1
    run = Run(paths, dict(CFG))
    if "--json" in args:
        print(json.dumps(run.as_json(), ensure_ascii=False, indent=2))
    else:
        print(run.report())
    return 2 if run.violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
