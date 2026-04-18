# srt-watch

SRT #681 (2026-05-01 수서→여수EXPO) 잔여석을 주기적으로 조회하고, 매진 → 가능
전이가 감지되면 텔레그램으로 알림을 보내는 개인용 스크립트.

> **원격 운영 (상태 확인 / 테스트 알림 / 중단·재개) 은 [`OPS.md`](OPS.md) 참조.**
> GitHub Actions 로 24/7 구동 중이므로 일반적인 조작은 거의 전부 `OPS.md` 한 문서로 처리된다.
>
> ⚠️ 소유자(@ojin0611) 의 `gh` 기본 호스트는 보통 `oss.navercorp.com` 으로 잡혀 있다.
> **어떤 명령이든 실행 전에** `OPS.md` 의 "사전작업" 섹션을 반드시 먼저 수행해
> `github.com` 으로 고정해야 한다. 빼먹으면 전부 엉뚱한 호스트로 질의돼 실패한다.

## 구성

- `watch.py` — 메인 스크립트
- `requirements.txt` — `SRTrain`, `requests`
- `com.user.srt-watch.plist` — launchd 설정 (`StartInterval=10`)
- `.venv/` — 프로젝트 전용 파이썬 환경 (시스템 파이썬 오염 방지용)
- `state.json` — 직전 조회 시 `available` 상태 저장 (알림 중복 방지)
- `session.pkl` — SRT 로그인 세션 쿠키 (매 실행마다 갱신)

## 시크릿 관리 (macOS Keychain)

`watch.py` 는 환경변수나 파일 대신 **로그인 Keychain** 에서 `security(1)` 로
값을 읽는다. 서비스 이름 기준:

| 서비스 이름     | 용도                               |
|----------------|------------------------------------|
| `srt-id`       | SRT 홈페이지 로그인 ID             |
| `srt-pw`       | SRT 홈페이지 비밀번호              |
| `tg-bot-token` | Telegram Bot API 토큰              |
| `tg-chat-id`   | 알림을 받을 Telegram chat id       |

### 등록 (새 맥북으로 옮길 때)

로그인한 사용자 계정으로 아래를 실행. `-U` 는 이미 같은 서비스명이 있을 경우
덮어쓰기.

```sh
security add-generic-password -a "$USER" -s srt-id       -w 'SRT_ID_VALUE'        -U
security add-generic-password -a "$USER" -s srt-pw       -w 'SRT_PW_VALUE'        -U
security add-generic-password -a "$USER" -s tg-bot-token -w 'TG_BOT_TOKEN_VALUE'  -U
security add-generic-password -a "$USER" -s tg-chat-id   -w 'TG_CHAT_ID_VALUE'    -U
```

비밀번호에 `!` 등 셸 특수문자가 있으면 반드시 **홑따옴표**로 감싸거나 `\` 로
이스케이프해야 그대로 저장된다.

### 조회 / 확인

```sh
security find-generic-password -s srt-id -w
security find-generic-password -s srt-pw -w
security find-generic-password -s tg-bot-token -w
security find-generic-password -s tg-chat-id -w
```

`watch.py` 내부에서도 동일 명령을 `subprocess` 로 호출한다. 첫 호출 시
Keychain 이 GUI 로 접근 허용을 물어볼 수 있고, "항상 허용" 을 선택해 둬야
launchd 자동 실행이 막히지 않는다.

### 삭제

```sh
security delete-generic-password -s srt-id
security delete-generic-password -s srt-pw
security delete-generic-password -s tg-bot-token
security delete-generic-password -s tg-chat-id
```

## 실행

### 수동 실행

```sh
./.venv/bin/python watch.py
```

결과:
- stdout: `[YYYY-MM-DD HH:MM:SS] <열차정보> | available=<bool>`
- 매진 → 가능 전이 시 Telegram 알림 발송
- `state.json`, `session.pkl` 갱신

### launchd 상시 실행

`com.user.srt-watch.plist` 의 `ProgramArguments` 가 `.venv/bin/python` 을 가
리키도록 되어 있다. 설치:

```sh
cp com.user.srt-watch.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.user.srt-watch.plist
launchctl enable gui/$UID/com.user.srt-watch
```

로그는 프로젝트 루트 `out.log`, `err.log` 에 쌓인다.

해제:

```sh
launchctl bootout gui/$UID/com.user.srt-watch
rm ~/Library/LaunchAgents/com.user.srt-watch.plist
```

### GitHub Actions 백업 스케줄

`.github/workflows/watch.yml` 이 10분 간격 cron + 수동 디스패치로 동일한
`watch.py` 를 클라우드 러너에서 돌린다. 로컬 launchd 가 어떤 이유로(슬립/전원/에러)
멈춰도 GA 가 보조로 감시를 이어간다.

- Private repo 이므로 월 2,000분 무료 quota 공유. 10분 cron 기준 월 ~4,320분이지만,
  대상 열차 출발 전까지만 돌리면 기간 내 quota 안에 들어옴.
- 시크릿은 Keychain 이 아니라 **Actions secrets** 로 주입되며 (`SRT_ID`, `SRT_PW`,
  `TG_BOT_TOKEN`, `TG_CHAT_ID`), `watch.py` 의 `kc()` 가 환경변수
  `KC_<서비스명 대문자>` 를 우선 검사하고 없을 때만 Keychain 으로 폴백한다.
- `state.json` 은 `actions/cache` 로 run 간 영속화 (매진→가능 전이 dedup 유지).
- 수동 실행: `gh workflow run watch.yml -R ojin0611/srt-watch`
- 최근 run 로그: `gh run list -R ojin0611/srt-watch`, `gh run view <id> --log`
- 새 맥북으로 이전 시 시크릿 재등록:

  ```sh
  for pair in srt-id:SRT_ID srt-pw:SRT_PW tg-bot-token:TG_BOT_TOKEN tg-chat-id:TG_CHAT_ID; do
    security find-generic-password -s "${pair%:*}" -w \
      | gh secret set "${pair#*:}" -R ojin0611/srt-watch
  done
  ```

- 스케줄 변경은 `.github/workflows/watch.yml` 의 `cron:` 값만 수정 후 커밋·푸시.
  참고로 퍼블릭 리포는 60일 비활성 시 cron 자동 중단 (프라이빗은 이 제한 없음).

## 로그 확인 방법

### 수동 실행 중

`watch.py` 는 stdout/stderr 로 바로 찍는다. 포어그라운드로 돌리면 즉시 확인 가능.

```sh
./.venv/bin/python watch.py
```

### launchd 백그라운드 상시 실행 중

실시간 팔로우:

```sh
tail -f /Users/user/srt-watch/out.log
```

에러만:

```sh
tail -f /Users/user/srt-watch/err.log
```

최근 N줄만:

```sh
tail -n 50 /Users/user/srt-watch/out.log
```

### 정상 동작을 알리는 로그 패턴

정상일 때 `out.log` 에는 `StartInterval`(10초) 간격으로 아래 형식의 한 줄이 쌓인다:

```
[YYYY-MM-DD HH:MM:SS] [SRT 681] 05월 01일, 수서~여수EXPO(HH:MM~HH:MM) 특실 매진, 일반실 매진, 예약대기 불가능 | available=False
```

포인트:

- **시각이 꾸준히 갱신**되면 launchd 가 스케줄을 타고 있고 스크립트가 죽지 않고
  있다는 뜻.
- **`available=False`** 가 유지된다 = 매진 상태 감지 중, 아직 알림 트리거 조건
  아님.
- **`available=True`** 로 바뀌는 첫 순간에 Telegram 알림이 발송되고 이후에는
  상태가 같으므로 다시 보내지 않음. 이 전이를 `state.json` 이 기억한다.
- 처음 한 번만 `[info] new login` 이 찍히고, 이후 실행에서는 안 찍혀야 정상
  (쿠키 재사용). 매번 찍힌다면 세션 저장/로드가 깨진 것.

### 에러 해석

- `err.log` 의 `NotOpenSSLWarning` 은 무해 (LibreSSL + urllib3 경고, 동작 영향 없음).
- `SRTError` / `SRTResponseError` 가 계속 찍히면 → `TESTING.md` 의 블로커 2 원인과
  유사. SRT 가 또 다른 안티봇 레이어를 추가했을 수 있으므로 업스트림 마스터에서
  최신 변경을 받아 재패치.
- `KeyError` / `ValueError: Station ... not exists` → SRT 역 코드 추가가 필요.
  `TESTING.md` 의 블로커 1 절차 참고.
- `subprocess.CalledProcessError` 가 `security find-generic-password` 에서 발생
  하면 Keychain 항목 누락. 위 "등록" 절차 재실행.

## Healthcheck

### 한 방에 체크 — `healthcheck.sh`

```sh
./healthcheck.sh
```

다음을 한꺼번에 확인한다:

1. `com.user.srt-watch` 가 launchd 에 등록돼 있고 마지막 종료코드가 0 인가
2. `out.log` 가 최근 60초 이내에 갱신됐는가 (= 스크립트가 죽지 않고 tick 중인가)
3. 가장 최근 한 줄이 `[SRT 681] ... available=...` 포맷을 따르는가
4. `err.log` 에 NotOpenSSL 경고 외의 실제 에러가 남아 있지 않은가
5. 현재 `state.json` 값(available 여부)

정상이면 exit code `0`, 하나라도 실패하면 `1`. cron/launchd 에서 감시용으로 체이닝해도 되고, 평소엔 그냥 수동으로 가끔 돌리면 된다.

출력 예 (정상):

```
== srt-watch healthcheck ==
  OK  launchd 등록됨 (-  0  com.user.srt-watch)
  OK  out.log 최근 4s 전 갱신
  OK  최근 tick 포맷 정상
  ..  [2026-04-18 17:49:53] [SRT 681] 05월 01일, 수서~여수EXPO(10:20~13:36) 특실 매진, 일반실 매진, 예약대기 불가능 | available=False
  OK  err.log 에 실제 에러 없음 (NotOpenSSL 경고만)
  ..  state.json: {"available": false}

결과: OK
```

### 수동 원라이너 모음

빠르게 눈으로 확인하고 싶을 때:

```sh
# launchd 등록 상태 (PID + 마지막 exit code)
launchctl list | grep com.user.srt-watch

# 실행 중인지 + 마지막 exit code + 총 실행 횟수
launchctl print gui/$UID/com.user.srt-watch | grep -E "state|runs|last exit"

# 로그가 살아있는지 (시각이 갱신되면 OK)
tail -n 3 out.log

# 에러 있는지 (NotOpenSSL 경고 제외)
grep -v "NotOpenSSL\|warnings.warn" err.log | tail

# 현재 감지 상태
cat state.json
```

### 텔레그램 알림 경로만 수동 점검

봇 토큰/chat id 가 살아있는지, 네트워크 전송 자체가 되는지 확인:

```sh
./.venv/bin/python -c '
import subprocess, requests
kc=lambda s: subprocess.check_output(["security","find-generic-password","-s",s,"-w"]).decode().strip()
r=requests.post(f"https://api.telegram.org/bot{kc(\"tg-bot-token\")}/sendMessage",
  data={"chat_id":kc("tg-chat-id"),"text":"srt-watch healthcheck ping"},timeout=10)
print(r.status_code, r.json().get("ok"))
'
```

`200 True` 가 나오면 알림 경로 정상.

### state.json / session.pkl 리셋

상태 꼬였다 싶을 때:

```sh
rm -f /Users/user/srt-watch/state.json /Users/user/srt-watch/session.pkl
```

다음 실행에서 새 로그인이 이뤄지고 상태가 다시 쌓인다.
