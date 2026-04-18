#!/usr/bin/env bash
# srt-watch healthcheck — launchd 등록 여부, 최근 tick, 에러 유무를 한 번에 점검.
# 사용: ./healthcheck.sh  (정상이면 exit 0, 문제 있으면 exit 1)

set -u
BASE="$(cd "$(dirname "$0")" && pwd)"
OUT="$BASE/out.log"
ERR="$BASE/err.log"
STATE="$BASE/state.json"
LABEL="com.user.srt-watch"
FRESH_SEC=60   # 로그가 이 시간(초) 안에 갱신됐어야 정상 (StartInterval=10 기준 충분한 마진)

FAIL=0
ok()   { printf '  \033[32mOK\033[0m  %s\n' "$1"; }
bad()  { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAIL=1; }
info() { printf '  \033[36m..\033[0m  %s\n' "$1"; }

echo "== srt-watch healthcheck =="

# 1. launchd 등록 여부
if launchctl list | grep -q "$LABEL"; then
  line=$(launchctl list | grep "$LABEL")
  pid=$(awk '{print $1}' <<<"$line")
  rc=$(awk '{print $2}' <<<"$line")
  ok  "launchd 등록됨 ($line)"
  [[ "$rc" == "0" || "$rc" == "-" ]] || bad "마지막 종료코드 비정상: $rc"
else
  bad "launchd 에 $LABEL 미등록 — README.md 의 launchd 설치 절차 실행 필요"
fi

# 2. out.log 존재 및 최근 갱신 여부
if [[ -f "$OUT" ]]; then
  mtime=$(stat -f %m "$OUT")
  now=$(date +%s)
  age=$(( now - mtime ))
  if (( age <= FRESH_SEC )); then
    ok  "out.log 최근 ${age}s 전 갱신"
  else
    bad "out.log 가 ${age}s 동안 멈춰있음 (기대 ≤ ${FRESH_SEC}s)"
  fi
else
  bad "out.log 없음 — 아직 한 번도 실행되지 않았거나 권한 문제"
fi

# 3. 가장 최근 줄이 기대한 포맷인지
if [[ -f "$OUT" ]]; then
  last=$(tail -n 1 "$OUT")
  if [[ "$last" == *"[SRT 681]"* && "$last" == *"available="* ]]; then
    ok  "최근 tick 포맷 정상"
    info "$last"
  else
    bad "최근 tick 포맷 이상: $last"
  fi
fi

# 4. err.log 내 실제 에러(NotOpenSSL 경고 제외) 최근 발생 여부
if [[ -f "$ERR" ]]; then
  real_errs=$(grep -v "NotOpenSSL\|warnings.warn" "$ERR" | tail -n 5)
  if [[ -z "$real_errs" ]]; then
    ok  "err.log 에 실제 에러 없음 (NotOpenSSL 경고만)"
  else
    bad "err.log 에 에러 감지됨 (마지막 5줄):"
    printf '%s\n' "$real_errs" | sed 's/^/      /'
  fi
fi

# 5. 현재 상태 출력
if [[ -f "$STATE" ]]; then
  info "state.json: $(cat "$STATE")"
fi

echo
if (( FAIL == 0 )); then
  echo "결과: OK"
  exit 0
else
  echo "결과: FAIL"
  exit 1
fi
