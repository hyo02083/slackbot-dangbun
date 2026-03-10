# slackbot-dangbun

매월 1일 당번을 자동으로 알려주는 Slack 봇입니다.

## 기능

- **월간 자동 알림** — 매월 1일 10:00에 해당 월 당번을 태그하여 채널에 공지
- **슬래시 커맨드로 관리** — 채널에서 직접 당번 순서 조회/추가/삭제/변경 가능
- **멤버 추가 시 자동 순서 배정** — 새로 추가된 멤버는 자동으로 가장 마지막 순서에 배정

## 슬래시 커맨드

| 커맨드 | 설명 |
|--------|------|
| `/당번` | 전체 당번 순서 + 사용법 확인 |
| `/당번 추가 이름 U슬랙ID [순서], ...` | 멤버 추가 (여러 명 가능, `[순서]`는 선택값 — 생략 시 맨 뒤에 추가) |
| `/당번 삭제 U슬랙ID, ...` | 멤버 삭제 (여러 명 가능, `/당번 상세`에서 ID 확인) |
| `/당번 순서변경 이름1,이름2,...` | 순서 재배치 |
| `/당번 상세` | 전체 순서 + 슬랙ID 확인 |

## 설치 및 실행

### 1. Slack App 설정

1. [Slack API](https://api.slack.com/apps)에서 앱 생성
2. **Socket Mode** 활성화 → App-Level Token(`xapp-...`) 생성
3. **OAuth & Permissions** → Bot Token Scopes에 `chat:write`, `commands` 추가
4. **Slash Commands** → `/당번` 커맨드 등록
5. 워크스페이스에 앱 설치 → Bot Token(`xoxb-...`) 복사
6. 메시지를 보낼 채널에 봇 초대

### 2. 환경 설정

```bash
cp .env.example .env
```

`.env` 파일에 토큰과 채널 ID를 입력합니다.

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_CHANNEL_ID=C0XXXXXXXXX
```

### 3. 당번 명단 설정

`leaders.json` 파일이 없어도 봇이 처음 실행될 때 자동으로 빈 파일(`[]`)을 생성합니다.
이후 `/당번 추가 이름 U슬랙ID` 명령어로 멤버를 추가하면 됩니다. 여러 명을 한 번에 추가할 수도 있습니다.

```
/당번 추가 홍길동 U12345678, 김철수 U87654321
```

직접 파일을 만들어 초기 명단을 설정할 수도 있습니다.

```json
[
    {"month": 1, "name": "홍길동", "userId": "U12345678"},
    {"month": 2, "name": "김철수", "userId": "U87654321"}
]
```

> Slack User ID는 프로필 → ··· → **멤버 ID 복사**에서 확인할 수 있습니다.

### 4. 실행

```bash
pip install -r requirements.txt
python bot.py
```
