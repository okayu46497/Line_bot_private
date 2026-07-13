"""
database.py - データベース接続・初期化モジュール

SQLAlchemyを使用してSQLiteデータベースへの接続を管理する。
テーブル作成・セッション管理を担当する。
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./line_bot.db")

# SQLite用の接続引数
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    """テーブルを作成する（存在しない場合のみ）"""
    from models import User, Message, Schedule  # noqa: F401
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI Dependencyとして使用するDBセッション生成器"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
