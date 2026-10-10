# SF6 Review — PROJECT STATUS

更新日: 2026-10-11 JST（Claude Code引継ぎ後に更新）

## 現在地

設計、ローカルのPython環境、AWS基盤テンプレート、Claude引継ぎを作成。Claude Codeでの引継ぎ・PC環境構築・ローカル検証・AWS環境の事前確認まで完了。対戦解析本体・AWS資源作成は未実装。

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

## 未実施・ブロッカー

- **Sf6ReviewGitHubOidcスタックのデプロイがClaude Code auto modeの分類器にブロックされた**。GitHubSubject値は確定済みのため、ユーザー承認後に`aws cloudformation deploy`を再試行するか、ユーザー自身の実行が必要。
- AWSデプロイ/疎通（foundation側）、ECRイメージbuild/push、Fargate、Step Functionsは未実施。
- 動画を解析していない。**本人の正確な表示名、操作タイプ、パッチ、Gemini APIキー・利用モデル・ライブ予算はユーザー確認待ち**（フレンド識別情報は分析対象を絞る段階で別途）。
- 試合・機会・HP推定の抽出精度、実データ統計、料金/予算は未検証。
- 配置先はUeter/sf6-diagnosisのsf6-review/。既存index.htmlとの結果連携は未実装（データ契約確定後に着手）。

## 次のアクション

1. ユーザーから本人識別情報（表示名・操作タイプ・既知ならパッチ）とGemini APIキー・予算承認を受け取る。
2. Sf6ReviewGitHubOidcスタックのデプロイ（ユーザー承認/実行待ち）。
3. Gemini利用可能モデル一覧を確認し、料金・GEMINI_MODELを設定。
4. 15分pilotで機会の成功・失敗を両方取り、手動で精度検証。
5. 統計集計とフレンドの条件付き反応を実装。
6. AWSの変更計画を確認し基盤とruntimeを構築。
7. 3時間一本、次に複数アーカイブへ拡張。

詳細な検証記録: docs/validation.md。設計正本: docs/design.md / docs/statistical-analysis.md / docs/opponent-analysis.md。
