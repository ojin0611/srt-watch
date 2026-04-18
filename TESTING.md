# TESTING — 신규 환경에서 동작까지의 조사/검증 기록

다른 PC에서 쓰던 코드를 이 맥북으로 옮기는 과정에서 두 개의 블로커를 만났고,
각각 어떻게 확인하고 우회했는지 정리한다. 재세팅 시 그대로 재현 가능하다.

## 환경 전제

- 시스템 파이썬: `/usr/bin/python3` (Python 3.9.6, Apple stock)
- 시스템 파이썬/전역 site-packages 는 건드리지 않음. 모든 의존성은 프로젝트 로컬
  `.venv/` 안에 격리.
- 비밀값은 macOS Keychain 에 저장 (`README.md` 참고).

## 셋업 단계

```sh
cd /Users/user/srt-watch
/usr/bin/python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt   # SRTrain 2.0.7, requests
```

## 블로커 1 — 역 이름 "여수EXPO" 미등록

### 증상

```
ValueError: Station "여수EXPO" not exists
```

### 조사

설치된 `SRTrain 2.0.7` 의 `STATION_CODE` 딕셔너리를 덤프:

```sh
./.venv/bin/python -c "from SRT.constants import STATION_CODE; print(list(STATION_CODE))"
```

전라선 계열(`여수EXPO`, `전주`, `순천` 등)이 전혀 포함되어 있지 않음.

업스트림 마스터(미릴리즈)의
[constants.py](https://github.com/ryanking13/SRT/blob/master/SRT/constants.py)
에는 `"여수EXPO": "0053"` 등이 추가되어 있음을 확인.

### 조치

업스트림 상수표 기준으로 `.venv/.../SRT/constants.py` 의 `STATION_CODE` 에 누락
역들을 추가. 이 수정은 venv 내부에만 존재하므로 시스템 영향 없음.

## 블로커 2 — SRT 서버의 NetFunnel 대기열 도입

### 증상

역 이름 패치 이후에도 `search_train` 호출 시 아래 에러 반복 (파라미터 무관):

```
SRT.errors.SRTResponseError: 서비스가 접속이 원활하지 않습니다.
잠시후 다시 시도하여 주시기 바랍니다.
```

### 원인 좁히기

`diag.py` 를 만들어 다양한 조합으로 호출해본 결과, 잘 알려진 `수서→부산/오늘`
조차 동일 에러 → 파라미터/역 이름 문제 아님 확인.

```sh
./.venv/bin/python diag.py
```

### 근본 원인

SRT 가 `nf.letskorail.com` 기반의 **NetFunnel** 대기열/봇차단 레이어를 도입했고,
모든 검색 요청은 여기서 발급받은 `netfunnelKey` 를 동반해야 통과함.

업스트림에는 2024-12-13 커밋 `d07c997` ("Fix search_train '정상적인 경로로 접근
부탁드립니다.' issue") 로 `SRT/netfunnel.py` 모듈과 해당 key 삽입 로직이
추가되었으나, PyPI 최신 릴리즈 `2.0.7` 에는 이 변경이 반영되어 있지 않음.

### 조치

업스트림 master 의 `SRT/*.py` 파일 일체를 받아 `.venv/.../SRT/` 에 덮어쓴다.
단, 업스트림 코드는 `requires-python = ">= 3.10"` 이고 `str | None` 등 PEP 604
신문법을 사용하므로 시스템 파이썬 3.9 에서 그대로는 임포트 불가.

→ 각 파일 최상단에 `from __future__ import annotations` 를 추가하여 모든
어노테이션을 지연 평가(문자열)로 돌려 3.9 에서 임포트 가능하게 함. 런타임 로직
자체는 match/case 등 3.10 전용 구문을 쓰지 않아 동작에 지장 없음.

재적용 방법(필요 시 재현):

```sh
mkdir -p /tmp/srt-upstream
base=https://raw.githubusercontent.com/ryanking13/SRT/master/SRT
for f in __init__.py constants.py errors.py netfunnel.py passenger.py \
         reservation.py response_data.py seat_type.py srt.py train.py; do
  curl -fsSL -o /tmp/srt-upstream/$f "$base/$f"
done

TARGET=/Users/user/srt-watch/.venv/lib/python3.9/site-packages/SRT
for f in __init__.py constants.py errors.py netfunnel.py passenger.py \
         reservation.py response_data.py seat_type.py srt.py train.py; do
  { echo 'from __future__ import annotations'; echo ''; cat /tmp/srt-upstream/$f; } > "$TARGET/$f"
done
```

의존성은 `requests` 외 추가 없음.

## 검증 시나리오

| # | 시나리오 | 확인 지점 | 결과 |
|---|-----------|-----------|------|
| 1 | 최초 실행 (session.pkl 없음) | 새 로그인 후 조회 성공, `session.pkl`/`state.json` 생성 | ✅ `[info] new login` 로그 찍히고 열차 정보 출력 |
| 2 | 재실행 (session.pkl 존재) | 기존 쿠키 재사용, `[info] new login` 미출력 | ✅ |
| 3 | 3회 연속 실행 | 각 호출 모두 200 응답, `state.json` 동일 유지 | ✅ |
| 4 | 역 이름 여수EXPO 인식 | `ValueError` 미발생 | ✅ |
| 5 | NetFunnel 통과 | `SRTResponseError` 미발생 | ✅ |

실제 로그 예시 (2026-04-18 17:33 기준):

```
[2026-04-18 17:33:21] [info] new login
[2026-04-18 17:33:21] [SRT 681] 05월 01일, 수서~여수EXPO(10:20~13:36) 특실 매진, 일반실 매진, 예약대기 불가능 | available=False
```

이 줄이 매 실행마다 찍히면 정상. `available=True` 로 전이되는 순간에 Telegram
알림이 발송된다(`STATE_FILE` 비교 기반, 중복 발송 방지).

## diag.py 사용법

동작이 다시 깨졌을 때 빠르게 파라미터/서버 중 어느 쪽이 문제인지 판정용.

```sh
./.venv/bin/python diag.py
```

잘 알려진 `수서→부산` 조차 모두 `[ERR]` 로 나오면 서버/라이브러리 쪽(예: 또 다른
안티봇 변경)이고, 특정 조합만 실패하면 해당 파라미터 문제다.
