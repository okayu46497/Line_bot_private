"""
models.py - SQLAlchemy データモデル定義

以下の3テーブルを定義する：
- users: LINEユーザー情報
- messages: メッセージ送受信履歴
- schedules: 通知スケジュール
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base

# 日本標準時 (JST = UTC+9)
JST = timezone(timedelta(hours=9))


def now_jst():
    """現在の日本時間を返す"""
    return datetime.now(JST)


class User(Base):
    """LINEユーザー情報テーブル"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    line_user_id = Column(String(64), unique=True, nullable=False, index=True)
    display_name = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=now_jst)
    updated_at = Column(DateTime, default=now_jst, onupdate=now_jst)

    # リレーション
    messages = relationship("Message", back_populates="user")
    schedules = relationship("Schedule", back_populates="target_user")

    def __repr__(self):
        return f"<User(id={self.id}, display_name={self.display_name})>"


class Message(Base):
    """メッセージ履歴テーブル"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    message_text = Column(Text, nullable=False)
    direction = Column(String(8), nullable=False, default="recv")  # "recv" or "sent"
    created_at = Column(DateTime, default=now_jst)

    # リレーション
    user = relationship("User", back_populates="messages")

    def __repr__(self):
        return f"<Message(id={self.id}, direction={self.direction})>"


class Schedule(Base):
    """通知スケジュールテーブル"""
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    month = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    message = Column(Text, nullable=False)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    enabled = Column(Boolean, default=True)

    # リレーション
    target_user = relationship("User", back_populates="schedules")

    def __repr__(self):
        return f"<Schedule(id={self.id}, month={self.month}, day={self.day})>"
