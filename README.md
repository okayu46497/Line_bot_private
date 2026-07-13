# 学費支払い通知Bot

LINE Messaging APIを利用した学費支払いリマインドBotです。  
毎年決まった日時に、学費支払いに関するリマインドメッセージをLINEで自動送信します。

## 機能一覧

- **Webhook受信**: LINEからのメッセージ・フォローイベントを処理
- **ユーザー自動登録**: 初回メッセージ送信時にLINEプロフィールを取得・保存
- **メッセージ履歴**: 送受信メッセージをすべてDB保存
- **スケジュール管理**: 通知日時・メッセージをDB管理
- **自動送信**: Render Cron Jobで毎日チェック → 該当日にPush送信
- **コマンド応答**: 「スケジュール」「ヘルプ」などのキーワードに応答

## ファイル構成

```
LINE_BOT/
├── app.py              # FastAPIメインアプリ（Webhook処理）
├── database.py         # DB接続・セッション管理
├── models.py           # SQLAlchemy データモデル
├── line_service.py     # LINE API送受信処理
├── scheduler.py        # 定期通知処理（Cron Job用）
├── seed.py             # 初期スケジュール投入スクリプト
├── Procfile            # Render用起動設定
├── requirements.txt    # Python依存パッケージ
├── .env.example        # 環境変数テンプレート
├── .gitignore          # Git除外設定
└── README.md           # このファイル
```

---

## セットアップ手順

### 1. LINE公式アカウント・Messaging APIの設定

#### 1-1. LINE Developersコンソールでチャネル作成

1. [LINE Developers](https://developers.line.biz/) にログイン
2. 「プロバイダー」を作成（または既存のものを選択）
3. 「Messaging API」チャネルを新規作成
   - チャネル名: 「学費支払い通知Bot」（任意）
   - チャネル説明: 任意
   - 業種: 該当するものを選択

#### 1-2. チャネルシークレットの取得

1. チャネルの「チャネル基本設定」タブを開く
2. **チャネルシークレット** をコピー → `.env` の `CHANNEL_SECRET` に設定

#### 1-3. チャネルアクセストークンの取得

1. チャネルの「Messaging API設定」タブを開く
2. 「チャネルアクセストークン（長期）」を発行してコピー
3. → `.env` の `CHANNEL_ACCESS_TOKEN` に設定

#### 1-4. Webhook URLの設定

1. 「Messaging API設定」タブの「Webhook設定」セクション
2. Webhook URL に以下を入力:
   ```
   https://your-app-name.onrender.com/webhook
   ```
3. 「Webhookの利用」をオンにする
4. 「検証」ボタンで接続確認

#### 1-5. 応答メッセージの無効化

1. 「Messaging API設定」タブ → 「LINE公式アカウント機能」
2. 「応答メッセージ」→ 「無効」に設定  
   （Botが自動返信するため、LINE公式の自動応答は不要）

---

### 2. ローカル環境でのセットアップ

```bash
# リポジトリをクローン
git clone https://github.com/your-username/LINE_BOT.git
cd LINE_BOT

# 仮想環境を作成・有効化
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

# 依存パッケージをインストール
pip install -r requirements.txt

# 環境変数ファイルを作成
cp .env.example .env
# .env を編集して CHANNEL_SECRET, CHANNEL_ACCESS_TOKEN を設定

# 初期スケジュール投入
python seed.py

# サーバー起動
uvicorn app:app --reload --port 8000
```

---

### 3. Renderへのデプロイ

#### 3-1. Web Service の作成

1. [Render](https://render.com/) にログイン
2. 「New」→「Web Service」を選択
3. GitHubリポジトリを接続
4. 以下を設定:

| 設定項目 | 値 |
|---|---|
| **Name** | `line-tuition-bot`（任意） |
| **Runtime** | `Python` |
| **Build Command** | `pip install -r requirements.txt && python seed.py` |
| **Start Command** | `uvicorn app:app --host 0.0.0.0 --port $PORT` |
| **Plan** | Free |

5. 「Environment Variables」に以下を設定:

| 環境変数名 | 値 |
|---|---|
| `CHANNEL_SECRET` | LINE Developersで取得した値 |
| `CHANNEL_ACCESS_TOKEN` | LINE Developersで取得した値 |
| `DATABASE_URL` | `sqlite:///./line_bot.db` |

6. 「Create Web Service」をクリック

#### 3-2. デプロイ後の確認

デプロイ完了後、以下のURLでヘルスチェック:
```
https://your-app-name.onrender.com/
```

応答例:
```json
{"status": "ok", "message": "学費支払い通知Bot is running"}
```

#### 3-3. Webhook URLの設定

LINE DevelopersコンソールのWebhook URLを更新:
```
https://your-app-name.onrender.com/webhook
```

---

### 4. Cron Job の設定

#### 4-1. Render Cron Job の作成

1. Renderダッシュボードで「New」→「Cron Job」を選択
2. 同じGitHubリポジトリを接続
3. 以下を設定:

| 設定項目 | 値 |
|---|---|
| **Name** | `tuition-bot-scheduler` |
| **Runtime** | `Python` |
| **Build Command** | `pip install -r requirements.txt` |
| **Command** | `python scheduler.py` |
| **Schedule** | `0 23 * * *`（= 日本時間 毎朝8時） |

> **注意**: RenderのCron JobはUTCで動作します。  
> 日本時間 (JST) は UTC+9 なので、日本時間の朝8時 = UTC 23:00（前日）です。

4. 環境変数はWeb Serviceと同じものを設定
5. 「Create Cron Job」をクリック

---

## 必要な環境変数一覧

| 変数名 | 説明 | 必須 |
|---|---|---|
| `CHANNEL_SECRET` | LINE Messaging APIのチャネルシークレット | ✅ |
| `CHANNEL_ACCESS_TOKEN` | LINE Messaging APIのチャネルアクセストークン | ✅ |
| `DATABASE_URL` | SQLiteデータベースのパス（デフォルト: `sqlite:///./line_bot.db`） | - |
| `NOTIFY_HOUR` | 通知実行時刻（デフォルト: 8、現在は参考値） | - |

---

## 管理用エンドポイント

| エンドポイント | メソッド | 説明 |
|---|---|---|
| `/` | GET | ヘルスチェック |
| `/webhook` | POST | LINE Webhook受信 |
| `/setup/schedules` | POST | デフォルトスケジュール投入 |
| `/admin/users` | GET | 登録ユーザー一覧 |
| `/admin/messages` | GET | メッセージ履歴（直近50件） |
| `/admin/schedules` | GET | スケジュール一覧 |

---

## デフォルトの通知スケジュール

| 月日 | メッセージ |
|---|---|
| 4月15日 | 📚 前期学費の支払い期限が近づいています。お手続きをお願いいたします。 |
| 9月15日 | 📚 後期学費の支払い期限が近づいています。お手続きをお願いいたします。 |

スケジュールの追加・変更はDBの `schedules` テーブルを直接編集するか、  
`/admin/schedules` エンドポイントで確認できます。

---

## 拡張ポイント

- **通知日の追加**: `schedules` テーブルにレコードを追加するだけ
- **複数ユーザー対応**: `target_user_id` を `NULL` にすると全ユーザーに送信
- **管理画面**: `/admin/` エンドポイントをベースにWeb UIを追加可能
- **Flex Message**: `line_service.py` を拡張してリッチなメッセージに対応可能

---

## ライセンス

MIT License
