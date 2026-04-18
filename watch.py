#!/usr/bin/env python3
"""매분 실행되어 SRT #681 (2026-05-01 수서→여수EXPO) 잔여석을 확인하고,
매진→가능 전이 시 텔레그램으로 알림을 보낸다."""

import json
import os
import pathlib
import pickle
import subprocess
import sys
from datetime import datetime

import requests
from SRT import SRT
from SRT.errors import SRTError


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

TRAIN_NO = "681"
DEP = "수서"
ARR = "여수EXPO"
DATE = "20260501"
TIME = "100000"  # 이 시각 이후 출발 열차 조회

BASE = pathlib.Path(__file__).resolve().parent
STATE_FILE = BASE / "state.json"
SESSION_FILE = BASE / "session.pkl"


def kc(service: str) -> str:
    """시크릿 조회: 환경변수 우선, 없으면 macOS Keychain.

    - 환경변수 키는 ``KC_<서비스명 대문자, '-' → '_'>`` 형식 (예: `srt-id` → `KC_SRT_ID`).
    - CI (GitHub Actions) 에서는 Keychain 이 없으므로 환경변수만 사용.
    - 로컬 macOS 에서는 환경변수를 세팅 안 하면 기존대로 Keychain 에서 읽음.
    """
    env_key = "KC_" + service.upper().replace("-", "_")
    if env_key in os.environ:
        return os.environ[env_key]
    return subprocess.check_output(
        ["security", "find-generic-password", "-s", service, "-w"]
    ).decode().strip()


def _source_tag() -> str:
    """알림 발송 주체를 문자열로 식별.

    - GitHub Actions 러너: `GITHUB_ACTIONS=true` 가 기본 세팅됨
    - 그 외(로컬 macOS 등): hostname 으로 표시
    """
    if os.environ.get("GITHUB_ACTIONS") == "true":
        run_id = os.environ.get("GITHUB_RUN_ID", "")
        return f"GitHub Actions (run {run_id})" if run_id else "GitHub Actions"
    import socket
    host = socket.gethostname().split(".")[0]
    return f"MacBook ({host})" if host else "MacBook"


def notify(text: str) -> None:
    token = kc("tg-bot-token")
    chat = kc("tg-chat-id")
    msg = f"{text}\n\n📍 출처: {_source_tag()}"
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat, "text": msg},
        timeout=10,
    ).raise_for_status()


def get_srt() -> "SRT":
    """저장된 세션 쿠키가 있으면 재사용하고, 없거나 만료되면 새 로그인."""
    srt = SRT(kc("srt-id"), kc("srt-pw"), auto_login=False)
    if SESSION_FILE.exists():
        try:
            srt._session.cookies.update(pickle.loads(SESSION_FILE.read_bytes()))
            srt.is_login = True
            return srt
        except Exception as e:
            print(f"[{ts()}] [info] cookie load failed: {e}", file=sys.stderr)
    srt.login()
    SESSION_FILE.write_bytes(pickle.dumps(srt._session.cookies))
    print(f"[{ts()}] [info] new login", file=sys.stderr)
    return srt


def main() -> int:
    srt = get_srt()
    try:
        trains = srt.search_train(DEP, ARR, DATE, TIME, available_only=False)
    except SRTError:
        # 세션 만료 등 — 캐시 폐기 후 1회 재로그인
        SESSION_FILE.unlink(missing_ok=True)
        srt = get_srt()
        trains = srt.search_train(DEP, ARR, DATE, TIME, available_only=False)
    # 매번 갱신된 쿠키를 다시 저장 (만료 연장)
    SESSION_FILE.write_bytes(pickle.dumps(srt._session.cookies))
    target = next((t for t in trains if t.train_number == TRAIN_NO), None)

    if target is None:
        print(f"[{ts()}] [warn] #{TRAIN_NO} not found in results", file=sys.stderr)
        return 0

    available = target.general_seat_available() or target.special_seat_available()
    prev = (
        json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {"available": False}
    )

    print(f"[{ts()}] {target} | available={available}", flush=True)

    if available and not prev.get("available"):
        notify(f"🚄 SRT #{TRAIN_NO} 자리 생김!\n{target}\nhttps://etk.srail.kr/")

    STATE_FILE.write_text(json.dumps({"available": available}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
