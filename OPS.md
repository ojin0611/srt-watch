# OPS — 원격 운영 핸드북

이 문서 하나만 보면 srt-watch (GitHub Actions) 의 상태 점검, 테스트 알림 발송,
서비스 일시중단/재개를 모두 할 수 있다. 이 저장소 URL 을 새로운 AI 어시스턴트나
다른 PC 의 본인에게 보여줄 때, 이 문서가 진입점이 된다.

## 이 저장소는 private 이다

리포 내용을 읽으려면 반드시 아래 전제를 만족해야 한다. 웹 브라우저 로그인만으로는
부족하고, 명령행 도구가 인증되어 있어야 한다.

## ⚠️ 사전작업 (절대 빼먹지 말 것) — `gh` 를 `github.com` 쪽으로 고정

> 이 저장소 소유자(@ojin0611) 는 평소 `oss.navercorp.com` (사내 GHES) 을 `gh` 기본
> 호스트로 쓴다. 이 상태에서 아래 치트시트의 명령을 그냥 실행하면 **사내 GHES 로
> 질의가 나가서 엉뚱하게 실패한다** (리포 not found, 권한 에러, 토큰 무효 등).
>
> 따라서 어떤 명령을 돌리기 전이든, 반드시 **github.com 을 사용하도록 먼저
> 고정**해야 한다. 아래 둘 중 하나.

**방법 A — 이번 셸 세션 동안만 환경변수로 고정 (제일 안전)**

```sh
export GH_HOST=github.com
export REPO=ojin0611/srt-watch
```

이 두 줄을 해당 터미널에서 한 번 실행하고, 이후 치트시트 명령을 그대로 쓰면 된다.
새 터미널을 열면 다시 export 해야 한다.

**방법 B — `gh` 의 기본 호스트 자체를 github.com 으로 스위치 (영구)**

```sh
gh auth switch -h github.com -u ojin0611
```

사내 환경에서 `oss.navercorp.com` 도 다시 써야 한다면 언제든 `gh auth switch -h
oss.navercorp.com -u <사내계정>` 로 되돌릴 수 있다.

**방법 A 를 쓸 경우라도** 혹시 `export` 를 까먹고 돌렸을 때를 대비해, 뒤의 치트시트
모든 `gh ...` 명령 대신 `GH_HOST=github.com gh ...` 처럼 **한 줄 앞에 prefix** 로
박아두는 것도 안전한 습관이다.

### 전제 최종 체크

```sh
GH_HOST=github.com gh auth status
```

출력에 다음이 포함되어야 한다:

```
github.com
  ✓ Logged in to github.com account ojin0611
  - Token scopes: ..., 'repo', ..., 'workflow', ...
```

안 되어 있으면 **이 장비의 사용자 본인이 직접** 로그인:

```sh
gh auth login -h github.com
# Protocol: HTTPS
# Authenticate Git: Yes
# Method: Login with a web browser
```

## 저장소

- URL: https://github.com/ojin0611/srt-watch
- `REPO` 축약: `ojin0611/srt-watch`

위 **사전작업** 단계의 `export REPO=...` 가 끝나 있어야 아래 치트시트의 `$REPO` 치환이
동작한다.

## 워크플로우

| 파일 | 이름 | 트리거 | 역할 |
|------|------|--------|------|
| `.github/workflows/watch.yml`        | `srt-watch`    | 10분 cron + 수동 | 본 감시 루프 — 자리 전이 감지 시 Telegram 알림 |
| `.github/workflows/notify-test.yml`  | `notify-test`  | 수동 전용       | Telegram 경로만 단독 테스트 (알림 1건 발송) |

---

## 명령 치트시트 (요청 문장 → 명령)

아래는 본인이 자주 할 요청 4가지를 그대로 옮겼다. 각 섹션의 명령만 실행하면 된다.

> **다시 한번** — 아래 명령들은 모두 `GH_HOST=github.com` 이 세팅돼 있다고 가정한다.
> 위 "사전작업" 단계(방법 A 의 `export` 두 줄 또는 방법 B 의 `gh auth switch`) 를
> **먼저 수행**하지 않으면 사내 GHES 쪽으로 질의가 나가서 실패한다. 새 터미널을
> 열었다면 `export` 두 줄부터 다시.

### 1) "실행중인 workflow 확인해줘"

등록된 워크플로우 목록과 활성/비활성 상태:

```sh
gh workflow list -R $REPO
```

최근 실행 이력 (각 워크플로우별):

```sh
gh run list -R $REPO -L 10
# 특정 워크플로우만:
gh run list -R $REPO -w watch.yml -L 10
```

현재 돌고 있는 run 이 있나:

```sh
gh run list -R $REPO --status in_progress
```

### 2) "잘 동작하고 있는지 확인해줘. 마지막에 실행된게 언제인지 봐줘" (= healthcheck)

가장 최근 `srt-watch` run 한 건 요약:

```sh
gh run list -R $REPO -w watch.yml -L 1 \
  --json databaseId,status,conclusion,createdAt,updatedAt,event,displayTitle
```

- `status` 가 `completed` 이고 `conclusion` 이 `success`
- `updatedAt` 이 **현재 시각 기준 10분 이내** (cron 주기 기준, 여유 2배 = 20분까지는 정상 범주)

두 조건 만족이면 정상.

최근 5건에 실패가 있었는지 한 번에 보기:

```sh
gh run list -R $REPO -w watch.yml -L 5 \
  --json status,conclusion,createdAt,displayTitle \
  --jq '.[] | "\(.createdAt) \(.status)/\(.conclusion // "-") \(.displayTitle)"'
```

가장 최근 run 로그에서 실제 감지 결과 확인:

```sh
latest=$(gh run list -R $REPO -w watch.yml -L 1 --json databaseId --jq '.[0].databaseId')
gh run view "$latest" -R $REPO --log | grep -E "SRT 681|available=|error|Error" | tail -10
```

기대되는 정상 로그 패턴 한 줄:

```
[YYYY-MM-DD HH:MM:SS] [SRT 681] 05월 01일, 수서~여수EXPO(10:20~13:36) 특실 매진, 일반실 매진, 예약대기 불가능 | available=False
```

`available=False` 는 "아직 매진, 알림 없음" 의미. True 로 바뀌는 순간에만 Telegram
발송. `available=` 토큰 자체가 안 찍히면 서버/라이브러리 쪽 이상이므로 `TESTING.md`
참조.

### 3) "테스트 알림 보내봐줘"

`notify-test` 워크플로우를 수동 디스패치. 실제 매진 상태와 무관하게 Telegram 한
건이 `📍 출처: GitHub Actions (run ...)` 꼬리와 함께 날아간다.

```sh
gh workflow run notify-test.yml -R $REPO

# 5~10초 후 결과 확인
sleep 10
gh run list -R $REPO -w notify-test.yml -L 1 \
  --json status,conclusion,databaseId,createdAt
```

`conclusion: success` + Telegram 도착 확인 = 알림 경로 정상.

### 4) "서비스 종료해줘" (= 일시중단)

자리 감시를 멈추고 더이상 Telegram 알림이 오지 않게 한다. **리포와 시크릿은 그대로
유지**되어 나중에 `enable` 한 줄로 바로 복구 가능.

```sh
gh workflow disable watch.yml -R $REPO
# notify-test 는 cron 이 없어 수동 호출 안 하면 돌지 않으므로 굳이 disable 불필요.
# 굳이 한다면:
gh workflow disable notify-test.yml -R $REPO
```

중단 확인:

```sh
gh workflow list -R $REPO
# watch.yml 쪽 state 가 disabled_manually 로 나오면 정상
```

### 5) "서비스 다시 시작" (재개)

```sh
gh workflow enable watch.yml -R $REPO
# 필요 시
gh workflow enable notify-test.yml -R $REPO
```

다음 cron tick 까지 기다리거나 즉시 한 번 돌려보려면:

```sh
gh workflow run watch.yml -R $REPO
```

---

## 시크릿 관리

Actions 에 등록된 이름만 확인 (값은 조회 불가):

```sh
gh secret list -R $REPO
```

교체(rotation) 필요 시 — 예: Telegram 봇 토큰 변경:

```sh
echo -n "새-토큰" | gh secret set TG_BOT_TOKEN -R $REPO
```

맥북 Keychain 에서 그대로 옮기고 싶을 때:

```sh
for pair in srt-id:SRT_ID srt-pw:SRT_PW tg-bot-token:TG_BOT_TOKEN tg-chat-id:TG_CHAT_ID; do
  security find-generic-password -s "${pair%:*}" -w \
    | gh secret set "${pair#*:}" -R $REPO
done
```

시크릿 이름은 4개 고정: `SRT_ID`, `SRT_PW`, `TG_BOT_TOKEN`, `TG_CHAT_ID`.
`watch.py` 의 `kc()` 가 `KC_<이름 대문자>` 환경변수를 우선 조회하므로 workflow
쪽 `env:` 매핑은 `.github/workflows/watch.yml` 참고.

## 간격 바꾸기

`.github/workflows/watch.yml` 의 `cron:` 값만 수정해서 커밋·푸시.

- 퍼블릭 리포: 무제한 Actions 분량
- 프라이빗 리포 (현재): 월 2,000분 공유 quota
  - `*/10 * * * *`: 월 ~4,320분 → 주 단위로 끊어서 쓰기엔 OK
  - `*/15 * * * *`: 월 ~2,880분 → 한계 근처
  - `*/30 * * * *`: 월 ~1,440분 → 여유
  - `*/5  * * * *`: 월 ~8,640분 → 중간 고갈

## 완전 삭제 (주의)

리포와 시크릿, Actions 이력까지 전부 날리려는 경우에만. 되돌릴 수 없음.

```sh
gh repo delete $REPO --yes
```

일반적인 "잠시 쉬자" 는 위 **4)** 의 `workflow disable` 로 충분하다.

## 로컬(맥북) launchd 상황

현재 비활성. GA 로 완전히 이관됨. 재설치가 필요하면 `README.md` 의 "launchd 상시
실행" 절차를 따른다. 로컬과 GA 를 동시에 돌리면 전이 시점 근처에서 알림이 두 번
올 수 있다(이후엔 각자 dedup).
