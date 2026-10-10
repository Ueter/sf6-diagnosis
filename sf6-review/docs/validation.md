# 検証記録

検証対象: 設計・環境キット。対戦映像の分析結果は含まない。

## 実施済み

- Python 3.12専用venvでrequirements.lock.txtの依存をインストール。
- doctor: boto3 / google-genai / PyYAML / jsonschema / yt-dlp、FFmpeg / ffprobeが使用可能。ローカル準備完了。秘密値の出力なし。
- unittest: 9件すべて成功。 URL正規化、15分窓の重複と境界、ランクマとフレンドの識別キー、JSON Schema、SDKの区間/fps引数、設定、基盤の構成を検証。
- 15分の計画は1窓、2時間58分4秒は12窓。API呼び出しなし、analysis_executed=false。
- cfn-lint: foundation.json、github-oidc.json。実デプロイではなく構文と資源仕様の静的検証。
- GitHubの配置先はUeter/sf6-diagnosis/master。配置前のツリーにはindex.htmlのみ。AGENTS.mdやCLAUDE.md等の既存作業ルールなし。

## 未実施

AWS認証、CloudFormation changeset/実デプロイ、OIDC subject実値の照合、GitHub Actions実行、Docker build、ECR登録、Fargate/Step Functions実行、Gemini API疎通、実動画の抽出と統計、費用検証。

この環境にはAWS認証、Docker、Gemini APIキーがない。doctorのlocal_environment_readyと実対戦解析の準備完了は別。機会検出・体力推定の精度をpilotで手動評価してから統計とアドバイスを実装する。
