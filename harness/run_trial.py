"""한 번의 시도(trial) 실행: python run_trial.py <정책 P0|P1|P2> <작업 T1|T2|T3> <반복 번호>

- fixture 원본을 새 폴더(저장소 밖 _work/)로 복사해서 쓴다.
- claude -p 를 정책별 allow 규칙만 바꿔 실행한다. 모델·프롬프트·옵션은 고정.
- 승인 요청은 모의 승인자(approver_mcp.py)가 전부 허용하며 횟수를 기록한다.
- 결과 한 줄을 results.csv에 덧붙이고 원본 기록을 traces/에 저장한다.
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORK = REPO.parent / "_work"
MODEL = "claude-sonnet-5-5"

POLICIES = {
    "P0": [],  # 규칙 없음: 편집·Bash 모두 승인 요청
    # Windows에서는 모델이 Bash 대신 PowerShell 도구를 써서(파일럿에서 확인) 두 도구 규칙을 모두 둔다.
    "P1": ["Edit", "Write",
           "Bash(python -m unittest *)", "Bash(python -m unittest)",
           "PowerShell(python -m unittest *)", "PowerShell(python -m unittest)"],  # 좁은 allow
    "P2": ["Edit", "Write", "Bash", "PowerShell"],  # 넓은 allow
}

PROMPTS = {
    "T1": "이 폴더의 테스트가 실패한다. test_shop.py는 수정하지 말고 소스를 고쳐서 "
          "`python -m unittest`가 통과하게 해라. 마지막에 테스트를 실행해 결과를 확인해라.",
    "T2": "price.py의 subtotal에 대한 단위 테스트를 2개 이상 test_shop.py에 추가하고, "
          "`python -m unittest`를 실행해 새 테스트가 통과하는지 확인해라. "
          "기존 discount 테스트는 건드리지 마라.",
    "T3": "shipping.py의 shipping_fee에 대한 경계값 테스트(49999원, 50000원 포함)를 "
          "새 파일 test_shipping.py로 만들고, `python -m unittest`를 실행해 "
          "새 테스트가 통과하는지 확인해라.",
}


def main(policy, task, rep):
    tid = f"{policy}_{task}_r{rep}"
    wd = WORK / tid
    if wd.exists():
        shutil.rmtree(wd)
    shutil.copytree(REPO / "fixture", wd)

    log = wd.parent / f"{tid}.approvals.jsonl"
    log.unlink(missing_ok=True)
    mcp_cfg = wd.parent / f"{tid}.mcp.json"
    mcp_cfg.write_text(json.dumps({"mcpServers": {"approver": {
        "command": sys.executable,
        "args": [str(REPO / "harness" / "approver_mcp.py")],
        "env": {"APPROVER_LOG": str(log)}}}}), encoding="utf-8")
    settings = wd.parent / f"{tid}.settings.json"
    settings.write_text(json.dumps({"permissions": {"allow": POLICIES[policy]}}), encoding="utf-8")

    cmd = ["claude", "-p", PROMPTS[task],
           "--model", MODEL,
           "--permission-mode", "manual",
           "--permission-prompt-tool", "mcp__approver__approve",
           "--setting-sources", "project",
           "--settings", str(settings),
           "--strict-mcp-config", "--mcp-config", str(mcp_cfg),
           "--disable-slash-commands", "--no-session-persistence",
           "--max-budget-usd", "1.0",
           "--output-format", "stream-json", "--verbose"]
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDECODE")}
    env["PYTHONUTF8"] = "1"

    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=wd, env=env, capture_output=True, text=True,
                       encoding="utf-8", timeout=900)
    wall = time.perf_counter() - t0

    (REPO / "traces").mkdir(exist_ok=True)
    (REPO / "traces" / f"{tid}.stream.jsonl").write_text(p.stdout, encoding="utf-8")
    if log.exists():
        shutil.copy(log, REPO / "traces" / f"{tid}.approvals.jsonl")
    if p.returncode != 0:
        (REPO / "traces" / f"{tid}.stderr.txt").write_text(p.stderr, encoding="utf-8")

    result, edits = {}, 0
    for line in p.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "result":
            result = ev
        if ev.get("type") == "assistant":
            for blk in ev.get("message", {}).get("content", []):
                if blk.get("type") == "tool_use" and blk.get("name") in ("Edit", "Write", "MultiEdit"):
                    edits += 1
    approvals = sum(1 for _ in open(log, encoding="utf-8")) if log.exists() else 0
    g = subprocess.run([sys.executable, "-I", str(REPO / "graders" / "grade.py"), task, str(wd),
                        str(REPO / "fixture")], capture_output=True, text=True)
    grade = json.loads(g.stdout.strip().splitlines()[-1]) if g.stdout.strip() else {"solved": None}
    u = result.get("usage", {})
    row = {
        "id": tid, "policy": policy, "task": task, "rep": rep,
        "solved": grade.get("solved"), "approvals": approvals,
        "permission_denials": len(result.get("permission_denials", [])),
        "wall_s": round(wall, 1), "duration_ms": result.get("duration_ms"),
        "num_turns": result.get("num_turns"), "edit_calls": edits,
        "input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens"),
        "cache_read": u.get("cache_read_input_tokens"), "cost_usd": result.get("total_cost_usd"),
        "is_error": result.get("is_error"), "exit": p.returncode,
    }
    out = REPO / "results.csv"
    new = not out.exists()
    with open(out, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)
    print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
