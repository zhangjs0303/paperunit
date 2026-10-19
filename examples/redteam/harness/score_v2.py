#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""score_v2.py — DeSci 协作系统 v0.2 修订版奖励函数的确定性裁判

v0.2 与 v0 的区别（全部由红队模拟的结果驱动，见 ../2026-10-18_reward_hacking_红队报告.md）：
  1. 结算点从 verify 移到 merge：只有 merge 过的验收标准才计分，merge 的独立 checker 才有贡献点。
  2. 奖励挂在**预先登记、加权、幂等**的验收标准上，不挂在事件数/复核数上；拆分任务不增加分数。
  3. provenance 从"加分项"改成"gate"：字段不全的 artifact 不计入 P̃。
  4. 失败测试：每轮有界（最多算 2 次），且必须由独立 check 的 reject 产生。
  5. H/W/U/G/F 等自报量全部移出目标函数（retrospect 只留文字）。
  6. 撤回回溯（clawback）：retract 后对应 credit 归零；报告 as-of 与 final 两套读数。
  7. 个体贡献 = 验收标准权重 × 0.5/0.5 的 fate-sharing 分摊；不再有角色权重 b=1/2/3。

用法:
    python3 score_v2.py task_events.jsonl
    python3 score_v2.py x.jsonl --json
退出码: 0 = 合法; 2 = 存在非法事件
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

KINDS = {"rerun", "prediction", "counterexample"}
OPS = {"propose", "produce", "verify", "challenge", "merge", "retract", "retrospect"}
W_V, W_P, W_F = 3.0, 2.0, 1.0
F_FULL = 2.0          # 每轮最多需要多少次独立确认的失败才拿满 F̃
SHARE_PRODUCER = 0.5  # fate-sharing: 生产者
SHARE_CHECKER = 0.5   # 独立 checker


def _s(x) -> str:
    return x if isinstance(x, str) else ""


def _num(x, default=None):
    if isinstance(x, bool):
        return default
    return float(x) if isinstance(x, (int, float)) else default


class Run:
    def __init__(self, paths):
        self.violations: list[str] = []
        self.ambiguities: list[str] = []
        self.tasks: dict[str, dict] = {}
        self.events: dict[str, dict] = {}
        self.order: list[tuple[int, int, dict]] = []
        self.rounds: list[int] = []
        self._load(paths)
        self._play()
        self._score()

    # -- 载入 ---------------------------------------------------------------
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
                    rnd = ev.get("round")
                    if not isinstance(rnd, int) or isinstance(rnd, bool) or rnd < 0:
                        self.violations.append(f"{path}:{lineno} round 非法")
                        continue
                    if not _s(ev.get("id")):
                        self.violations.append(f"{path}:{lineno} id 缺失")
                        continue
                    ev["__line__"] = f"{path}:{lineno}"
                    seq += 1
                    self.order.append((rnd, seq, ev))
        self.order.sort(key=lambda x: (x[0], x[1]))
        self.rounds = sorted({r for r, _, _ in self.order})
        last = -1
        for rnd, _, ev in self.order:
            if rnd < last:
                self.violations.append(f"{ev['__line__']} 轮次倒退")
            last = rnd

    def _bad(self, ev, msg):
        self.violations.append(f"{ev.get('__line__')}/{ev.get('id')}: {msg}")

    def _amb(self, ev, msg):
        tag = f"{ev.get('id')}: {msg}"
        if tag not in self.ambiguities:
            self.ambiguities.append(tag)

    # -- 回放 ---------------------------------------------------------------
    def _play(self):
        for rnd, _, ev in self.order:
            op, actor = _s(ev.get("op")), _s(ev.get("actor"))
            if op not in OPS:
                self._bad(ev, f"未知 op {op!r}（允许: propose/produce/verify/challenge/merge/retract/retrospect）")
                continue
            if not actor:
                self._bad(ev, "actor 缺失")
                continue
            getattr(self, f"_op_{op}")(ev, actor, rnd)

    def _op_propose(self, ev, actor, rnd):
        task = _s(ev.get("task"))
        crits = ev.get("criteria")
        if not task:
            return self._bad(ev, "propose 缺 task")
        if task in self.tasks:
            return self._bad(ev, f"任务 {task} 重复 propose")
        if not isinstance(crits, list) or not crits:
            return self._bad(ev, "propose 必须给出非空 criteria 列表")
        ids, wsum = set(), 0.0
        for c in crits:
            if not isinstance(c, dict):
                return self._bad(ev, "criterion 必须是对象")
            cid, w, kind, test = _s(c.get("id")), _num(c.get("w")), _s(c.get("kind")), _s(c.get("test"))
            if not cid or cid in ids:
                return self._bad(ev, f"criterion id 非法或重复: {cid!r}")
            if w is None or w <= 0:
                return self._bad(ev, f"criterion {cid} 的权重 w 必须 > 0")
            if kind not in KINDS:
                return self._bad(ev, f"criterion {cid} 的 kind 必须是 {sorted(KINDS)}")
            if len(test.strip()) < 10:
                return self._bad(ev, f"criterion {cid} 缺少可执行验收步骤 test")
            ids.add(cid); wsum += w
        if abs(wsum - 1.0) > 1e-3:
            return self._bad(ev, f"criteria 权重之和必须为 1（容差 1e-3，当前 {wsum}）")
        self.tasks[task] = {"owner": actor, "round": rnd, "criteria": {c["id"]: c for c in crits},
                            "num": len(crits), "question": _s(ev.get("question"))}

    def _op_produce(self, ev, actor, rnd):
        eid, task, cid = _s(ev.get("id")), _s(ev.get("task")), _s(ev.get("criterion"))
        if eid in self.events:
            return self._bad(ev, f"事件 id {eid} 重复")
        if task not in self.tasks:
            return self._bad(ev, f"produce 的任务 {task!r} 未先 propose")
        crit = self.tasks[task]["criteria"].get(cid)
        if crit is None:
            return self._bad(ev, f"produce 的 criterion {cid!r} 不在任务预注册标准里")
        art = ev.get("artifact")
        if not isinstance(art, dict):
            return self._bad(ev, "produce 缺 artifact 对象")
        if crit["kind"] in ("rerun", "counterexample"):
            if not _s(art.get("hash")) or not _s(art.get("cmd")):
                return self._bad(ev, f"criterion {cid} 是 {crit['kind']}，artifact 必须含 hash 与 cmd（可复跑）")
        if crit["kind"] == "prediction":
            if not _s(art.get("prediction")) or not _s(art.get("threshold")):
                return self._bad(ev, f"criterion {cid} 是 prediction，artifact 必须含 prediction 与 threshold")
        prov = ev.get("prov")
        if not isinstance(prov, dict):
            return self._bad(ev, "produce 缺 prov 对象")
        src = prov.get("sources")
        if not isinstance(src, list) or not src or not all(isinstance(s, str) and s.strip() for s in src):
            return self._bad(ev, "prov.sources 必须是非空字符串列表")
        if _num(prov.get("ai_share")) is None or not 0 <= _num(prov.get("ai_share")) <= 1:
            return self._bad(ev, "prov.ai_share 缺失或不在 [0,1]")
        if not isinstance(prov.get("version"), int):
            return self._bad(ev, "prov.version 必须是整数")
        self.events[eid] = {
            "id": eid, "round": rnd, "actor": actor, "task": task, "criterion": cid,
            "kind": crit["kind"], "w": crit["w"], "prov_ok": self._prov_ok(art, prov),
            "artifact": art, "state": "draft", "verifiers": [], "first_verify_round": None,
            "merged_round": None, "merger": None, "retract_round": None, "challenges": [],
        }

    @staticmethod
    def _prov_ok(art, prov) -> bool:
        """v0.2 的 P̃ 是 gate：字段齐备才算数，字段不齐不扣分也不加分。"""
        if not isinstance(prov.get("sources"), list) or not prov["sources"]:
            return False
        if _num(prov.get("ai_share")) is None or not isinstance(prov.get("version"), int):
            return False
        has_rerun = bool(_s(art.get("hash"))) and bool(_s(art.get("cmd")))
        has_pred = bool(_s(art.get("prediction"))) and bool(_s(art.get("threshold")))
        return has_rerun or has_pred

    def _op_verify(self, ev, actor, rnd):
        tgt = self.events.get(_s(ev.get("target")))
        if tgt is None:
            return self._bad(ev, "verify 的 target 不存在")
        if actor == tgt["actor"]:
            return self._bad(ev, "违反最小约束：不得复核自己的产出")
        if tgt["state"] not in ("draft", "disputed"):
            return self._bad(ev, f"verify 不能在状态 {tgt['state']} 上执行")
        decision = _s(ev.get("decision"))
        if decision not in ("accept", "reject"):
            return self._bad(ev, "verify.decision 必须是 accept/reject")
        evid = _s(ev.get("evidence"))
        if len(evid.strip()) < 20:
            return self._bad(ev, "verify 缺检查记录（evidence < 20 字符；v0.2 要求可复述的检查记录）")
        rr = ev.get("rerun")
        if tgt["kind"] in ("rerun", "counterexample"):
            if not isinstance(rr, dict) or not isinstance(rr.get("ok"), bool) or not _s(rr.get("own_hash")):
                return self._bad(ev, "rerun 类 claim 的 verify 必须给出自己的复跑结果 rerun{ok, own_hash}")
        tgt["verifiers"].append({"actor": actor, "round": rnd, "decision": decision, "ev": ev})
        if decision == "accept":
            tgt["state"] = "verified"
            if tgt["first_verify_round"] is None:
                tgt["first_verify_round"] = rnd
        else:
            tgt["state"] = "disputed"

    def _op_challenge(self, ev, actor, rnd):
        tgt = self.events.get(_s(ev.get("target")))
        if tgt is None:
            return self._bad(ev, "challenge 的 target 不存在")
        if tgt["state"] == "retracted":
            return self._bad(ev, "challenge 已 retract 的事件")
        claim, evid = _s(ev.get("claim")), _s(ev.get("evidence"))
        if len(claim.strip()) < 20 or len(evid.strip()) < 20:
            return self._bad(ev, "challenge 需要具体疑点与证据（各 >= 20 字符）")
        tgt["challenges"].append({"actor": actor, "round": rnd, "resolved": None})
        tgt["state"] = "disputed"

    def _op_merge(self, ev, actor, rnd):
        tgt = self.events.get(_s(ev.get("target")))
        if tgt is None:
            return self._bad(ev, "merge 的 target 不存在")
        if tgt["state"] != "verified":
            return self._bad(ev, f"merge 只能在 verified 上执行（当前 {tgt['state']}）")
        if tgt["merged_round"] is not None:
            return self._bad(ev, "merge 重复执行（v0.2：同一 artifact 只结算一次）")
        if len(_s(ev.get("own_words")).strip()) < 40:
            return self._bad(ev, "merge 缺“用自己的话说明假设/证据/局限”（< 40 字符）")
        if actor == tgt["actor"]:
            return self._bad(ev, "v0.2 要求 merge 由非生产者执行（整合者负责核实）")
        checkers = [v for v in tgt["verifiers"] if v["decision"] == "accept"]
        if not checkers:
            return self._bad(ev, "merge 缺独立 checker（accept verify）")
        tgt["merged_round"] = rnd
        tgt["merger"] = actor
        for ch in tgt["challenges"]:
            if ch["resolved"] is None:
                ch["resolved"] = ("merge", rnd)

    def _op_retract(self, ev, actor, rnd):
        tgt = self.events.get(_s(ev.get("target")))
        if tgt is None:
            return self._bad(ev, "retract 的 target 不存在")
        if tgt["state"] not in ("verified", "disputed", "draft"):
            return self._bad(ev, f"retract 不能在状态 {tgt['state']} 上执行")
        if len(_s(ev.get("reason")).strip()) < 10:
            return self._bad(ev, "retract 缺理由")
        tgt["state"] = "retracted"
        tgt["retract_round"] = rnd

    def _op_retrospect(self, ev, actor, rnd):
        """v0.2：复盘仍是操作，但 H/W/U/G/F 等自报数字不进入奖励；
        裁判只接受并忽略，不接受任何会改分的数字字段。"""
        for k in ("H", "W", "U", "G", "F"):
            if k in ev:
                self._amb(ev, f"retrospect.{k} 在 v0.2 中不参与计分（只进复盘文本）")
        self.notes = getattr(self, "notes", [])
        self.notes.append((rnd, actor, _s(ev.get("notes"))))

    # -- 计分 ---------------------------------------------------------------
    def _score(self):
        self.credited: dict[tuple[str, str], dict] = {}
        for e in self.events.values():
            if e["merged_round"] is None:
                continue
            key = (e["task"], e["criterion"])
            if key in self.credited:
                self._amb({"id": e["id"], "__line__": "-"},
                          "同一 criterion 有第二个被 merge 的 artifact；v0.2 只结算第一个（幂等）")
                continue
            self.credited[key] = e

        self.rnd = {}
        for t in self.rounds:
            met_asof = met_final = 0.0
            p_num = p_den = 0
            fails = 0
            for e in self.credited.values():
                task = e["task"]
                wt = self.tasks[task]["criteria"][e["criterion"]]["w"] / len(self.tasks)
                if e["merged_round"] == t:
                    met_asof += wt
                    if e["state"] != "retracted":
                        met_final += wt
                    p_den += 1
                    if e["prov_ok"]:
                        p_num += 1
            for e in self.events.values():
                for v in e["verifiers"]:
                    if v["round"] == t and v["decision"] == "reject":
                        fails += 1
            F = min(1.0, fails / F_FULL)
            P = (p_num / p_den) if p_den else 0.0
            self.rnd[t] = {
                "Vtilde_asof": round(met_asof, 4), "Vtilde_final": round(met_final, 4),
                "Ptilde": round(P, 4), "Ftilde": round(F, 4),
                "fails": fails, "merged": p_den,
                "R_asof": round(W_V * met_asof + W_P * P + W_F * F, 4),
                "R_final": round(W_V * met_final + W_P * P + W_F * F, 4),
            }

        # 个体贡献：fate-sharing
        self.credit_person = defaultdict(float)
        self.credit_person_final = defaultdict(float)
        for (task, cid), e in self.credited.items():
            wt = self.tasks[task]["criteria"][cid]["w"] / len(self.tasks)
            acc = [v["actor"] for v in e["verifiers"] if v["decision"] == "accept"]
            checkers = sorted(set(acc))
            share = SHARE_CHECKER / len(checkers) if checkers else 0.0
            add = {e["actor"]: wt * SHARE_PRODUCER}
            for c in checkers:
                add[c] = add.get(c, 0.0) + share * wt
            for p, val in add.items():
                self.credit_person[p] += val
                if e["state"] != "retracted":
                    self.credit_person_final[p] += val

        # 诊断指标
        self.diag = {
            "events_per_criterion": round(len(self.events) / max(1, len(self.credited)), 3),
            "n_produce": len(self.events), "n_credited": len(self.credited),
            "n_retract": sum(1 for e in self.events.values() if e["state"] == "retracted"),
            "n_reject": sum(1 for e in self.events.values() for v in e["verifiers"] if v["decision"] == "reject"),
            "n_challenge": sum(len(e["challenges"]) for e in self.events.values()),
            "n_merge": sum(1 for e in self.credited.values()),
        }

        # v0.2.1：整段试验级（trial-level）分数。
        # 逐轮求和的 R_t 里，P̃ 与 F̃ 每轮都能重新拿满，所以"总 R"随轮数无界；
        # 红队 rt5 用 6 轮把总 R 刷到 21.0。把 P̃/F̃ 定义为"截至试验结束"的累积量后，
        # 总 R = 3Ṽ + 2P̃ + F̃ ∈ [0, 6]，与轮数无关。
        self.trial = {}
        if self.credited:
            v_asof = sum(d["Vtilde_asof"] for d in self.rnd.values())
            v_final = sum(d["Vtilde_final"] for d in self.rnd.values())
            prov_ok = sum(1 for e in self.credited.values() if e["prov_ok"])
            p_trial = prov_ok / len(self.credited)
            f_trial = min(1.0, self.diag["n_reject"] / F_FULL)
            self.trial = {
                "Vtilde_trial_asof": round(v_asof, 4),
                "Vtilde_trial_final": round(v_final, 4),
                "Ptilde_trial": round(p_trial, 4),
                "Ftilde_trial": round(f_trial, 4),
                "R_trial_asof": round(W_V * v_asof + W_P * p_trial + W_F * f_trial, 4),
                "R_trial_final": round(W_V * v_final + W_P * p_trial + W_F * f_trial, 4),
            }
        else:
            self.trial = {"Vtilde_trial_asof": 0.0, "Vtilde_trial_final": 0.0,
                          "Ptilde_trial": 0.0, "Ftilde_trial": 0.0,
                          "R_trial_asof": 0.0, "R_trial_final": 0.0}

    # -- 输出 ---------------------------------------------------------------
    def report(self):
        o = ["=" * 78, "DeSci 协作系统 v0.2 —— 裁判读数（结算点=merge；标准预注册加权幂等）",
             f"任务={len(self.tasks)}  produce={self.diag['n_produce']}  "
             f"merge 结算={self.diag['n_credited']}  轮次={len(self.rounds)}", "=" * 78]
        o.append(f"{'轮':>3} {'Ṽ_asof':>9} {'Ṽ_final':>9} {'P̃':>6} {'F̃':>6} "
                 f"{'fail':>5} {'merge':>6} {'R_asof':>9} {'R_final':>9}")
        for t in self.rounds:
            d = self.rnd[t]
            o.append(f"{t:>3} {d['Vtilde_asof']:>9.3f} {d['Vtilde_final']:>9.3f} "
                     f"{d['Ptilde']:>6.3f} {d['Ftilde']:>6.3f} {d['fails']:>5} {d['merged']:>6} "
                     f"{d['R_asof']:>9.3f} {d['R_final']:>9.3f}")
        o.append("-" * 78)
        o.append(f"总 R_asof={sum(d['R_asof'] for d in self.rnd.values()):.3f}   "
                 f"总 R_final={sum(d['R_final'] for d in self.rnd.values()):.3f}")
        o.append("")
        o.append("个体贡献（fate-sharing: 生产者 0.5 / checker 0.5，按 criterion 权重）：")
        if self.credit_person:
            for m in sorted(self.credit_person):
                o.append(f"  {m:>3}: asof={self.credit_person[m]:.3f}  final={self.credit_person_final[m]:.3f}")
        else:
            o.append("  （无）")
        o.append("")
        o.append("试验级分数 v0.2.1（推荐官方口径：P̃/F̃ 只结算一次，不随轮数重复）：")
        o.append(f"  Ṽ_trial(asof)={self.trial['Vtilde_trial_asof']:.3f}  "
                 f"Ṽ_trial(final)={self.trial['Vtilde_trial_final']:.3f}  "
                 f"P̃_trial={self.trial['Ptilde_trial']:.3f}  F̃_trial={self.trial['Ftilde_trial']:.3f}")
        o.append(f"  R_trial_asof={self.trial['R_trial_asof']:.3f}   "
                 f"R_trial_final={self.trial['R_trial_final']:.3f}   （上界 6.0，与轮数无关）")
        o.append("")
        o.append("诊断（不是奖励项，只用于复盘/停止条件）：")
        for k, v in self.diag.items():
            o.append(f"  {k} = {v}")
        if self.ambiguities:
            o.append(f"\n规则歧义命中 {len(self.ambiguities)} 条：")
            o.extend(f"  - {a}" for a in self.ambiguities)
        if self.violations:
            o.append(f"\n非法事件 {len(self.violations)} 条（不计分）：")
            o.extend(f"  ! {v}" for v in self.violations)
        else:
            o.append("\n合法性: 通过（未触发任何机械约束）")
        o.append("=" * 78)
        return "\n".join(o)

    def as_json(self):
        return {"rounds": {str(t): self.rnd[t] for t in self.rounds},
                "total_R_asof": round(sum(d["R_asof"] for d in self.rnd.values()), 4),
                "total_R_final": round(sum(d["R_final"] for d in self.rnd.values()), 4),
                "trial": self.trial,
                "individual_asof": {m: round(v, 4) for m, v in self.credit_person.items()},
                "individual_final": {m: round(v, 4) for m, v in self.credit_person_final.items()},
                "diagnostics": self.diag, "violations": self.violations,
                "ambiguities": self.ambiguities}


def main(argv):
    paths, as_json = [], False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--json":
            as_json = True
            i += 1
        elif a in ("-h", "--help"):
            print(__doc__); return 0
        else:
            paths.append(a); i += 1
    if not paths:
        print(__doc__); return 1
    run = Run(paths)
    print(json.dumps(run.as_json(), ensure_ascii=False, indent=2) if as_json else run.report())
    return 2 if run.violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
