#!/usr/bin/env bash
set -euo pipefail

# ========== 可配置区域 ==========
# 你可以直接在这里填写参数，然后直接 ./batch_run_coverage.sh 运行
ROOT_DIR="${ROOT_DIR:-/Users/linzheyuan/loghound/tgt_sys}"   # 根目录：包含多个数据库子目录
QUERY_FILE="${QUERY_FILE:-/Users/linzheyuan/loghound/ql_script/static-coverage/static_coverage_summary_}" # 你的 .ql 查询文件路径
SEARCH_PATH="${SEARCH_PATH:-}"                    # 若不用 Query Pack 方式运行，需指定 packs 根目录，例如 "$HOME/.codeql/packages:/path/to/codeql"
PARALLEL="${PARALLEL:-1}"                         # 并行度：同时跑几个数据库
DRY_RUN="${DRY_RUN:-false}"                       # true=只打印要跑哪些命令；false=实际执行
OUT_DIR="${OUT_DIR:-./coverage_out}"              # 结果输出目录
# =================================
mkdir -p "$OUT_DIR"
QUERY_FILE_base="${QUERY_FILE}"
# 查找所有数据库目录：判断是否存在 codeql-database.yml
DB_DIRS=()
for f in $(find "$ROOT_DIR" -type f -name "codeql-database.yml"); do
  DB_DIRS+=("$(dirname "$f")")
done

if [[ ${#DB_DIRS[@]} -eq 0 ]]; then
  echo "$ROOT_DIR No CodeQL DB found"
  exit 1
fi

echo "Found ${#DB_DIRS[@]} DBS:"
for d in "${DB_DIRS[@]}"; do
  echo " - $d"
done
echo

run_one() {
  local db="$1"
  local dbname="$(basename "$db")"
  local bqrs_out="$OUT_DIR/${dbname}_coverage.bqrs"
  local json_out="$OUT_DIR/${dbname}_coverage.csv"

  echo "$dbname"
  if [[ "$dbname" == cassandra-* ]]; then
    suffix="cas"
  elif [[ "$dbname" == hadoop-0.21* ]]; then
    suffix="ha021"
  elif [[ "$dbname" == hadoop-0.23* || "$dbname" == hadoop-1.* || "$dbname" == hadoop-2.* ]]; then
    suffix="ha023"
  elif [[ "$dbname" == hbase-0.90* || "$dbname" == hbase-0.92* || "$dbname" == hbase-0.94* ]]; then
    suffix="hb90"
  elif [[ "$dbname" == hbase-0.95* || "$dbname" == hbase-0.96* || "$dbname" == hbase-0.98* ]]; then
    suffix="hb95"
  else
    suffix="zk"  # 默认后缀
  fi

  QUERY_FILE="${QUERY_FILE}${suffix}.ql"
  echo "$QUERY_FILE"

  local run_cmd=(codeql query run "$QUERY_FILE" --database="$db" --output "$bqrs_out")
  if [[ -n "$SEARCH_PATH" ]]; then
    run_cmd+=(--search-path "$SEARCH_PATH")
  fi

  echo "==> [$dbname] running query..."
  "${run_cmd[@]}"

  echo "==> [$dbname] transfer to JSON..."
  codeql bqrs decode "$bqrs_out" --format=csv --output "$json_out"

  echo "==> [$dbname] finished: $json_out"
}

# 批量并行执行（zsh 的内置 job control）

for db in "${DB_DIRS[@]}"; do
  QUERY_FILE="${QUERY_FILE_base}"
  run_one "$db"
done

wait
echo "Finished, check $OUT_DIR"