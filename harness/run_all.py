"""본 실험 전체 실행: 3 정책 x 3 작업 x 3 반복 = 27회. 순차 실행(병렬이면 시간 측정이 오염됨).
순서는 고정 시드로 섞어 시간대·캐시 상태 편향이 한 조건에 몰리지 않게 한다."""
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
rng = random.Random(20261016)
trials = [(p, t, r) for r in (1, 2, 3) for t in ("T1", "T2", "T3") for p in ("P0", "P1", "P2")]
rng.shuffle(trials)
for i, (p, t, r) in enumerate(trials, 1):
    print(f"[{i}/{len(trials)}] {p} {t} r{r}", flush=True)
    out = subprocess.run([sys.executable, str(HERE / "run_trial.py"), p, t, str(r)],
                         capture_output=True, text=True, encoding="utf-8")
    print(out.stdout.strip() or out.stderr.strip()[-300:], flush=True)
