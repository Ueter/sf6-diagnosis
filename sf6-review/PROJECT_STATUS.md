# SF6 Review — PROJECT STATUS

更新日: 2026-10-11 JST（Claude Code引継ぎ後に更新）

## 現在地

設計、ローカルのPython環境、AWS基盤テンプレート、Claude引継ぎを作成。Claude Codeでの引継ぎ・PC環境構築・ローカル検証・AWS環境の事前確認・**Gemini APIでの実スキャン初回成功**まで完了。詳細解析・統計集計・AWS資源作成は未実装。

## 確定要件

- 約3時間の公開YouTube配信URLが多数。任意タイミングで手動分析する。
- 既存Indeedプロジェクトと同じAWSアカウント/接続方式を利用できる。
- 本格実装はPCのClaude Codeで行う。
- 統計を根拠にしたアドバイス。起き攻めの観測期待値、状況別被弾リスク、機会数と欠測を表示する。
- 一般ランクマと特定フレンド×キャラの重点分析を分け、人読みと相手の適応を扱う。

## 実装済み・検証済み

- Python 3.12の独立venvに依存をインストール。requirements.lock.txtへ固定。
- doctorでFFmpeg/ffprobe、SDK等のローカル準備を確認。
- 公開URLの正規化、15分/全配信の処理窓計画、モードごとの識別キー。
- 15分範囲は1窓、2:58:04の全配信は12窓で計画生成。API呼び出しなし。
- AWS基盤CloudFormationをcfn-lintで検証。
- SDKの動画区間/fps引数をローカル構築で確認。Gemini実呼出しではない。
- 設定/URL/重複窓/別集計/データ契約のテスト。
- **（2026-10-11）** PCにFFmpeg導入・venv構築・doctor/unittest/cfn-lint/plan_jobを実機で再検証。日本語Windows（cp932既定ロケール）でconfig.example.yaml読込が`UnicodeDecodeError`になるバグを発見し、`encoding='utf-8'`明示で修正（5ファイル）。
- **（2026-10-11）** AWS STSでアカウント516035591962と一致を確認（root認証情報）。CDKToolkit bootstrap済み（version 32）。Default VPCにPublicサブネット3つ・IGW経路ありを確認し、Fargateの送信経路設計を実地裏付け。
- **（2026-10-11）** 既存Indeedロールの信頼ポリシーとGitHub APIから、SF6用の正しいOIDC subject実値を確定: `repo:Ueter@86462382/sf6-diagnosis@1355560250:ref:refs/heads/master`。

## ユーザー確認済み（2026-10-11）

- プレイヤー表示名: Octopus。操作タイプ: クラシック。ゲームパッチ: 本人未把握のため暫定で2.0401（2026-10-11のWeb検索、要再確認）。ライブAPI予算: ¥2,000以内の指定を受け`api_budget_usd: 13.0`（1ドル150円換算、安全側）に設定。いずれも`config.yaml`（Git管理外）へ反映し、plan_job.pyの再生成で動作確認済み。
- **Sf6ReviewGitHubOidcスタックをユーザー自身が実行し`CREATE_COMPLETE`で成功**。trust policyがStringEquals厳密一致（`repo:Ueter@86462382/sf6-diagnosis@1355560250:ref:refs/heads/master`のみ）であることを確認。ロールARN: `arn:aws:iam::516035591962:role/GitHubActions-Sf6ReviewDeploy`。
- `.env`を作成済み・Gemini APIキー設定済み（値はコミット・表示とも一切なし）。途中、AI Studio画面のテキストを誤って`.env`へ貼り付けた際にキー断片が確認用コマンドの出力へ表示される事故が発生。ユーザーに失効・再発行を依頼し、`.env`は安全な方法で再構成済み。
- モデルは`models.list()`に出ていた`gemini-2.5-flash`ではなく`gemini-3.8-flash`（新規ユーザー向けにAPIが明示的に案内）。単価: 入力$0.75/1M・出力$3.75/1Mトークン（2026-12-31までの導入価格）。
- **`scripts/scan_window.py`（探索段階）と`schemas/match_index.schema.json`を新規実装**。予算超過・モデル未設定・ライブ無効時はAPIを呼ばない安全装置つき。`--dry-run`で課金なしに見積もり確認可能。
- **0〜900秒区間の実スキャンに成功**: 候補6試合を検出、スキーマ検証合格、実コスト$0.0657（予算$13に対し十分な余裕）、`data/cost-log.json`に記録。本人表示名「octopus」を複数候補でobserved確認。
- **スキャン段階の手動照合が完了・6/6一致**。対戦相手「ガチコイニキ」（舞、試合1-2）と判定・ラウンドスコアを本人が確認し、design.md §9の目標（3〜5試合）を上回る件数で本人サイド誤認0・勝敗誤認0を確認。サガット戦2件・ディージェイ戦2件も含め全件一致。

- **`scripts/detail_match.py`（詳細段階）を新規実装**。試合3（サガット戦と判定済み、336〜435秒）で実行し7エピソード抽出、スキーマ検証合格、実コスト$0.0379（累積$0.141、予算$13）。
- **要照合**: 詳細解析のモデル出力内で対戦相手キャラクターの記述が割れている（注入値"Sagat" vs モデルの自由文"Marisa"）。本人による動画確認待ち。

## 未実施・ブロッカー

- AWSデプロイ/疎通（foundation側）、ECRイメージbuild/push、Fargate、Step Functionsは未実施。
- 詳細解析の手動照合が未完了（上記のキャラクター不整合の解決待ち）。checkpoint/lease/有限retry/キャンセル（design.md §7）は未実装・未検証。
- 統計集計、実データ統計は未着手（詳細解析の精度確認後）。
- 配置先はUeter/sf6-diagnosisのsf6-review/。既存index.htmlとの結果連携は未実装（データ契約確定後に着手）。

## 次のアクション

1. **試合3の対戦相手キャラクター不整合（Sagat/Marisa）を本人が動画で確認**（最優先、下記タイムスタンプ参照）。
2. 詳細解析のエピソード内容（起き攻め・対空・ダメージ量など）を本人が照合。
3. 統計集計とフレンドの条件付き反応を実装。
4. AWSの変更計画（foundation.json）を確認し基盤とruntimeを構築。
5. 3時間一本、次に複数アーカイブへ拡張。

詳細な検証記録: docs/validation.md。設計正本: docs/design.md / docs/statistical-analysis.md / docs/opponent-analysis.md。
