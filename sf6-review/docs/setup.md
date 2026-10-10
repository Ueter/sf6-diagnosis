# 環境構築手順

## A. PCの環境

1. `Ueter/sf6-diagnosis` のmasterを取得し、`sf6-review/` ディレクトリへ移動する。以降のコマンドはこのディレクトリで実行する。
2. Python 3.12とFFmpeg/ffprobeをPATHに用意する。既存環境へ上書きせず、このフォルダ専用venvを使用する。
3. Windowsは `powershell -File scripts/bootstrap.ps1`、Linux/macOSは `bash scripts/bootstrap.sh`。実行ポリシーがスクリプトを禁止する場合は、スクリプトにある3つのPythonコマンドを手動実行し、保護を無効化しない。
4. `.env.example` と `config.example.yaml` をコピーし、後でキー・モデル・正確な自分の表示名・操作タイプ・パッチを設定する。doctor/planのみならキー不要。
5. フレンド分析は `opponents.example.yaml` を `opponents.yaml` にコピーし、対象の表示名/キャラを登録する。ランクマの集合とは分ける。

Windows例:
```powershell
.\.venv\Scripts\python.exe scripts\doctor.py
.\.venv\Scripts\python.exe scripts\plan_job.py --end 900 --output data\plan-15min.json
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Linux/macOS例:
```bash
.venv/bin/python scripts/doctor.py
.venv/bin/python scripts/plan_job.py --end 900 --output data/plan-15min.json
.venv/bin/python -m unittest discover -s tests
.venv/bin/cfn-lint -t infra/foundation.json
```

`doctor.py`はdotenvを自動ロードしない。APIキーの存在チェックはそのプロセスの環境変数を対象にする。Claudeがライブ実装を作る際に、Git管理外設定の読込を追加する。キー値を表示する診断は不要。

## B. AWS接続の確認（今回未実施）

PCの既存AWS CLI/SSO/一時認証を利用する。共有環境の長期アクセスキーを新しく作る前提にしない。

```bash
aws sts get-caller-identity
aws cloudformation describe-stacks --stack-name CDKToolkit --region ap-northeast-1
aws ec2 describe-vpcs --filters Name=is-default,Values=true --region ap-northeast-1
```

アカウント516035591962、リージョンap-northeast-1を確認する。Default VPCが実環境に無い場合は既存VPCを選び、Fargate実装前にPublic Subnet/IGW/ルートを確認する。

Pythonによる接続確認:
```bash
.venv/bin/python scripts/doctor.py --check-aws
```

GitHub Actions専用ロールに直接CloudFormationを操作する権限があるとは仮定しない。既存のGitHubActions-IndeedAiAssistantDeployはCDK BootstrapロールのAssumeRoleに限定されている。SF6リポジトリはそのIndeed専用ロールを引き受けられないため、専用のGitHubActions-Sf6ReviewDeployを新設する。SF6のworkflowは専用ロールからCDK deploy-roleへrole chainingし、CloudFormation操作は既存cfn-exec-roleで行う。現在のBootstrap権限を実地確認し、不足なら原因を確認して限定した権限を設定する。

## C. 基盤の変更計画

ローカルの現在のAWS認証がCloudFormationの変更計画を作成できる場合:
```bash
.venv/bin/python scripts/plan_foundation.py --vpc-id VPC_ID
```

必要に応じて `--execution-role-arn` に既存のcfn-exec-roleを指定する。スクリプトはchange setを作るだけで実行しない。新規スタックのchange setを作るとREVIEW_IN_PROGRESSのスタック記録ができるが、資源本体はまだ作られない。

出力されたChangeSet ARNを指定し、AWS CLIの `cloudformation describe-change-set` またはコンソールで資源差分を確認する。このテンプレートはSF6専用の基盤のみ。既存Indeedスタックを対象にしない。

計画を確認して環境構築を進めるときは、そのchange setに対して `cloudformation execute-change-set` を実行する。完了後 `describe-stacks` のOutputsを控え、S3の公開禁止、IAMの対象、ログ設定を確認する。これはPC側で行う未実施の手順であり、この文書の存在をデプロイ成功とみなさない。

## D. 手動GitHub Actions

リポジトリ直下の `.github/workflows/sf6-environment.yml` に配置済み。キット内の `integration/github-workflows/sf6-environment.yml` は同じ内容の参照コピー。

masterに置いた後、Actions → SF6 Environment → Run workflow:

- `validate`: PythonテストとCloudFormation lintのみ。AWS接続不要。
- `plan`: VPC IDを指定し、SF6専用OIDC/既存Bootstrap経由でSF6基盤のchange setを作る。デプロイしない。

本体解析の手動起動workflowは、Claudeがruntimeを実装した後に追加する。現在のworkflowは解析起動ボタンではない。

`plan` の前にPCのAWS管理用認証で `infra/github-oidc.json` をSf6ReviewGitHubOidcスタックとして導入する。OIDC Providerは既存の `token.actions.githubusercontent.com` を参照し、新規作成しない。

GitHubSubjectパラメータは必須。SF6の実際のOIDC subjectがデフォルト形式なら `repo:Ueter/sf6-diagnosis:ref:refs/heads/master`、既存Indeedと同じID付き形式なら `repo:Ueter@86462382/sf6-diagnosis@1355560250:ref:refs/heads/master`。SF6側のOIDC subject customization設定を確認して選ぶ。テンプレートはこの2つのみを許可し、audはsts.amazonaws.com固定。ワイルドカードtrustやIndeedロールへの追加はしない。

```bash
aws cloudformation deploy --template-file infra/github-oidc.json --stack-name Sf6ReviewGitHubOidc --parameter-overrides GitHubSubject=確認した完全一致subject --capabilities CAPABILITY_NAMED_IAM --region ap-northeast-1
```

上記は未実施の導入手順。bootstrapロールの権限は基盤作成用の既存経路を使用するため、共有CFN実行ロールの権限もレビューする。実行時のTaskRoleはSF6資源に限定する。

## E. API設定とライブ検証

Google AI Studio側で使える動画対応モデルを確認し、APIキーを取得する。秘密値はチャットへ貼らない。PCのGit管理外 `.env` または既存の秘密管理へ置く。AWSワーカー実装時は `/sf6-review/gemini-api-key` のSSM SecureStringへ安全に投入し、取得した値を出力しない。

同じ設定で利用モデルの現在単価と予算を設定し、初回は0〜900秒に限定する。pilotの精度が出るまでは統計的な全体結論を出さない。最初に「動画を実際に処理できた」「本人を識別できた」「機会の成功と失敗を両方数えられた」を確認する。

## F. Claudeが追加するAWS runtime

Docker worker、ECRへのイメージ登録（immutableなバージョンタグ/ダイジェスト）、ECS TaskDefinition、Step Functions Standard、実行権限、手動start/status/cancel、S3成果物表示を追加する。既存スタックの `deploy --all` を実行しない。

Fargateでの実行はアウトバウンドHTTPS接続が必要。Public SubnetとPublic IPならNATを新設せずに実行できるが、その設定・料金・外部APIの接続を実地確認する。Private Subnetに置く場合は外向き経路を別途計画する。URLの取得失敗をAWSの課題と動画のアクセス制約に切り分ける。

## G. 今回の引継ぎ時点

ローカル環境と静的検証はdocs/validation.mdを参照。AWS資源作成、AWS疎通、Docker build、Gemini接続、実動画の解析は未実施。実際に行ったらPROJECT_STATUS.mdに追記する。
