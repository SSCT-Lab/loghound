#!/bin/bash

# 定义需要排除的目录列表
EXCLUDED_DIRS=(
    "zookeeper-3.5.0-alpha"
    "apache-cassandra-2.0.0-src"
    "codeql2"
    "java-se-7u75-ri"
)

# 遍历当前目录下的所有子目录
for dir in */; do
    # 移除目录名末尾的斜杠
    dir_name=${dir%/}

    # 检查是否是目录
    if [ -d "$dir_name" ]; then
        # 检查当前目录是否在排除列表中
        if [[ " ${EXCLUDED_DIRS[@]} " =~ " $dir_name " ]]; then
            echo "------------------------------------------------"
            echo "跳过排除目录: $dir_name"
            continue
        fi

        echo "------------------------------------------------"
        echo "处理目录: $dir_name"

        # 进入目录
        cd "$dir_name" || {
            echo "无法进入目录 $dir_name，跳过..."
            continue
        }

        # 创建CodeQL数据库，数据库名使用目录名的缩写
        # 提取主要名称和版本号作为数据库名
        db_name=$(echo "$dir_name" | sed -E 's/^apache-|^release-//; s/-src//; s/([a-z]+)-.*/\1/; s/([A-Z][a-z]+)/\L\1/')$(echo "$dir_name" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 | tr -d '.')

        echo "创建CodeQL数据库: $db_name"

        # 执行CodeQL数据库创建命令
        codeql database create "$db_name" \
            --language=java \
            --source-root=. \
            --build-mode=none

        # 返回到上级目录
        cd ..
    fi
done

echo "------------------------------------------------"
echo "所有目录处理完成"