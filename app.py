"""
app.py - FastAPI メインアプリケーション

LINE Messaging API Webhook の受信・処理を行う。
以下の機能を提供する：
- Webhook署名検証
- メッセージイベント処理
- ユーザー自動登録（初回利用時）
- メッセージ履歴保存
- ヘルスチェックエンドポイント
- 初期スケジュール投入エンドポイント
"""

import os
import logging
import hashlib
import hmac
import base64
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import init_db, get_db
from models import User, Message, Schedule, now_jst
from line_service import get_user_profile, push_message

load_dotenv()

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

CHANNEL_SECRET = os.getenv("CHANNEL_SECRET", "")
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN", "")
CRON_SECRET = os.getenv("CRON_SECRET", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーション起動時にDBを初期化する"""
    init_db()
    logger.info("データベース初期化完了")
    yield


app = FastAPI(
    title="学費支払い通知Bot",
    description="LINE Messaging APIを利用した学費支払いリマインドBot",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# ヘルスチェック
# ---------------------------------------------------------------------------
@app.get("/")
def health_check():
    """Render等のヘルスチェック用"""
    return {"status": "ok", "message": "学費支払い通知Bot is running"}


# ---------------------------------------------------------------------------
# Webhook署名検証
# ---------------------------------------------------------------------------
def verify_signature(body: bytes, signature: str) -> bool:
    """LINE Webhookの署名を検証する"""
    hash_value = hmac.new(
        CHANNEL_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    expected_signature = base64.b64encode(hash_value).decode("utf-8")
    return hmac.compare_digest(signature, expected_signature)


# ---------------------------------------------------------------------------
# ユーザー登録・取得
# ---------------------------------------------------------------------------
def get_or_create_user(db: Session, line_user_id: str) -> User:
    """
    ユーザーをDBから取得する。存在しなければ新規作成する。
    LINEプロフィールAPIからdisplayNameも取得して保存する。
    """
    user = db.query(User).filter(User.line_user_id == line_user_id).first()

    if user:
        # displayNameを最新に更新
        profile = get_user_profile(line_user_id)
        if profile and profile.get("displayName"):
            user.display_name = profile["displayName"]
            user.updated_at = now_jst()
            db.commit()
        return user

    # 新規ユーザー作成
    logger.info(f"新規ユーザー登録: {line_user_id}")
    profile = get_user_profile(line_user_id)
    display_name = profile.get("displayName", "Unknown") if profile else "Unknown"

    new_user = User(
        line_user_id=line_user_id,
        display_name=display_name,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"ユーザー登録完了: {new_user}")
    return new_user


# ---------------------------------------------------------------------------
# Webhook受信
# ---------------------------------------------------------------------------
@app.get("/webhook")
def webhook_get():
    """LINE Webhook URL検証用（GETリクエスト対応）"""
    return JSONResponse(content={"status": "ok"}, status_code=200)


@app.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    """
    LINE Messaging API Webhook エンドポイント

    1. 署名検証
    2. イベント解析
    3. ユーザー登録・更新
    4. メッセージ履歴保存
    5. 応答メッセージ送信

    注意: LINE仕様上、いかなる場合も200を返す必要がある
    """
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")

    # 署名検証（失敗してもログのみ、200は返す）
    if not verify_signature(body, signature):
        logger.warning("Webhook署名検証失敗")
        return JSONResponse(content={"status": "error", "message": "Invalid signature"}, status_code=200)

    try:
        # イベント解析
        try:
            payload = await request.json()
        except Exception:
            logger.warning("JSONパース失敗")
            return JSONResponse(content={"status": "ok"}, status_code=200)

        events = payload.get("events", [])
        logger.info(f"Webhook受信: {len(events)}件のイベント")

        # events が空 = LINE Webhook URL検証リクエスト
        if not events:
            logger.info("Webhook検証リクエスト（eventsが空）→ 200 OK")
            return JSONResponse(content={"status": "ok"}, status_code=200)

        for event in events:
            event_type = event.get("type")

            # フォローイベント（友だち追加時）
            if event_type == "follow":
                line_user_id = event["source"]["userId"]
                user = get_or_create_user(db, line_user_id)
                logger.info(f"フォローイベント: {user.display_name}")

                # ウェルカムメッセージ送信
                welcome_text = (
                    "このbotは学費通知botです。\n"
                    "前期・後期の学費支払期限が近づき次第リマインドします。\n"
                    "(案内予定日：4月5日及び9月5日)\n\n"
                    "またこのbotに対するメッセージはすべて保存されます。"
                )
                push_message(line_user_id, welcome_text)

            # メッセージイベント
            elif event_type == "message":
                message = event.get("message", {})
                if message.get("type") != "text":
                    continue

                line_user_id = event["source"]["userId"]
                text = message.get("text", "")

                # ユーザー取得 or 登録
                user = get_or_create_user(db, line_user_id)

                # 受信メッセージを履歴に保存（相手からのメッセージのみ）
                msg_record = Message(
                    user_id=user.id,
                    message_text=text,
                    direction="recv",
                )
                db.add(msg_record)
                db.commit()

                logger.info(f"メッセージ受信: {user.display_name} -> {text}")

                # コマンド処理
                response_text = handle_command(db, user, text)
                if response_text:
                    push_message(line_user_id, response_text)

    except Exception as e:
        # どんなエラーが起きても200を返す（LINE仕様）
        logger.error(f"Webhook処理中にエラー発生: {e}", exc_info=True)

    return JSONResponse(content={"status": "ok"}, status_code=200)


# ---------------------------------------------------------------------------
# コマンド処理
# ---------------------------------------------------------------------------
def handle_command(db: Session, user: User, text: str) -> str | None:
    """
    ユーザーからのメッセージに応じた処理を行う。

    対応コマンド:
    - 「スケジュール」: 登録済みスケジュール一覧を表示
    - 「テスト通知」: 実際の通知メッセージをテスト送信
    - 「ヘルプ」: 利用方法を表示
    - その他: デフォルトの応答
    """
    from datetime import datetime, timezone, timedelta
    JST = timezone(timedelta(hours=9))

    text_stripped = text.strip()

    if text_stripped in ("スケジュール", "予定", "一覧"):
        # スケジュール一覧を返す
        schedules = (
            db.query(Schedule)
            .filter(Schedule.enabled == True)  # noqa: E712
            .order_by(Schedule.month, Schedule.day)
            .all()
        )
        if not schedules:
            return "登録されたスケジュールはありません。"

        lines = ["📅 通知スケジュール一覧\n"]
        for s in schedules:
            # メッセージの1行目だけを表示（長文対策）
            first_line = s.message.split("\n")[0]
            lines.append(f"  {s.month}月{s.day}日: {first_line}")
        return "\n".join(lines)

    elif text_stripped in ("支払った", "支払い完了", "納入済み"):
        # 支払い確認 → 現在の月から前期/後期を判定して来期を案内
        now = datetime.now(JST)
        if 4 <= now.month <= 8:
            # 前期の支払い → 来期は後期（9月上旬）
            return "今期の学費納入を確認しました。来期は9月上旬ごろの案内となります。"
        else:
            # 後期の支払い → 来期は前期（4月上旬）
            return "今期の学費納入を確認しました。来期は4月上旬ごろの案内となります。"

    elif text_stripped in ("テスト通知", "テスト", "test"):
        # テスト: 登録済みスケジュールの最初の1件を実際に送信する
        schedule = (
            db.query(Schedule)
            .filter(Schedule.enabled == True)  # noqa: E712
            .order_by(Schedule.month, Schedule.day)
            .first()
        )
        if not schedule:
            return "⚠ 登録されたスケジュールがないためテストできません。"

        # {year} を現在の年度に置換
        fiscal_year = datetime.now(JST).year
        test_message = schedule.message.replace("{year}", str(fiscal_year))

        # 送信
        success = push_message(user.line_user_id, test_message)
        if success:
            return None  # テスト通知自体がメッセージなので追加応答は不要
        else:
            return "⚠ テスト通知の送信に失敗しました。ログを確認してください。"

    elif text_stripped in ("ヘルプ", "help", "使い方"):
        return (
            "📚 学費支払い通知Bot ヘルプ\n\n"
            "以下のメッセージを送ると情報を確認できます：\n"
            '・「スケジュール」→ 通知予定一覧\n'
            '・「支払った」→ 学費納入の報告\n'
            '・「テスト通知」→ 通知メッセージをテスト送信\n'
            '・「ヘルプ」→ この説明を表示'
        )

    else:
        return "記録しました。"


# ---------------------------------------------------------------------------
# 初期スケジュール投入
# ---------------------------------------------------------------------------
@app.post("/setup/schedules")
def setup_default_schedules(db: Session = Depends(get_db)):
    """
    デフォルトの学費通知スケジュールを投入する。
    既存のスケジュールがある場合はスキップする。
    """
    from seed import MESSAGE_TEMPLATE

    existing = db.query(Schedule).count()
    if existing > 0:
        return {"message": f"既に{existing}件のスケジュールが登録されています。"}

    default_schedules = [
        Schedule(
            month=4,
            day=5,
            message=MESSAGE_TEMPLATE.format(semester="前期", year="{year}"),
        ),
        Schedule(
            month=9,
            day=5,
            message=MESSAGE_TEMPLATE.format(semester="後期", year="{year}"),
        ),
    ]

    for s in default_schedules:
        db.add(s)
    db.commit()

    logger.info("デフォルトスケジュール投入完了")
    return {
        "message": "デフォルトスケジュールを登録しました。",
        "schedules": [
            {"month": s.month, "day": s.day}
            for s in default_schedules
        ],
    }


# ---------------------------------------------------------------------------
# Cron 実行エンドポイント（GitHub Actions から呼び出す）
# ---------------------------------------------------------------------------
@app.get("/cron/run")
def cron_run(key: str = "", db: Session = Depends(get_db)):
    """
    GitHub Actions から毎日呼び出される通知実行エンドポイント。
    クエリパラメータ key が CRON_SECRET と一致する場合のみ実行する。

    使用例: GET /cron/run?key=your_cron_secret
    """
    # 認証チェック
    if not CRON_SECRET or key != CRON_SECRET:
        logger.warning("Cron実行: 認証失敗")
        raise HTTPException(status_code=403, detail="Forbidden")

    from scheduler import run_scheduled_notifications
    try:
        run_scheduled_notifications()
        logger.info("Cron実行: 完了")
        return {"status": "ok", "message": "スケジュール確認を実行しました。"}
    except Exception as e:
        logger.error(f"Cron実行エラー: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# 管理用エンドポイント
# ---------------------------------------------------------------------------
@app.get("/admin/users")
def list_users(db: Session = Depends(get_db)):
    """登録ユーザー一覧を取得する"""
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "line_user_id": u.line_user_id,
            "display_name": u.display_name,
            "created_at": str(u.created_at),
        }
        for u in users
    ]


@app.get("/admin/messages")
def list_messages(db: Session = Depends(get_db)):
    """メッセージ履歴を取得する（直近50件）"""
    messages = (
        db.query(Message)
        .order_by(Message.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": m.id,
            "user_id": m.user_id,
            "message_text": m.message_text,
            "direction": m.direction,
            "created_at": str(m.created_at),
        }
        for m in messages
    ]


@app.get("/admin/schedules")
def list_schedules(db: Session = Depends(get_db)):
    """スケジュール一覧を取得する"""
    schedules = db.query(Schedule).all()
    return [
        {
            "id": s.id,
            "month": s.month,
            "day": s.day,
            "message": s.message,
            "target_user_id": s.target_user_id,
            "enabled": s.enabled,
        }
        for s in schedules
    ]
