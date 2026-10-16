"""results.csv + traces/*.approvals.jsonl -> results_summary.md (사전 판정식 적용). 사용: python analyze.py"""
import csv
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
rows = list(csv.DictReader(open(REPO / "results.csv", encoding="utf-8")))
cell = defaultdict(list)
for r in rows:
    cell[(r["task"], r["policy"])].append(r)

med = lambda xs: st.median(xs)
f = lambda r, k: float(r[k])
tasks, pols = ("T1", "T2", "T3"), ("P0", "P1", "P2")
out = []


def T(r, d):
    return f(r, "wall_s") + d * int(r["approvals"])


out.append("### 조건별 결과 (n=3, 중앙값 [최소–최대])\n")
out.append("| 작업 | 정책 | 해결 | 승인 횟수 | wall_s | T(5s) | T(15s) | T(30s) | output 토큰 | 턴 | 비용 $ |")
out.append("|---|---|---|---|---|---|---|---|---|---|---|")
for t in tasks:
    for p in pols:
        v = cell[(t, p)]
        solved = f"{sum(x['solved'] == 'True' for x in v)}/{len(v)}"
        def m(fn, nd=1):
            xs = [fn(x) for x in v]
            return f"{med(xs):.{nd}f} [{min(xs):.{nd}f}–{max(xs):.{nd}f}]"
        out.append(f"| {t} | {p} | {solved} | {m(lambda x: int(x['approvals']))} | {m(lambda x: f(x, 'wall_s'))} | "
                   f"{m(lambda x: T(x, 5))} | {m(lambda x: T(x, 15))} | {m(lambda x: T(x, 30))} | "
                   f"{m(lambda x: f(x, 'output_tokens'))} | {m(lambda x: f(x, 'num_turns'))} | {m(lambda x: f(x, 'cost_usd'), 3)} |")

# 판정
a_ok = b_ok = c_ok = 0
detail = []
for t in tasks:
    p0, p1 = cell[(t, "P0")], cell[(t, "P1")]
    ma0, ma1 = med([int(x["approvals"]) for x in p0]), med([int(x["approvals"]) for x in p1])
    a = ma1 <= 0.5 * ma0
    s0 = sum(x["solved"] == "True" for x in p0) / len(p0)
    s1 = sum(x["solved"] == "True" for x in p1) / len(p1)
    b = s1 >= s0
    t0, t1 = med([T(x, 15) for x in p0]), med([T(x, 15) for x in p1])
    c = t1 < t0
    a_ok += a; b_ok += b; c_ok += c
    detail.append(f"| {t} | {ma0:g} → {ma1:g} ({'충족' if a else '미충족'}) | {s0:.2f} → {s1:.2f} ({'충족' if b else '미충족'}) | "
                  f"{t0:.1f} → {t1:.1f} ({'충족' if c else '미충족'}) |")
A = a_ok >= 2
B = b_ok == 3
C = c_ok >= 2
out.append("\n### 사전 판정식 적용 (P0 → P1)\n")
out.append("| 작업 | (a) 승인 중앙값 ≤ 50% | (b) 해결률 비열등 | (c) T(15s) 중앙값 감소 |")
out.append("|---|---|---|---|")
out += detail
out.append(f"\n(a) 충족 작업 {a_ok}/3 → {'통과' if A else '실패'} · (b) {b_ok}/3 → {'통과' if B else '실패'} · (c) {c_ok}/3 → {'통과' if C else '실패'}")
out.append(f"\n**판정: {'가설 지지' if (A and B and C) else '가설 기각'}**")

# d=0 (순수 벽시계) 비교
out.append("\n### 벽시계 시간만 (d=0) P0 vs P1 vs P2 중앙값(초)\n")
out.append("| 작업 | P0 | P1 | P2 |")
out.append("|---|---|---|---|")
for t in tasks:
    out.append(f"| {t} | " + " | ".join(f"{med([f(x, 'wall_s') for x in cell[(t, p)]]):.1f}" for p in pols) + " |")

# 승인 분류
out.append("\n### 승인 요청 원문 분류 (전 조건, 승인 로그 기준)\n")
cnt = defaultdict(Counter)
examples = defaultdict(list)
for r in rows:
    lg = REPO / "traces" / f"{r['id']}.approvals.jsonl"
    if not lg.exists():
        continue
    for line in open(lg, encoding="utf-8"):
        e = json.loads(line)
        tool, inp = e["tool"], e["input"]
        if tool in ("Edit", "Write"):
            kind = "파일 편집/쓰기"
        else:
            cmd = inp.get("command", "")
            if "unittest" in cmd and any(s in cmd for s in ("&&", ";", "|", "sed ", "python -c", "2>&1")):
                kind = f"{tool}: 테스트 실행에 파이프·&&·리다이렉션 등이 붙음(좁은 규칙과 모양이 다름)"
            elif "unittest" in cmd:
                kind = f"{tool}: 단독 테스트 실행"
            else:
                kind = f"{tool}: 기타 명령"
        cnt[r["policy"]][kind] += 1
        if len(examples[kind]) < 2:
            examples[kind].append(" ".join(str(inp.get("command", inp.get("file_path", ""))).split())[:90])
kinds = sorted({k for c in cnt.values() for k in c})
out.append("| 분류 | P0 | P1 | P2 | 예시 |")
out.append("|---|---|---|---|---|")
for k in kinds:
    ex = "; ".join(f"`{e}`" for e in examples[k][:1]).replace("|", "\\|")
    out.append(f"| {k} | {cnt['P0'][k]} | {cnt['P1'][k]} | {cnt['P2'][k]} | {ex} |")

tot = defaultdict(float)
for r in rows:
    tot["cost"] += f(r, "cost_usd")
out.append(f"\n총 시도 {len(rows)}회, 비용 합계 ${tot['cost']:.2f}(API 환산 보고값), 해결 {sum(r['solved'] == 'True' for r in rows)}/{len(rows)}, 오류 종료 {sum(r['is_error'] not in ('False', '') for r in rows)}회")
(REPO / "results_summary.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
