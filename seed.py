"""
seed.py - 初期データ投入スクリプト

デフォルトの学費通知スケジュールをDBに登録する。
初回セットアップ時に実行する。

使用方法:
    python seed.py
"""

from database import SessionLocal, init_db
from models import Schedule

# ---------------------------------------------------------------------------
# メッセージテンプレート
# {semester} → 前期 / 後期
# {year} → scheduler.py 実行時の年度に自動置換される
# ---------------------------------------------------------------------------
MESSAGE_TEMPLATE = """\
{semester}における学費の支払期日が近づいてきました。\
下記のURLと情報をもとに支払い手続きを進めてください。


■ 学納金納入手続システム
https://tuition-fee.52school.com/it-chiba/tuition/login


■ ログインに関する情報

学籍番号：24G2052
年度：{year}
氏名カナ
　セイ：サカグチ
　メイ：ケイタ
生年月日
　年：2005
　月：10
　日：20


■ その他・学生納付金マニュアル

1. 学納金納入手続システム操作について
https://drive.google.com/file/d/1Ko5aaNCYH0CekAXl7Svlso7Yfmq9pI3B/view?usp=sharing

2. 学費の支払方法（振込）について
https://drive.google.com/file/d/10gOAEBDf0uD1d3MjU3Tfy7GvdQQbh8JH/view?usp=sharing

3. 学費の支払方法（引落）について
https://drive.google.com/file/d/10qTAsvQlMssc0QLCwZqA-92ICOmiaErx/view?usp=sharing

4. 学費口座引落登録方法について
https://drive.google.com/file/d/1ev2aSBvjXq3nUV9y4FSQIF05QEmZG7gP/view?usp=sharing


■ 支払い完了後のご連絡

学費の納入が完了しましたら、このチャットに「支払った」とメッセージを送ってください。"""


def seed_schedules():
    """デフォルトのスケジュールを投入する"""
    init_db()
    db = SessionLocal()

    try:
        existing = db.query(Schedule).count()
        if existing > 0:
            print(f"既に{existing}件のスケジュールが登録されています。スキップします。")
            return

        schedules = [
            Schedule(
                month=4,
                day=5,
                message=MESSAGE_TEMPLATE.format(semester="前期", year="{year}"),
                enabled=True,
            ),
            Schedule(
                month=9,
                day=5,
                message=MESSAGE_TEMPLATE.format(semester="後期", year="{year}"),
                enabled=True,
            ),
        ]

        for s in schedules:
            db.add(s)
        db.commit()

        print("デフォルトスケジュールを登録しました:")
        for s in schedules:
            print(f"  {s.month}月{s.day}日")

    finally:
        db.close()


if __name__ == "__main__":
    seed_schedules()
