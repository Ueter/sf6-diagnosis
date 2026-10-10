# SF6 Review — PROJECT STATUS

更新日: 2026-10-11 JST

## 現在地

設計、ローカルのPython環境、AWS基盤テンプレート、Claude引継ぎを作成。対戦解析本体は未実装。AWS資源は未作成。

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

## 未実施・ブロッカー

- 今の実行環境にAWS認証、Docker、Gemini APIキーがない。
- AWSデプロイ/疎通、ECRイメージbuild/push、Fargate、Step Functionsは未実施。
- 動画を解析していない。本人の正確な表示名、操作タイプ、パッチ、フレンドの識別情報は未設定。
- 試合・機会・HP推定の抽出精度、実データ統計、料金/予算は未検証。
- 配置先はUeter/sf6-diagnosisのsf6-review/。既存index.htmlとの結果連携は未実装。
- SF6専用OIDCロールのテンプレートと手動検証workflowを追加。ロール自体は未作成。

## 次のアクション

1. PCでキットを開き、CLAUDE.mdからロード。
2. AWS接続とGeminiのモデル/キーを設定し、本人の識別を設定。
3. 15分pilotで機会の成功・失敗を両方取り、手動で精度検証。
4. 統計集計とフレンドの条件付き反応を実装。
5. AWSの変更計画を確認し基盤とruntimeを構築。
6. 3時間一本、次に複数アーカイブへ拡張。

詳細な検証記録: docs/validation.md。設計正本: docs/design.md / docs/statistical-analysis.md / docs/opponent-analysis.md。
