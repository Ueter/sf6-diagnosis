# 検証記録

検証対象: 設計・環境キット。対戦映像の分析結果は含まない。

## 実施済み（ChatGPTによる設計時点）

- Python 3.12専用venvでrequirements.lock.txtの依存をインストール。
- doctor: boto3 / google-genai / PyYAML / jsonschema / yt-dlp、FFmpeg / ffprobeが使用可能。ローカル準備完了。秘密値の出力なし。
- unittest: 9件すべて成功。 URL正規化、15分窓の重複と境界、ランクマとフレンドの識別キー、JSON Schema、SDKの区間/fps引数、設定、基盤の構成を検証。
- 15分の計画は1窓、2時間58分4秒は12窓。API呼び出しなし、analysis_executed=false。
- cfn-lint: foundation.json、github-oidc.json。実デプロイではなく構文と資源仕様の静的検証。
- GitHubの配置先はUeter/sf6-diagnosis/master。配置前のツリーにはindex.htmlのみ。AGENTS.mdやCLAUDE.md等の既存作業ルールなし。

## 実施済み（2026-10-11、Claude Codeによる引継ぎ後）

- `git fetch`でコミット`45fbe6e`（指定ハッシュと完全一致）を確認し、ff-onlyでpull。
- PCにFFmpeg/ffprobe未導入だったため導入（scoop）。bootstrap.ps1（`pwsh`経由、legacy `powershell.exe`はこのPCで既知の理由により不可）でvenv作成・依存インストール・doctor実行。
- **バグ発見・修正**: `plan_job.py`・`plan_foundation.py`・`infra/make_template.py`・`tests/test_contracts.py`・`tests/test_plan.py`の`read_text()`/`write_text()`が`encoding`未指定だったため、日本語Windows既定ロケール（cp932）でUTF-8ファイル（config.example.yaml等）の読み込みに失敗（`UnicodeDecodeError`）。全箇所に`encoding='utf-8'`を明示して修正。修正後、unittest 9件・cfn-lint 2ファイルとも成功を再確認。
- `doctor.py --check-aws`: `aws_check=expected_account`（アカウント516035591962と一致）。
- `plan_job.py --end 900`: 15分計画を再生成、1窓・API呼び出し0件・`analysis_executed=false`を確認（修正後の再現性確認）。
- AWS STS: `arn:aws:iam::516035591962:root`で疎通（ルート認証情報。専用IAMユーザー/ロールでの運用は未検討）。
- CDKToolkit: `CREATE_COMPLETE`、bootstrap version 32（indeed-ai-assistant導入時のものを流用可能、SF6専用の新規ブートストラップは不要）。
- Default VPC（`vpc-0e6e35246f8c573f1`）に3つのPublicサブネット（1a/1c/1d、いずれも`MapPublicIpOnLaunch=true`）とIGW（`igw-05115d48ee7269b87`）への`0.0.0.0/0`ルートを確認。NAT無しでFargateの送信経路が成立する設計を実地確認済み。
- 既存`GitHubActions-IndeedAiAssistantDeploy`ロールの信頼ポリシーを確認し、OIDC subjectがID付き形式（`repo:Ueter@86462382/indeed-ai-assistant@1388593329:...`）であることを確認。GitHub APIで`sf6-diagnosis`のrepo IDが`1355560250`、ownerの`Ueter`のuser IDが`86462382`であることを確認し、`infra/github-oidc.json`の`GitHubSubject`パラメータは2つの許容値のうち`repo:Ueter@86462382/sf6-diagnosis@1355560250:ref:refs/heads/master`が正しいことを確定（推測ではなく実値照合）。

## ユーザー確認済み（2026-10-11）

- プレイヤー表示名: Octopus。`config.yaml`（Git管理外、.example差分のみ追跡）に設定し、`plan_job.py --config config.yaml`で再生成・動作確認済み。
- ゲームパッチ: 本人未把握のため、2026-10-11のWeb検索でSF6の最新パッチ（2.0401、Yasmine、2026-08-03）を確認し暫定設定。公式パッチノートでの再確認が必要で、確反・コンボ最適解の精密な判定には使わない方針を`config.yaml`のコメントに明記。
- ライブ実行のAPI予算: 「このプロジェクトで¥2,000以内」という指定を受け、1ドル150円換算で安全側に切り下げた`api_budget_usd: 13.0`を設定。
- 操作タイプ（モダン/クラシック）は未回答。`controls: unknown`のまま。

## 未実施・ブロッカー

- **`Sf6ReviewGitHubOidc`スタックのデプロイがClaude Code auto modeの分類器にブロックされた**（IAMロール作成を含むCloudFormation deployが機密性の高い操作として拒否）。ロール自体は未作成。コマンドをユーザーへ渡し、ユーザー自身の実行を依頼中。
- CloudFormation changeset/実デプロイ（foundation.json側）、GitHub Actions実行、Docker build、ECR登録、Fargate/Step Functions実行、Gemini API疎通、実動画の抽出と統計、費用検証は未実施。
- 操作タイプ、Gemini APIキー・利用モデルの確定は引き続きユーザー確認待ち（下記「次のアクション」参照）。

この環境にはGemini APIキーがまだない。doctorのlocal_environment_readyと実対戦解析の準備完了は別。機会検出・体力推定の精度をpilotで手動評価してから統計とアドバイスを実装する。
