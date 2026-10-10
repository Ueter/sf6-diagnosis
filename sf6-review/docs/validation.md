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
- 操作タイプ: クラシック。`config.yaml`の`controls`を更新し再生成・動作確認済み。
- **`Sf6ReviewGitHubOidc`スタックをユーザー自身が実行し、`CREATE_COMPLETE`で成功**。`aws iam get-role`でtrust policyを確認し、`StringEquals`で`token.actions.githubusercontent.com:sub`が`repo:Ueter@86462382/sf6-diagnosis@1355560250:ref:refs/heads/master`に厳密一致する設定になっていることを確認（ワイルドカードなし）。ロールARN: `arn:aws:iam::516035591962:role/GitHubActions-Sf6ReviewDeploy`。
- `.env`を`.env.example`から作成（Git管理外）。
- **インシデント**: ユーザーがAI Studio画面のテキストをそのまま`.env`に貼り付け、確認用スクリプトの出力にキーの断片がそのままターミナルへ表示される事故が発生。ユーザーへ当該キーの失効・再発行を依頼し、`.env`は正規表現で安全に再構成（値を一切表示しないスクリプトで実施）。以後、`.env`の値を読む処理はbool/lengthのみ出力し、値そのものは一切printしない運用を徹底。
- Gemini APIキー（再発行後のもの）を設定・`length=53`で存在確認（値は非表示）。`google-genai`で`client.models.list()`疎通成功。
- **モデル選定のやり直し**: `models.list()`に出ていた`gemini-2.5-flash`を最初に選定したが、実際の`generate_content`呼び出しは404（「新規ユーザーには提供されていない、gemini-3.8-flashへ切り替えよ」とAPIが明示）。一覧に出ることと実際に呼べることは別だと判明。`gemini-3.8-flash`に切替。2026-10-11のWeb検索で単価確認: 入力$0.75/1Mトークン、出力$3.75/1Mトークン（2026-12-31までの導入価格、2027-01-01に倍額）。
- **`scripts/scan_window.py`を新規実装**（スキャン段階、CLAUDE.md手順3）。`schemas/match_index.schema.json`を新規作成（探索段階の候補専用スキーマ、design.md §4の出力要件に対応）。安全装置: `live_analysis_enabled`が`false`なら拒否、価格未定義モデルなら拒否、見積コストが残予算を超えるなら拒否、`--dry-run`で課金なしに見積もりだけ取得可能、実行ごとに`data/cost-log.json`へ実コストを積算。
- **`config.yaml`の`live_analysis_enabled`をユーザー承認済み予算のもとで`true`に変更**（15分pilot範囲に限定する前提）。
- **0〜900秒区間の実スキャンを実行**: dry-runでの見積り$0.19に対し、実際は入力82,266トークン・出力1,076トークン・実コスト$0.0657（見積りより低い実績）。候補6試合を検出、`schemas/match_index.schema.json`でスキーマ検証も合格。本人表示名「octopus」が複数候補で画面確認（observed, confidence 0.9〜0.95）。900秒境界をまたいだ試合6はincomplete・round_result未確定として正しく扱われている（design.mdの窓境界処理方針どおり）。累積コスト$0.0657、予算$13に対し十分な余裕。
- 出力は`data/scan-0-900.json`（Git管理外）。
- **手動照合（1回目、2026-10-11）**: 本人が試合1・試合2（対戦相手「ガチコイニキ」、舞）を実際に見て確認。AIの判定（試合1: 舞が2-0で勝利／試合2: octopus/ジュリが2-1で勝利）と**一致**。一度「1-1で引き分けのはず」という指摘があったが、本人が見直した結果AIの判定が正しいことを確認（引き分けという記憶が誤りだった）。対戦相手の表示名「ガチコイニキ」は現状のスキーマでは記録していない（opponent_character止まり。ranked_generalでは相手個人を追跡しない設計のため意図通りだが、casual/custom戦で相手名が見えるケースがあることは留意）。
- **手動照合（2回目、2026-10-11）**: 残り4候補（試合3〜6、ランクマ サガット×2・ディージェイ×2）も本人が確認し一致。**スキャン段階は6/6候補が手動照合で一致**（design.md §9の目標「3〜5試合」を上回る件数）。本人サイド誤認0・勝敗誤認0を満たす。試合境界の秒数単位の誤差（±3秒目標）は厳密な秒単位確認はしていないが、大きなズレの指摘はなし。

## 未実施・ブロッカー

- CloudFormation changeset/実デプロイ（foundation.json側）、GitHub Actions実行、Docker build、ECR登録、Fargate/Step Functions実行は未実施。
- 詳細解析（1試合のevents.schema.json出力、5fps）は未実装・未検証。checkpoint/lease/有限retry/キャンセルも未実装（design.md §7、CLAUDE.md手順5）。
- 統計集計、フレンド分析、3時間全体・複数URLへの拡張はいずれも未着手。
