"""Run one complete backend suite per process and record every round."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from xml.etree import ElementTree


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path)
    parser.add_argument("--rounds", type=int, default=120)
    parser.add_argument("--first-round", type=int, default=1)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    guard = Path(__file__).resolve().with_name("guard")
    root = args.output.resolve()
    results = root / "backend-results"
    results.mkdir(parents=True)
    environment = {
        key: value for key, value in os.environ.items()
        if not key.upper().startswith(("YUNO_", "TURSO_", "PYTEST_"))
        and key.upper() not in ("PYTHONPATH", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
    }
    environment.update(PYTHONPATH=str(guard), NO_PROXY="127.0.0.1,localhost,::1")

    def run(number):
        mode = "sqlite" if number % 2 else "libsql"
        stem = f"{number:03d}-{mode}"
        report = results / (stem + ".xml")
        start = perf_counter()
        with TemporaryDirectory(prefix=stem + "-", dir=root) as temp:
            env = dict(environment, TEMP=temp, TMP=temp, TMPDIR=temp, YUNO_DB_DRIVER=mode)
            with (results / (stem + ".log")).open("wb") as log:
                proc = subprocess.run(
                    [sys.executable, "-m", "pytest", "tests", "-q",
                     "-p", "no:cacheprovider", "--basetemp", str(Path(temp) / "pytest"),
                     "--junitxml", str(report)],
                    cwd=args.repo, env=env, stdout=log, stderr=subprocess.STDOUT,
                    timeout=240, check=False,
                )
        counts = dict(tests=0, failures=0, errors=0, skipped=0)
        if report.exists():
            for suite in ElementTree.parse(report).iter("testsuite"):
                for key in counts:
                    counts[key] += int(suite.get(key, "0"))
        return {
            "round": number, "driver": mode, "seconds": round(perf_counter() - start, 2),
            "exit_code": proc.returncode, **counts,
            "passed": proc.returncode == 0 and counts["tests"] > 0
                      and not any(counts[key] for key in ("failures", "errors", "skipped")),
        }

    all_passed = True
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rounds = range(args.first_round, args.first_round + args.rounds)
        futures = {pool.submit(run, number): number for number in rounds}
        with (root / "backend-rounds.jsonl").open("x", encoding="utf-8") as ledger:
            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception as error:
                    result = {"round": futures[future], "passed": False, "error": str(error)}
                line = json.dumps(result)
                if not result["passed"]:
                    all_passed = False
                    for log in results.glob(f'{result["round"]:03d}-*.log'):
                        print(log.read_text(encoding="utf-8", errors="replace")[-10000:], flush=True)
                ledger.write(line + "\n")
                ledger.flush()
                print(line, flush=True)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
