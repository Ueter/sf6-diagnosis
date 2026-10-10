# SF6 Review Starter

公開YouTubeの長時間スト6配信を、任意実行で分析するための設計・環境構築キットです。解析本体はまだ実装されていません。

## 今回の成果物

- `docs/design.md`: 設計と実装判断
- `docs/setup.md`: PC/AWS環境構築手順
- `CLAUDE.md`: 本格実装への引継ぎ
- `infra/foundation.json`: 独立したAWS基盤
- `scripts/doctor.py`: 秘密値を表示しない環境チェック
- `scripts/plan_job.py`: URL正規化と処理窓の計画生成（API呼び出しなし）
- `requirements.lock.txt`: 今回インストールして検証した依存バージョン
- `infra/github-oidc.json`: SF6リポジトリ専用のAWS接続ロール
- `integration/github-workflows/sf6-environment.yml`: リポジトリ直下の手動Actionsと同じ内容
- `docs/validation.md`: 実施済み/未実施の検証記録

## PCで開始

Python 3.12、FFmpeg/ffprobe、AWS接続、必要に応じてDockerを準備します。

Windows:
```powershell
powershell -File scripts/bootstrap.ps1
.\.venv\Scripts\python.exe scripts/plan_job.py --end 900 --output data/plan.json
```

Linux/macOS:
```bash
bash scripts/bootstrap.sh
.venv/bin/python scripts/plan_job.py --end 900 --output data/plan.json
```

bootstrapはAPIキー不要。doctorがローカル準備完了でもAWSやライブ解析が完了したという意味ではありません。

配置先は `Ueter/sf6-diagnosis/sf6-review/`。リポジトリを取得し、このディレクトリでコマンドを実行してください。既存の `index.html` は診断ページとして維持します。動画分析の結果をページへ取り込む部分は後続実装です。
