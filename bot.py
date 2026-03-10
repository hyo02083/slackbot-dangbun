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
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

app = App(token=SLACK_BOT_TOKEN)


# --- config.json 읽기/쓰기 ---

def load_config():
    if not os.path.exists(CONFIG_FILE):
        today = datetime.date.today()
        save_config({"start_year": today.year, "start_month": today.month})
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)


# --- leaders.json 읽기/쓰기 ---

def load_leaders():
    if not os.path.exists(LEADERS_FILE):
        save_leaders([])
        return []
    with open(LEADERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_leaders(leaders):
    with open(LEADERS_FILE, "w", encoding="utf-8") as f:
        json.dump(leaders, f, ensure_ascii=False, indent=4)


# --- 당번 계산 ---

def get_absolute_offset():
    """시작 시점으로부터 현재까지 몇 개월 지났는지 반환한다."""
    config = load_config()
    start_year = config.get("start_year", 2026)
    start_month = config.get("start_month", 1)
    today = datetime.date.today()
    return (today.year - start_year) * 12 + (today.month - start_month)


def get_current_duty_index(leaders):
    """현재 월의 당번 인덱스를 반환한다."""
    if not leaders:
        return -1
    return get_absolute_offset() % len(leaders)


def get_next_month_for_index(i, total):
    """리스트 인덱스 i번 사람의 다음 담당 연월을 반환한다. (year, month) 튜플."""
    current_offset = get_absolute_offset()
    remainder = current_offset % total
    if i >= remainder:
        next_offset = current_offset + (i - remainder)
    else:
        next_offset = current_offset + (total - remainder + i)
    config = load_config()
    start_year = config.get("start_year", 2026)
    start_month = config.get("start_month", 1)
    total_month = (start_month - 1) + next_offset
    year = start_year + total_month // 12
    month = (total_month % 12) + 1
    return year, month


def format_month(year, month, total):
    """인원수에 따라 월 표시 형식을 반환한다. 13명 이상이면 년도 포함."""
    if total > 12:
        return f"{year % 100}년 {month}월"
    return f"{month}월"


# --- 월별 메시지 전송 ---

def build_monthly_message():
    leaders = load_leaders()
    if not leaders:
        return None, None
    month = datetime.date.today().month
    idx = get_current_duty_index(leaders)
    leader = leaders[idx]

    total = len(leaders)
    schedule_lines = []
    for i, l in enumerate(leaders):
        y, m = get_next_month_for_index(i, total)
        month_str = format_month(y, m, total)
        if i == idx:
            schedule_lines.append(f"{i+1}. :crown: *{l['name']} — {month_str} [이번달 당번]*")
        else:
            schedule_lines.append(f"{i+1}. {l['name']} — {month_str}")
    schedule_text = "\n".join(schedule_lines)

    usage = (
        "\n\n:question: *사용법*\n"
        "• `/당번` — 전체 순서 + 사용법 확인\n"
        "• `/당번 추가` {이름} {U슬랙ID} [순서], ... — 멤버 추가 (순서 생략 시 맨 뒤)\n"
        "• `/당번 삭제` {U슬랙ID}, ... — 멤버 삭제\n"
        "• `/당번 순서변경` {이름1},{이름2},... — 순서 재배치\n"
            "• `/당번 상세` — 전체 순서 + 슬랙ID 확인"
    )

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": ":mega: 이번 달 담당자 안내", "emoji": True},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"이번 달 *{month}월* 담당자는 "
                    f"<@{leader['userId']}> (*{leader['name']}*)님입니다! :tada:\n"
                    f"잘 부탁드립니다 :yum:"
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*:clipboard: 전체 당번 순서*\n{schedule_text}",
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
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": usage,
            },
        },
    ]
    fallback = f"{month}월 담당자는 {leader['name']}님입니다!"
    return blocks, fallback


def send_monthly_message():
    blocks, fallback = build_monthly_message()
    if blocks is None:
        print(f"[{datetime.date.today()}] 등록된 멤버가 없어 메시지를 보내지 않았습니다.")
        return
    app.client.chat_postMessage(channel=CHANNEL_ID, blocks=blocks, text=fallback)
    print(f"[{datetime.date.today()}] 월간 당번 메시지 전송 완료")


# --- 스케줄러 (매월 1일 10:00) ---

def run_scheduler():
    schedule.every().day.at("10:00").do(check_and_send)
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
    elif text == "상세":
        cmd_detail(respond)
    else:
        respond(
            ":question: *사용법*\n"
            "• `/당번` — 전체 순서 + 사용법 확인\n"
            "• `/당번 추가` {이름} {U슬랙ID} [순서], ... — 멤버 추가 (순서 생략 시 맨 뒤)\n"
            "• `/당번 삭제` {U슬랙ID}, ... — 멤버 삭제\n"
            "• `/당번 순서변경` {이름1},{이름2},... — 순서 재배치\n"
            "• `/당번 상세` — 전체 순서 + 슬랙ID 확인"
        )


def cmd_show(respond):
    leaders = load_leaders()
    if not leaders:
        respond(":clipboard: 등록된 멤버가 없습니다. `/당번 추가 이름 U슬랙ID`로 추가해주세요.")
        return
    idx = get_current_duty_index(leaders)
    total = len(leaders)
    lines = []
    for i, l in enumerate(leaders):
        y, m = get_next_month_for_index(i, total)
        month_str = format_month(y, m, total)
        if i == idx:
            lines.append(f"{i+1}. :crown: *{l['name']} — {month_str} [이번달 당번]*")
        else:
            lines.append(f"{i+1}. {l['name']} — {month_str}")
    usage = (
        "\n\n:question: *사용법*\n"
        "• `/당번` — 전체 순서 + 사용법 확인\n"
        "• `/당번 추가` {이름} {U슬랙ID} [순서], ... — 멤버 추가 (순서 생략 시 맨 뒤)\n"
        "• `/당번 삭제` {U슬랙ID}, ... — 멤버 삭제\n"
        "• `/당번 순서변경` {이름1},{이름2},... — 순서 재배치\n"
            "• `/당번 상세` — 전체 순서 + 슬랙ID 확인"
    )
    respond(f":clipboard: *전체 당번 순서*\n" + "\n".join(lines) + usage)


def cmd_detail(respond):
    leaders = load_leaders()
    if not leaders:
        respond(":clipboard: 등록된 멤버가 없습니다.")
        return
    idx = get_current_duty_index(leaders)
    total = len(leaders)
    lines = []
    for i, l in enumerate(leaders):
        y, m = get_next_month_for_index(i, total)
        month_str = format_month(y, m, total)
        if i == idx:
            lines.append(f"{i+1}. :crown: *{l['name']}* ({l['userId']}) — {month_str} [이번달 당번]")
        else:
            lines.append(f"{i+1}. {l['name']} ({l['userId']}) — {month_str}")
    respond(f":mag: *전체 당번 상세*\n" + "\n".join(lines))


def cmd_add(text, respond):
    # /당번 추가 이름 U12345 [순서], 이름2 U67890 [순서]
    raw = text[len("추가"):].strip()
    if not raw:
        respond(":warning: 형식: `/당번 추가` {이름} {U슬랙ID} [순서]  (순서는 선택값, 생략 시 맨 뒤에 추가)")
        return

    entries = [e.strip() for e in raw.split(",")]
    leaders = load_leaders()
    added = []

    for entry in entries:
        parts = entry.split()
        if len(parts) not in (2, 3):
            respond(f":warning: `{entry}` — 형식이 올바르지 않습니다. (이름 U슬랙ID [순서])")
            return
        name, user_id = parts[0], parts[1]
        if not user_id.startswith("U"):
            respond(f":warning: `{entry}` — 슬랙 User ID는 U로 시작합니다.")
            return
        position = None
        if len(parts) == 3:
            if not parts[2].isdigit() or int(parts[2]) < 1:
                respond(f":warning: `{entry}` — 순서는 1 이상의 숫자여야 합니다.")
                return
            position = int(parts[2]) - 1  # 0-based index

        existing_uids = {l["userId"] for l in leaders}
        if user_id in existing_uids:
            respond(f":warning: `{user_id}` — 이미 등록된 슬랙ID입니다.")
            return

        new_entry = {"month": 0, "name": name, "userId": user_id}
        if position is not None and position < len(leaders):
            leaders.insert(position, new_entry)
            added.append(f"{name} ({position + 1}번)")
        else:
            leaders.append(new_entry)
            added.append(name)

    for i, l in enumerate(leaders):
        l["month"] = i + 1
    save_leaders(leaders)

    if len(added) == 1:
        respond(f":white_check_mark: *{added[0]}* 님이 추가되었습니다. (현재 {len(leaders)}명)")
    else:
        names_lines = "\n".join(f"• *{n}*" for n in added)
        respond(f":white_check_mark: {len(added)}명이 추가되었습니다. (현재 {len(leaders)}명)\n{names_lines}")


def cmd_remove(text, respond):
    # /당번 삭제 U슬랙ID1, U슬랙ID2, ...
    raw = text[len("삭제"):].strip()
    if not raw:
        respond(":warning: 형식: `/당번 삭제` {U슬랙ID}, ... (`/당번 상세`에서 ID 확인)")
        return

    targets = [t.strip() for t in raw.split(",")]
    leaders = load_leaders()
    uid_set = {l["userId"] for l in leaders}

    invalid = [t for t in targets if not t.startswith("U")]
    if invalid:
        respond(f":warning: U슬랙ID만 입력 가능합니다. (`/당번 상세`에서 ID 확인)")
        return

    missing = [t for t in targets if t not in uid_set]
    if missing:
        respond(f":warning: 다음 슬랙ID를 찾을 수 없습니다: {', '.join(missing)}")
        return

    remove_uids = set(targets)
    removed = []
    new_leaders = []
    for l in leaders:
        if l["userId"] in remove_uids:
            removed.append(l["name"])
        else:
            new_leaders.append(l)

    for i, l in enumerate(new_leaders):
        l["month"] = i + 1
    save_leaders(new_leaders)

    if len(removed) == 1:
        respond(f":white_check_mark: *{removed[0]}* 님이 삭제되었습니다. (현재 {len(new_leaders)}명)")
    else:
        names_lines = "\n".join(f"• *{n}*" for n in removed)
        respond(f":white_check_mark: {len(removed)}명이 삭제되었습니다. (현재 {len(new_leaders)}명)\n{names_lines}")


def cmd_reorder(text, respond):
    # /당번 순서변경 김00,이00,박00,...
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

    # 순서변경 시 현재 연월을 시작점으로 저장
    today = datetime.date.today()
    config = load_config()
    config["start_year"] = today.year
    config["start_month"] = today.month
    save_config(config)

    lines = [f"{i+1}. {l['name']}" for i, l in enumerate(new_leaders)]
    respond(f":white_check_mark: 순서가 변경되었습니다!\n" + "\n".join(lines))


# --- 엔트리 포인트 ---

if __name__ == "__main__":
    # 스케줄러를 백그라운드 스레드로 실행
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("당번봇 started!")

    # Socket Mode로 슬래시 커맨드 리스닝
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
