#!/usr/bin/env python3
"""서버 에러의 원인을 좁히기 위한 진단 스크립트.
수서→여수EXPO / 수서→부산 / 오늘 / 먼 미래 조합을 순차 시도."""

import subprocess
from datetime import datetime, timedelta
from SRT import SRT
from SRT.errors import SRTError


def kc(s):
    return subprocess.check_output(
        ["security", "find-generic-password", "-s", s, "-w"]
    ).decode().strip()


srt = SRT(kc("srt-id"), kc("srt-pw"))

today = datetime.now()
cases = [
    # (label, dep, arr, date, time)
    ("수서→부산 오늘",        "수서", "부산",     today.strftime("%Y%m%d"),              "000000"),
    ("수서→부산 내일",        "수서", "부산",     (today + timedelta(days=1)).strftime("%Y%m%d"), "000000"),
    ("수서→목포 2026-05-01",  "수서", "목포",     "20260501", "100000"),
    ("수서→여수EXPO 내일",     "수서", "여수EXPO", (today + timedelta(days=1)).strftime("%Y%m%d"), "000000"),
    ("수서→여수EXPO 2026-05-01", "수서", "여수EXPO", "20260501", "100000"),
]

for label, dep, arr, date, t in cases:
    try:
        trains = srt.search_train(dep, arr, date, t, available_only=False)
        print(f"[OK ] {label}: {len(trains)}건 — 예: {trains[0] if trains else '(없음)'}")
        # Look for train #681 if applicable
        t681 = [tr for tr in trains if tr.train_number == "681"]
        if t681:
            print(f"       #681 발견: {t681[0]}")
    except SRTError as e:
        print(f"[ERR] {label}: {type(e).__name__}: {e}")
    except Exception as e:
        print(f"[EXC] {label}: {type(e).__name__}: {e}")
