import os
import json
import datetime
import threading
import time

import schedule
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]
LEADERS_FILE = os.path.join(os.path.dirname(__file__), "leaders.json")

app = App(token=SLACK_BOT_TOKEN)


# --- leaders.json 읽기/쓰기 ---

def load_leaders():
    with open(LEADERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_leaders(leaders):
    with open(LEADERS_FILE, "w", encoding="utf-8") as f:
        json.dump(leaders, f, ensure_ascii=False, indent=4)


# --- 월별 메시지 전송 ---

def build_monthly_message():
    leaders = load_leaders()
    month = datetime.date.today().month
    idx = (month - 1) % len(leaders)
    leader = leaders[idx]

    ordered = leaders[idx:] + leaders[:idx]
    schedule_lines = []
    for i, l in enumerate(ordered):
        m = ((month - 1 + i) % 12) + 1
        if i == 0:
            schedule_lines.append(f"*:crown: {m}월 (이번 달): {l['name']}*")
        else:
            schedule_lines.append(f"    {m}월: {l['name']}")
    schedule_text = "\n".join(schedule_lines)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": ":rice: 이번 달 밥상머리 리더 안내", "emoji": True},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"이번 달 *{month}월* 밥상머리 리더는 "
                    f"<@{leader['userId']}>님입니다! :tada:\n"
                    f"맛있는 회식 장소 부탁드립니다 :yum:"
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*:clipboard: 전체 회식 당번 순서*\n{schedule_text}",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_순서는 {len(leaders)}개월 주기로 반복됩니다._",
                }
            ],
        },
    ]
    fallback = f"{month}월 밥상머리 리더는 {leader['name']}님입니다!"
    return blocks, fallback


def send_monthly_message():
    blocks, fallback = build_monthly_message()
    app.client.chat_postMessage(channel=CHANNEL_ID, blocks=blocks, text=fallback)
    print(f"[{datetime.date.today()}] 월간 밥상머리 메시지 전송 완료")


# --- 스케줄러 (매월 1일 09:00) ---

def run_scheduler():
    schedule.every().day.at("09:00").do(check_and_send)
    while True:
        schedule.run_pending()
        time.sleep(60)


def check_and_send():
    if datetime.date.today().day == 1:
        send_monthly_message()


# --- 슬래시 커맨드: /당번 ---

@app.command("/당번")
def handle_babsang(ack, command, respond):
    ack()
    text = command.get("text", "").strip()

    if not text or text == "조회":
        cmd_show(respond)
    elif text.startswith("추가"):
        cmd_add(text, respond)
    elif text.startswith("삭제"):
        cmd_remove(text, respond)
    elif text.startswith("순서변경"):
        cmd_reorder(text, respond)
    elif text == "이번달":
        cmd_this_month(respond)
    else:
        respond(
            ":question: 사용법:\n"
            "• `/당번` 또는 `/당번 조회` - 전체 순서 확인\n"
            "• `/당번 이번달` - 이번 달 당번 확인\n"
            "• `/당번 추가 이름 U슬랙ID` - 멤버 추가\n"
            "• `/당번 삭제 이름` - 멤버 삭제\n"
            "• `/당번 순서변경 이름1,이름2,이름3,...` - 순서 재배치"
        )


def cmd_show(respond):
    leaders = load_leaders()
    lines = [f"{i+1}. {l['name']} (<@{l['userId']}>)" for i, l in enumerate(leaders)]
    respond(f":clipboard: *전체 회식 당번 순서*\n" + "\n".join(lines))


def cmd_this_month(respond):
    leaders = load_leaders()
    month = datetime.date.today().month
    idx = (month - 1) % len(leaders)
    leader = leaders[idx]
    respond(f":rice: *{month}월* 밥상머리 리더는 <@{leader['userId']}> ({leader['name']})님입니다!")


def cmd_add(text, respond):
    # /당번 추가 이름 U12345
    parts = text.split()
    if len(parts) != 3:
        respond(":warning: 형식: `/당번 추가 이름 U슬랙ID`")
        return

    _, name, user_id = parts
    if not user_id.startswith("U"):
        respond(":warning: 슬랙 User ID는 U로 시작합니다. 프로필에서 멤버 ID를 복사해주세요.")
        return

    leaders = load_leaders()
    leaders.append({"month": len(leaders) + 1, "name": name, "userId": user_id})
    save_leaders(leaders)

    respond(f":white_check_mark: *{name}* (<@{user_id}>)님이 추가되었습니다. (현재 {len(leaders)}명)")


def cmd_remove(text, respond):
    # /당번 삭제 이름
    parts = text.split()
    if len(parts) != 2:
        respond(":warning: 형식: `/당번 삭제 이름`")
        return

    _, name = parts
    leaders = load_leaders()
    new_leaders = [l for l in leaders if l["name"] != name]

    if len(new_leaders) == len(leaders):
        respond(f":warning: *{name}*을(를) 찾을 수 없습니다.")
        return

    for i, l in enumerate(new_leaders):
        l["month"] = i + 1
    save_leaders(new_leaders)

    respond(f":white_check_mark: *{name}*님이 삭제되었습니다. (현재 {len(new_leaders)}명)")


def cmd_reorder(text, respond):
    # /당번 순서변경 오정민,김우진,황지원,...
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        respond(":warning: 형식: `/당번 순서변경 이름1,이름2,이름3,...`")
        return

    names = [n.strip() for n in parts[1].split(",")]
    leaders = load_leaders()
    leader_map = {l["name"]: l for l in leaders}

    missing = [n for n in names if n not in leader_map]
    if missing:
        respond(f":warning: 다음 이름을 찾을 수 없습니다: {', '.join(missing)}")
        return

    if len(names) != len(leaders):
        respond(f":warning: 현재 {len(leaders)}명인데 {len(names)}명만 입력되었습니다. 전원을 입력해주세요.")
        return

    new_leaders = []
    for i, name in enumerate(names):
        entry = leader_map[name]
        entry["month"] = i + 1
        new_leaders.append(entry)
    save_leaders(new_leaders)

    lines = [f"{i+1}. {l['name']}" for i, l in enumerate(new_leaders)]
    respond(f":white_check_mark: 순서가 변경되었습니다!\n" + "\n".join(lines))


# --- 엔트리 포인트 ---

if __name__ == "__main__":
    # 스케줄러를 백그라운드 스레드로 실행
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("Babsang bot started!")

    # Socket Mode로 슬래시 커맨드 리스닝
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
