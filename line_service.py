"""
line_service.py - LINE Messaging API 送受信サービス

LINE Messaging APIを使用して以下の処理を行う：
- Push Messageでテキストメッセージを送信する
- ユーザープロフィールを取得する
"""

import os
import logging
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN", "")

LINE_API_BASE = "https://api.line.me/v2"
LINE_MESSAGING_API = f"{LINE_API_BASE}/bot"


def _get_headers() -> dict:
    """LINE API用の認証ヘッダーを返す"""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
    }


def push_message(user_id: str, text: str) -> bool:
    """
    指定したLINE userIdへテキストメッセージをPush送信する。

    Args:
        user_id: LINE userId
        text: 送信するテキスト

    Returns:
        成功した場合 True、失敗した場合 False
    """
    url = f"{LINE_MESSAGING_API}/message/push"
    payload = {
        "to": user_id,
        "messages": [
            {
                "type": "text",
                "text": text,
            }
        ],
    }

    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(url, json=payload, headers=_get_headers())
            response.raise_for_status()
            logger.info(f"メッセージ送信成功: user_id={user_id}")
            return True
    except httpx.HTTPStatusError as e:
        logger.error(
            f"メッセージ送信失敗 (HTTP {e.response.status_code}): "
            f"user_id={user_id}, response={e.response.text}"
        )
        return False
    except Exception as e:
        logger.error(f"メッセージ送信エラー: user_id={user_id}, error={e}")
        return False


def get_user_profile(user_id: str) -> dict | None:
    """
    LINEプロフィールAPIを使用してユーザー情報を取得する。

    Args:
        user_id: LINE userId

    Returns:
        プロフィール情報の辞書。取得失敗時は None
    """
    url = f"{LINE_MESSAGING_API}/profile/{user_id}"

    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(url, headers=_get_headers())
            response.raise_for_status()
            profile = response.json()
            logger.info(f"プロフィール取得成功: {profile.get('displayName')}")
            return profile
    except httpx.HTTPStatusError as e:
        logger.error(
            f"プロフィール取得失敗 (HTTP {e.response.status_code}): "
            f"user_id={user_id}, response={e.response.text}"
        )
        return None
    except Exception as e:
        logger.error(f"プロフィール取得エラー: user_id={user_id}, error={e}")
        return None
