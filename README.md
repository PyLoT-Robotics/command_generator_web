# Command Generator Web (Vercel + Python)

RoboCupAtHomeJP の `CommandGenerator`（`rcj25_for_opl`）を Web UI から実行するプロジェクトです。

- Backend: Flask (`api/index.py`)
- Frontend: Vanilla HTML/CSS/JS (`public/`)
- Deploy: Vercel (`vercel.json`)
- Mobile: responsive 対応

## Web の使い方

1. `Generate` を押してコマンドを生成
2. モードを切り替えて生成タイプを変更
3. `Copy Result` で結果コピー
4. `Speak` で英語音声読み上げ
5. 必要なら `Voice Settings` を開いて速度・声を調整

生成モード:

- `any`: Any command
- `people`: Command without manipulation
- `objects`: Command with manipulation
- `batch`: Batch of three commands
- `egpsr`: Generate EGPSR setup

補足:

- 元の実体は `generate.py` ではなく `CommandGeneratorJP/generator.py` です。
- upstream の既知不整合で `WARNING` が出るケースがあるため、API 側で再抽選しています。

## GitHub へ上げて Vercel にデプロイ

1. このプロジェクトを GitHub に push
2. Vercel でリポジトリを Import
3. 設定は以下

- Framework Preset: `Other`
- Build Command: 未設定で OK
- Output Directory: 未設定で OK
- Install Command: `pip install -r requirements.txt`（デフォルトでも可）

4. Deploy 実行

`vercel.json` のルーティングにより、`/api/*` は Python API、その他は `public/` 配下が配信されます。

## clone 後にローカル再現する手順

以下は Windows PowerShell 前提です。

1. Web プロジェクトを clone

```powershell
git clone <your-repo-url>
cd <your-repo-name>
```

2. Python 環境を作成して依存を入れる

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. サブモジュールを取得

```powershell
git submodule update --init --recursive
```

4. 起動

```powershell
python api\index.py
```

ブラウザで `http://127.0.0.1:5000` を開きます。

## 元 CommandGenerator の更新を反映する方法

upstream に更新が入ったら、以下で取り込みます。

1. `CommandGenerator` サブモジュール参照を更新

```powershell
git submodule update --init --recursive --remote
```

2. Web 側の動作確認

```powershell
python api\index.py
```

3. 問題なければ GitHub へ反映

- このリポジトリ管理方法に合わせて、更新分を commit/push してください。
- その後 Vercel を再デプロイすると最新データが反映されます。

## API（簡易）

`POST /api/generate`

```json
{
  "mode": "any"
}
```

`mode`: `any|people|objects|batch|egpsr`
