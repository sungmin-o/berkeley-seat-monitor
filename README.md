# UC Berkeley 빈자리 → Telegram 알림

Python 3.12 표준 라이브러리와 GitHub Actions만 사용합니다. 서버, Berkeley 로그인, CalNet 비밀번호, 유료 문자 서비스가 필요 없습니다. Telegram 앱 푸시이며 SMS 문자가 아닙니다.

**현재 검증 상태 (2026-11-15):** 공식 Class Search의 PHYSICS 137B 강의 정보가 공개 검색에 노출되는 것은 확인했습니다. 하지만 이 제작 환경에서 실제 강의 URL과 `/node/522854` 접속은 **HTTP 403**이었습니다. 따라서 이 저장소는 설치 가능한 완성 코드지만, 실제 GitHub runner에서 Berkeley 접근 및 HTML 형식 확인을 먼저 통과해야 합니다. 실제 데이터 수집/Telegram 전송을 끝까지 성공했다고 주장하지 않습니다. 검색엔진 캐시를 실시간 데이터로 사용하지 않습니다.

## 1. 저장소 업로드

1. GitHub에서 새 저장소를 만듭니다. 이 폴더의 **내용 전체**를 기본 브랜치(보통 `main`)에 올립니다. `.github/workflows/monitor.yml`도 포함해야 합니다. ZIP 자체만 업로드하면 실행되지 않습니다.
2. 터미널 업로드 예시(이 폴더에서 실행):

   ```sh
   git init
   git add .
   git commit -m "Add Berkeley seat monitor"
   git branch -M main
   git remote add origin https://github.com/YOUR_NAME/YOUR_REPO.git
   git push -u origin main
   ```

3. Settings → Actions → General에서 Actions 사용을 허용합니다. 워크플로는 상태 파일 저장에 `contents: write` 권한을 사용합니다. 조직 정책이나 브랜치 보호가 봇 커밋을 금지하면 상태 저장이 실패합니다. 이를 해결하기 위해 과도한 권한의 PAT를 추가하지 마세요. 이 도구용 별도 저장소를 권장합니다.

## 2. Telegram 비밀값 등록

1. Telegram 공식 **@BotFather**에서 `/newbot`으로 봇을 만들고 토큰을 받습니다. 토큰은 비밀번호처럼 다루세요.
2. 생성한 봇과 개인 대화를 열고 **Start**를 누른 다음 메시지를 하나 보냅니다.
3. 아래 스크립트를 로컬 터미널에서 실행합니다. 토큰 입력은 화면에 표시되지 않습니다. 출력된 개인 대화 ID를 사용하세요. 그룹 알림은 이 안내의 범위 밖입니다.

   ```sh
   python3 telegram_setup.py
   ```

   결과가 없으면 봇에 메시지를 다시 보내세요. 기존 webhook이 있으면 getUpdates와 충돌할 수 있으므로 이 용도의 새 봇을 사용하세요. 토큰이 들어간 URL을 브라우저 주소창이나 저장소에 넣지 마세요.

4. GitHub 저장소 Settings → Secrets and variables → Actions → New repository secret에 등록합니다.

   | Name | Value |
   | --- | --- |
   | `TELEGRAM_BOT_TOKEN` | BotFather가 발급한 토큰 |
   | `TELEGRAM_CHAT_ID` | 위에서 확인한 대화 ID |

   `GITHUB_TOKEN`은 Actions가 자동 발급합니다. 별도 GitHub 토큰을 만들 필요 없습니다. `.env`를 커밋하지 마세요. 토큰을 노출했다면 BotFather에서 폐기/재발급하세요.

## 3. 강의 및 section 설정

`config.json`의 `sections` 배열에 강의별 객체를 넣습니다. 최대 20개이며 강의마다 1초 간격을 둡니다.

```json
{
  "sections": [
    {
      "term": "2026 Fall",
      "course": "PHYSICS 137B",
      "class_number": "23064",
      "url": "https://classes.berkeley.edu/content/2026-fall-physics-137b-001-lec-001",
      "min_open_seats": 1
    }
  ]
}
```

PHYS 137B의 공식 과목 표기는 **PHYSICS 137B**입니다. 이 예시는 **2026 Fall LEC 001, Class #23064**이며 다음 학기 예시가 아닙니다. 원하는 학기 강의를 [공식 검색](https://classes.berkeley.edu/)에서 찾아 URL, 학기, 과목명, Class #를 모두 바꾸세요. Class #는 5자리 문자열이며 `001` 같은 Section 번호나 Drupal node ID와 다릅니다. 학기마다 바뀔 수 있습니다. 숫자만으로 강의를 조회하는 익명 공식 API는 이번 검증에서 확인하지 못했으므로 **공식 상세 페이지 URL과 Class #를 함께 설정**합니다. discussion/lab도 해당 section의 상세 URL과 Class #가 필요합니다. 이름만 같다는 이유로 다른 section으로 대체하지 않습니다.

첫 성공 확인 때 이미 기준 이상이면 1회 알립니다. 계속 열려 있는 동안 빈자리 수가 달라져도 재알림하지 않습니다. 성공 확인에서 기준 미만으로 내려간 뒤 다시 기준 이상이면 재알림합니다. 오류는 닫힘으로 기록하지 않습니다. `min_open_seats`는 총 빈자리 기준입니다. 예약석, 전공/학년 제한, 대기자 우선권, 연결된 lab/discussion, 등록 기간은 판정하지 않습니다. 직접 CalCentral에서 등록 가능 여부를 확인하세요. 자동 수강신청은 하지 않습니다.

## 4. 첫 실행 — 반드시 순서대로

Actions → Berkeley seat monitor → Run workflow에서 기본 브랜치를 선택합니다.

1. `test-telegram`: 연결 성공 메시지가 휴대폰에 도착하는지 확인합니다. 앱/OS 알림도 켜세요.
2. `dry-run`: 실제 Berkeley 페이지 접근과 강의 identity/인원 파싱을 확인합니다. Telegram 전송이나 상태 변경을 하지 않습니다.
3. `check`: 실제 감시를 시작합니다. 처음 열려 있으면 알림이 갑니다. 닫혀 있으면 조용히 성공합니다.

`dry-run` 실패는 설치 완료가 아닙니다. 로그가 `check/delivery/state failed`라면 접근 차단, HTML 변경, 잘못된 학기/Class # 등을 확인하세요. 현재 403 문제 때문에 특히 중요합니다. 403에서 성공할 때까지 빠르게 재시도하거나 차단을 우회하지 마세요. 정상 브라우저에서 공식 페이지가 열리는지 확인한 뒤 나중에 수동 재실행합니다. 사이트가 JavaScript 전용으로 바뀌거나 enrollment 블록을 HTML에서 제거하면 parser 수정이 필요합니다. 누락을 0석으로 바꾸지 않습니다.

로컬 데이터 접근 확인:

```sh
python3 -m unittest discover -s tests -v
python3 monitor.py --dry-run
```

## 실행 간격과 비용

기본값은 UTC 매시 03, 13, 23, 33, 43, 53분(10분 간격)입니다. 더 빠른 간격은 cron을 `3-58/5 * * * *`로 바꿉니다. GitHub의 최소 간격은 **5분**입니다. 스케줄은 기본 브랜치에 파일이 있어야 실행됩니다. fork한 저장소에서는 Actions/스케줄을 직접 활성화해야 할 수 있습니다.

실행은 지연되거나 혼잡 시 누락될 수 있고, 기본 데이터 자체도 지연될 수 있어 알림 도착 시간을 보장하지 않습니다. 공개 저장소는 60일 동안 저장소 활동이 없으면 스케줄이 비활성화됩니다. 상태가 바뀔 때만 커밋하므로 봇 커밋이 영구 활성화를 보장한다고 가정하지 마세요. GitHub Actions 화면과 이메일 실패 알림도 확인하세요.

공개 저장소의 표준 GitHub hosted runner는 무료입니다. 비공개 저장소는 플랜의 포함 사용량/과금 대상입니다. 10분 간격은 하루 144회, 30일에 약 4,320회이고 실행 시간 외 요금 계산 방식은 계정의 현재 청구 화면에서 확인하세요. 감시 종료 시 Actions → 해당 workflow → Disable workflow를 선택하세요. 실행별 대기 루프나 상시 서버는 없습니다.

## 중복 방지와 오류 처리

`monitor-state.json`을 기본 브랜치에 저장합니다. 캐시 만료에 의존하지 않습니다. 토큰/대화 ID는 저장하지 않습니다. 공개 저장소라면 강의 설정과 열림/닫힘 이력도 공개됩니다. 여러 실행은 concurrency 그룹으로 직렬화하고 상태 파일의 SHA로 충돌을 감지합니다. 이 파일을 임의로 삭제하거나 초기화하면 열려 있는 강의가 다시 알림됩니다. 설정을 바꾸면 새 감시 대상으로 취급합니다.

일반 중복은 억제하지만 **exactly-once 전송은 보장하지 않습니다**. Telegram 전송 성공 후 상태 커밋 전에 실행이 중단되면 다음 실행에서 중복될 수 있습니다. Telegram이 메시지를 받았으나 응답이 유실된 경우에도 같습니다. 메시지 손실을 줄이기 위해 성공 응답 전에는 열림 상태를 저장하지 않으며, Telegram POST는 자동 재시도하지 않습니다. 실패 시 다음 예약 실행에서 다시 시도합니다.

Berkeley GET만 일시 오류(429/일부 5xx/네트워크)에 최대 3번 제한 재시도합니다. 403은 즉시 실패합니다. 요청 timeout 25초, 응답 크기 제한, HTTPS 호스트 제한, redirect 금지를 적용합니다. Telegram/GitHub 인증 요청의 원문 오류나 URL을 로그에 출력하지 않습니다. 일부 강의 오류 시 나머지는 계속 확인하고 최종 실행은 실패 처리합니다. 사이트 접근 자체가 실패할 때 Telegram 오류 알림을 반복 발송하지 않습니다. **GitHub의 Actions 실패 알림을 켜세요.** 상태 초기화 실패는 전체 실행을 중단합니다.

토큰은 check/test 단계에만 주입하고 PR/push 이벤트로 실행하지 않습니다. workflow는 두 GitHub 공식 action의 커밋 SHA를 고정합니다. 의존 패키지는 없습니다. 저장소 쓰기 권한자는 코드를 바꿀 수 있으므로 신뢰할 사람만 협업자로 추가하세요.

## 검증 범위와 공식 근거

- [PHYSICS 137B Fall 2026 공식 강의 정보](https://classes.berkeley.edu/node/522854): Class #23064 및 공개 enrollment 라벨 확인. 검색에 노출된 숫자를 현재 좌석 수로 간주하지 않았습니다. 직접 요청은 403이므로 실제 HTML 캡처 기반 테스트는 수행하지 못했습니다.
- [Berkeley Registrar 수강신청 안내](https://www.registrar.berkeley.edu/enrollment/how-to-enroll-in-classes/): 예약석/수강 조건과 대기자 규칙 확인.
- [Berkeleytime SIS API 개발 문서](https://docs.berkeleytime.com/core/api-sandbox/index.html): SIS API 개발 도구는 API 키를 사용합니다. 공개 Class Search와 인증 SIS API를 구별해야 합니다. 지원되는 익명 실시간 JSON API를 확보했다고 주장하지 않습니다.
- [GitHub 예약 실행 공식 문서](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule): 최소 간격, 지연, 기본 브랜치, 60일 조건.
- [GitHub Actions 요금](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
- [GitHub Contents API](https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents): 상태 파일 저장/충돌 검증.
- [Telegram Bot API](https://core.telegram.org/bots/api#sendmessage): sendMessage, chat_id, 응답 ok 판정.

단위 테스트는 **합성 HTML**과 모의 네트워크로 section 혼동, 누락/변경/차단 페이지 거부, 중복 억제, 재열림, 전송 실패 시 상태 보존, 토큰 비노출을 확인합니다. 실제 GitHub 저장소는 생성/배포하지 않았고 사용자 비밀값도 등록하지 않았습니다.
