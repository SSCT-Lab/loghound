#!/usr/bin/env bash
set -euo pipefail

# ========== 可配置区域 ==========
# 你可以直接在这里填写参数，然后直接 ./batch_run_coverage.sh 运行
ROOT_DIR="${ROOT_DIR:-/Users/linzheyuan/loghound/tgt_sys/hadoop-0.21.0}"   # 根目录：包含多个数据库子目录
QUERY_FILE="${QUERY_FILE:-/Users/linzheyuan/loghound/ql_script/static-coverage/static_coverage_summary.ql}" # 你的 .ql 查询文件路径
SEARCH_PATH="${SEARCH_PATH:-}"                    # 若不用 Query Pack 方式运行，需指定 packs 根目录，例如 "$HOME/.codeql/packages:/path/to/codeql"
PARALLEL="${PARALLEL:-1}"                         # 并行度：同时跑几个数据库
DRY_RUN="${DRY_RUN:-false}"                       # true=只打印要跑哪些命令；false=实际执行
OUT_DIR="${OUT_DIR:-./coverage_out}"              # 结果输出目录
# =================================
mkdir -p "$OUT_DIR"

# 查找所有数据库目录：判断是否存在 codeql-database.yml
DB_DIRS=()
for f in $(find "$ROOT_DIR" -type f -name "codeql-database.yml"); do
  DB_DIRS+=("$(dirname "$f")")
done

if [[ ${#DB_DIRS[@]} -eq 0 ]]; then
  echo "❌ 在 $ROOT_DIR 下没有发现 CodeQL 数据库"
  exit 1
fi

echo "✅ 发现 ${#DB_DIRS[@]} 个数据库:"
for d in "${DB_DIRS[@]}"; do
  echo " - $d"
done
echo

run_one() {
  local db="$1"
  local dbname="$(basename "$db")"
  local bqrs_out="$OUT_DIR/${dbname}_coverage.bqrs"
  local json_out="$OUT_DIR/${dbname}_coverage.csv"

  local run_cmd=(codeql query run "$QUERY_FILE" --database="$db" --output "$bqrs_out")
  if [[ -n "$SEARCH_PATH" ]]; then
    run_cmd+=(--search-path "$SEARCH_PATH")
  fi

  echo "==> [$dbname] 正在运行查询..."
  "${run_cmd[@]}"

  echo "==> [$dbname] 转换为 JSON..."
  codeql bqrs decode "$bqrs_out" --format=csv --output "$json_out"

  echo "==> [$dbname] 完成: $json_out"
}

# 批量并行执行（zsh 的内置 job control）
jobs=()
for db in "${DB_DIRS[@]}"; do
  run_one "$db" &
  jobs+=($!)
  # 控制并行度
  if [[ $(jobs -r | wc -l) -ge $PARALLEL ]]; then
    wait -n
  fi
done

wait
echo "🎉 全部完成，结果在 $OUT_DIR"