# circleci-orb-finder

[English](./README.md) | 日本語

与えられたツール・タスクに対して CircleCI orb が存在するかを正確に答える [Claude Code Agent Skill](https://code.claude.com/docs/en/skills)。
単純な名前検索では見落とされるケースもカバーします：より大きな orb 内に埋め込まれている機能（例：`uv` Python パッケージマネージャーは独自の orb ではなく、`circleci/python` 内の `pkg-manager: uv` オプション）。

詳細な手順は [`SKILL.md`](./SKILL.md) を参照してください。

## なぜ必要か

orb 名検索だけでは以下の問題が発生します：

- **偽陰性**：ツールがより大きな orb のパラメータとしてサポートされている場合、見つけられない
- **偽陽性**：短いキーワードが無関係な部分文字列にマッチする（`uv` が `villeneuve`、`bouvier`、`trouva` などと誤マッチ）

このスキルはこれらの問題を解決します：名前検索、GitHub 検索、認定 orb のソースコード全体に対するグレップを組み合わせることで、すべての認定 orb を確定的に、該当するかもしれない orb を事前に知る必要なく、検索できます。

## インストール

[skills CLI](https://github.com/vercel-labs/skills) を使用する場合：

```bash
npx skills add hidetaka-cci/circleci-orb-finder --agent claude-code
```

または、このディレクトリを個人またはプロジェクトのスキルフォルダに直接コピー：

```bash
git clone https://github.com/hidetaka-cci/circleci-orb-finder.git \
  ~/.claude/skills/circleci-orb-finder
```

`circleci`、`gh`、`jq` が `PATH` に含まれ、`circleci` と `gh` が認証済みである必要があります。

## ディレクトリ構成

```
SKILL.md                  # Claude が従う手順書
scripts/
  search_by_name.sh        # orb 名検索（認定＋未認定）
  search_github.sh         # GitHub コード/リポジトリ検索
  search_by_content.sh     # 認定 orb ソース全体に対するフルコンテンツグレップ（キャッシュ済み）
  verify_orb.sh             # 特定候補のメタデータ + ソース確認
evals/                     # evals/README.md を参照
  cases/
    skill-routing-cases.json   # フレーズベースのルーティング回帰テスト（LLMなし、ネットワークなし）
    functional-cases.json      # 実際の検索スクリプト出力回帰テスト（ライブネットワーク）
  scripts/
    run_routing_evals.py       # CI で実行 — .circleci/config.yml を参照
    run_functional_evals.sh    # ローカル専用、evals/README.md を参照
```

## 設計の参考元

- [anthropics/skills](https://github.com/anthropics/skills) の `skill-creator`：Agent Skills 作成形式とプログレッシブディスクロージャーモデル
- [CircleCI-Public/skills](https://github.com/CircleCI-Public/skills) の eval 階層化：軽量な決定論的チェックを CI で実行し、実際の呼び出しやライブネットワークが必要なチェックはローカル専用

## ライセンス

MIT — [LICENSE](./LICENSE) を参照。
