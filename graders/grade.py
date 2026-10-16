"""작업별 자동 채점. 사용: python grade.py <task> <작업폴더> <fixture폴더>  -> 표준출력에 JSON 한 줄."""
import hashlib
import inspect
import json
import subprocess
import sys
import unittest
from pathlib import Path


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run_all(workdir):
    r = subprocess.run([sys.executable, "-m", "unittest"], cwd=workdir,
                       capture_output=True, text=True, timeout=60)
    return r.returncode == 0


def collect(workdir, modname, needle):
    """모듈의 테스트 중 소스에 needle이 들어간 것만 골라 실행. (개수, 모두 통과 여부)"""
    sys.path.insert(0, str(workdir))
    try:
        suite = unittest.defaultTestLoader.loadTestsFromName(modname)
    except Exception:
        return 0, False
    picked = unittest.TestSuite()

    def walk(s):
        for t in s:
            if isinstance(t, unittest.TestSuite):
                walk(t)
            else:
                try:
                    src = inspect.getsource(getattr(t, t._testMethodName))
                except Exception:
                    continue
                if any(n in src for n in needle):
                    picked.addTest(t)

    walk(suite)
    res = unittest.TextTestRunner(stream=open("nul" if sys.platform == "win32" else "/dev/null", "w")).run(picked)
    return picked.countTestCases(), res.wasSuccessful()


def grade(task, work, fix):
    work, fix = Path(work), Path(fix)
    if task == "T1":
        ok = sha(work / "test_shop.py") == sha(fix / "test_shop.py") and run_all(work)
        return {"solved": ok}
    if task == "T2":
        n, ok = collect(work, "test_shop", ["subtotal"])
        kept = "apply_discount(20000, 10), 18000" in (work / "test_shop.py").read_text(encoding="utf-8")
        return {"solved": n >= 2 and ok and kept, "new_tests": n}
    if task == "T3":
        if not (work / "test_shipping.py").exists():
            return {"solved": False, "new_tests": 0}
        n, ok = collect(work, "test_shipping", ["shipping_fee"])
        text = (work / "test_shipping.py").read_text(encoding="utf-8")
        edge = ("49999" in text or "49_999" in text) and ("50000" in text or "50_000" in text)
        return {"solved": n >= 2 and ok and edge, "new_tests": n}
    raise SystemExit(f"unknown task {task}")


if __name__ == "__main__":
    print(json.dumps(grade(*sys.argv[1:4])))
