"""
scheduler.py - 定期通知処理スクリプト

Render Cron Jobから毎日実行される。
今日の日付と schedules テーブルを照合し、
該当するスケジュールがあれば LINE Push Message で通知する。

使用方法:
    python scheduler.py
"""

import logging
from datetime import datetime, timezone, timedelta

from database import SessionLocal, init_db
from models import Schedule, User, Message
from line_service import push_message

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# 日本標準時 (JST = UTC+9)
JST = timezone(timedelta(hours=9))


def run_scheduled_notifications():
    """
    今日の日付に該当する有効なスケジュールを検索し、
    対象ユーザーへLINEメッセージを送信する。
    """
    now = datetime.now(JST)
    today_month = now.month
    today_day = now.day

    logger.info(f"スケジュール確認開始: {now.strftime('%Y-%m-%d %H:%M:%S')} JST")

    db = SessionLocal()
    try:
        # 今日の日付に該当する有効なスケジュールを取得
        schedules = (
            db.query(Schedule)
            .filter(
                Schedule.month == today_month,
                Schedule.day == today_day,
                Schedule.enabled == True,  # noqa: E712
            )
            .all()
        )

        if not schedules:
            logger.info("本日の通知スケジュールはありません。")
            return

        logger.info(f"本日の通知スケジュール: {len(schedules)}件")

        for schedule in schedules:
            # 対象ユーザーを決定
            if schedule.target_user_id:
                # 特定ユーザーに送信
                users = (
                    db.query(User)
                    .filter(User.id == schedule.target_user_id)
                    .all()
                )
            else:
                # 全ユーザーに送信
                users = db.query(User).all()

            # テンプレート変数を置換（{year} → 現在の年度）
            fiscal_year = now.year
            send_message = schedule.message.replace("{year}", str(fiscal_year))

            for user in users:
                logger.info(
                    f"送信中: {user.display_name} ({user.line_user_id})"
                )
                success = push_message(user.line_user_id, send_message)

                if success:
                    logger.info(f"送信完了: {user.display_name}")
                else:
                    logger.error(f"送信失敗: {user.display_name}")

    except Exception as e:
        logger.error(f"スケジュール処理中にエラー発生: {e}")
        raise
    finally:
        db.close()

    logger.info("スケジュール確認完了")


if __name__ == "__main__":
    init_db()
    run_scheduled_notifications()
