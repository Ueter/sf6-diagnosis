# Claude Codeへの引継ぎ

## 必須の最初の読み取り

README.md、PROJECT_STATUS.md、docs/design.md、docs/statistical-analysis.md、docs/opponent-analysis.md、docs/setup.md、docs/validation.mdを読む。配置先はUeter/sf6-diagnosis/sf6-review。親ディレクトリに作業ルールが追加されていれば読む。既存index.htmlの変更は、動画集計JSONの契約が決まってから行う。

ユーザーの意図: 自分の公開YouTubeスト6配信（1本約3時間、URLが多数）から任意のタイミングでジュリの課題を分析したい。設計と環境準備をChatGPTが行い、本格実装はClaude Codeで行う。AWSは既存Indeedプロジェクトと同アカウントを利用できる。

最重要追加要件: 統計を根拠にしたアドバイス。起き攻めの観測期待値、状況別被弾率、成功率の分母、体力損失、サンプル数/欠測/不確実性を出す。数値集計はPythonが行い、LLMは分類と解釈。被弾した場面だけを数える方式では要求を満たさない。pilotで精度を確認後、勝敗に依存しないランダム抽出または全件で集計する。

同じく必須: ranked_generalとfriend_focus（特定フレンド×キャラ）を分離する。人読みは条件付きの相手反応と直前の刺激/セット内の適応を集計し、次の再戦で仮説を検証する。本人がフレンドを指定・同一性確認する仕組みを作り、名前だけで統合しない。

## 今あるものとないもの

Python依存、構築手順、foundation IaC、計画生成CLI、doctor、検証記録がある。解析、Gemini呼び出し、コーチング、Dockerの実ビルド、AWSデプロイ、Fargate/Step Functionsの稼働はまだない。ダミーの成功や架空の試合分析を出さない。

## 実装順序

1. PCのdoctorを実行。AWS STSでアカウント516035591962を確認。APIキー値は表示しない。プレイヤー名/操作タイプ/パッチをユーザーが分かる範囲で設定。
2. 利用可能Geminiモデル一覧、動画対応、SDKの区間指定とfps指定、料金を照合。GEMINI_MODELを設定。初期の非ライブ設定を変更する前に予算を設定。
3. URL 3BGM_C5DHHsの0〜900秒でindexのJSONを生成。本人と試合の境界を照合。動画未確認の間は火力不足を断定しない。
4. 詳細1試合とevents.schema.jsonの出力。observed/inferred/unknownを保持。本人側、動画絶対時刻、根拠を検証。
5. checkpoint、lease、予算/回数予約、有限retry、キャンセルを実装。3〜5試合で正解ラベルと比較。
6. Markdown/HTML生成。HTMLはescapeし、YouTube絶対時刻リンクを付ける。任意でClaude APIによる要約を追加する。Claude Codeを無人ワーカーの必須依存にしない。
7. foundationsの変更計画を確認してデプロイ。worker imageをECRへpush。runtimeスタックにTaskDefinitionとStep Functionsを実装、手動workflow_dispatchから起動。
8. 3時間・複数URLを検証する。最初から全アーカイブへ大量API呼び出ししない。

## 共有環境

既存OIDCはUeter/indeed-ai-assistantのmaster限定、ID付きsubject。新repoにコピーしても動かない。既存IAM信頼範囲を広げず、必要なら専用ロールを新設する。既存Windows EC2の稼働状態は未確認なので標準実行先にしない。IndeedのAPIキー/Chrome/Slackや業務バケットは使わない。既存スタックのdeploy --allをSF6のために実行しない。

## 進捗を残す

このフォルダのPROJECT_STATUS.mdを正本とし、実装・検証・未検証・ブロッカーを区別して更新する。既存IndeedのPROJECT_STATUS.mdへSF6の詳細を二重管理しない。
