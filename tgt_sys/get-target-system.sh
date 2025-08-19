#!/usr/bin/env bash

# urls
urls=(
    "https://archive.apache.org/dist/cassandra/0.6.5/apache-cassandra-0.6.5-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/0.7.0/apache-cassandra-0.7.0-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/0.7.0/apache-cassandra-0.7.0-beta1-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/0.7.6/apache-cassandra-0.7.6-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/0.8.0/apache-cassandra-0.8.0-beta1-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/0.8.1/apache-cassandra-0.8.1-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/0.8.2/apache-cassandra-0.8.2-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/0.8.7/apache-cassandra-0.8.7-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/1.0.0/apache-cassandra-1.0.0-rc2-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/1.0.10/apache-cassandra-1.0.10-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/1.0.5/apache-cassandra-1.0.5-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/1.0.7/apache-cassandra-1.0.7-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/1.1.10/apache-cassandra-1.1.10-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/1.1.11/apache-cassandra-1.1.11-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/1.1.5/apache-cassandra-1.1.5-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/1.2.0/apache-cassandra-1.2.0-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/1.2.1/apache-cassandra-1.2.1-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/1.2.10/apache-cassandra-1.2.10-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/1.2.15/apache-cassandra-1.2.15-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/1.2.4/apache-cassandra-1.2.4-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/1.2.7/apache-cassandra-1.2.7-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/1.2.8/apache-cassandra-1.2.8-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/2.0.1/apache-cassandra-2.0.1-src.tar.gz"
    "https://archive.apache.org/dist/cassandra/2.0.4/apache-cassandra-2.0.4-src.tar.gz"


    "https://archive.apache.org/dist/hadoop/common/hadoop-0.21.0/hadoop-0.21.0.tar.gz"
    "https://archive.apache.org/dist/hadoop/common/hadoop-0.23.0/hadoop-0.23.0-src.tar.gz"
    "https://archive.apache.org/dist/hadoop/common/hadoop-0.23.6/hadoop-0.23.6-src.tar.gz"
    "https://archive.apache.org/dist/hadoop/common/hadoop-1.2.0/hadoop-1.2.0.tar.gz"
    "https://archive.apache.org/dist/hadoop/common/hadoop-2.0.0-alpha/hadoop-2.0.0-alpha-src.tar.gz"
    "https://archive.apache.org/dist/hadoop/common/hadoop-2.0.2-alpha/hadoop-2.0.2-alpha-src.tar.gz"
    "https://archive.apache.org/dist/hadoop/common/hadoop-2.0.3-alpha/hadoop-2.0.3-alpha-src.tar.gz"
    "https://archive.apache.org/dist/hadoop/common/hadoop-2.0.4-alpha/hadoop-2.0.4-alpha-src.tar.gz"
    "https://archive.apache.org/dist/hadoop/common/hadoop-2.1.1-beta/hadoop-2.1.1-beta-src.tar.gz"
    "https://archive.apache.org/dist/hadoop/common/hadoop-2.2.0/hadoop-2.2.0-src.tar.gz"
    "https://archive.apache.org/dist/hadoop/common/hadoop-2.3.0/hadoop-2.3.0-src.tar.gz"
    "https://archive.apache.org/dist/hadoop/common/hadoop-2.6.0/hadoop-2.6.0-src.tar.gz"

    "https://archive.apache.org/dist/hbase/hbase-0.90.0/hbase-0.90.0.tar.gz"
    "https://archive.apache.org/dist/hbase/hbase-0.92.0/hbase-0.92.0.tar.gz"
    "https://archive.apache.org/dist/hbase/hbase-0.94.0/hbase-0.94.0.tar.gz"
    "https://archive.apache.org/dist/hbase/hbase-0.95.0/hbase-0.95.0-src.tar.gz"
    "https://archive.apache.org/dist/hbase/hbase-0.96.1/hbase-0.96.1-src.tar.gz"
    "https://archive.apache.org/dist/hbase/hbase-0.98.0/hbase-0.98.0-src.tar.gz"

    "https://github.com/apache/zookeeper/archive/refs/tags/release-3.3.0.tar.gz"
    "https://archive.apache.org/dist/zookeeper/zookeeper-3.5.0-alpha/zookeeper-3.5.0-alpha.tar.gz"
)
filenames=(
    "apache-cassandra-0.6.5-src.tar.gz"
    "apache-cassandra-0.7.0-src.tar.gz"
    "apache-cassandra-0.7.0-beta1-src.tar.gz"
    "apache-cassandra-0.7.6-src.tar.gz"
    "apache-cassandra-0.8.0-beta1-src.tar.gz"
    "apache-cassandra-0.8.1-src.tar.gz"
    "apache-cassandra-0.8.2-src.tar.gz"
    "apache-cassandra-0.8.7-src.tar.gz"
    "apache-cassandra-1.0.0-rc2-src.tar.gz"
    "apache-cassandra-1.0.10-src.tar.gz"
    "apache-cassandra-1.0.5-src.tar.gz"
    "apache-cassandra-1.0.7-src.tar.gz"
    "apache-cassandra-1.1.10-src.tar.gz"
    "apache-cassandra-1.1.11-src.tar.gz"
    "apache-cassandra-1.1.5-src.tar.gz"
    "apache-cassandra-1.2.0-src.tar.gz"
    "apache-cassandra-1.2.1-src.tar.gz"
    "apache-cassandra-1.2.10-src.tar.gz"
    "apache-cassandra-1.2.15-src.tar.gz"
    "apache-cassandra-1.2.4-src.tar.gz"
    "apache-cassandra-1.2.7-src.tar.gz"
    "apache-cassandra-1.2.8-src.tar.gz"
    "apache-cassandra-2.0.1-src.tar.gz"
    "apache-cassandra-2.0.4-src.tar.gz"

    "hadoop-0.21.0.tar.gz"
    "hadoop-0.23.0-src.tar.gz"
    "hadoop-0.23.6-src.tar.gz"
    "hadoop-1.2.0.tar.gz"
    "hadoop-2.0.0-alpha-src.tar.gz"
    "hadoop-2.0.2-alpha-src.tar.gz"
    "hadoop-2.0.3-alpha-src.tar.gz"
    "hadoop-2.0.4-alpha-src.tar.gz"
    "hadoop-2.1.1-beta-src.tar.gz"
    "hadoop-2.2.0-src.tar.gz"
    "hadoop-2.3.0-src.tar.gz"
    "hadoop-2.6.0-src.tar.gz"

    "hbase-0.90.0.tar.gz"
    "hbase-0.92.0.tar.gz"
    "hbase-0.94.0.tar.gz"
    "hbase-0.95.0-src.tar.gz"
    "hbase-0.96.1-src.tar.gz"
    "hbase-0.98.0-src.tar.gz"

    "zookeeper-release-3.3.0.tar.gz"
    "zookeeper-3.5.0-alpha.tar.gz"
)

folders=(
    "cassandra-0.6.5"
    "cassandra-0.7.0"
    "cassandra-0.7.0-beta1"
    "cassandra-0.7.6"
    "cassandra-0.8.0-beta1"
    "cassandra-0.8.1"
    "cassandra-0.8.2"
    "cassandra-0.8.7"
    "cassandra-1.0.0-rc2"
    "cassandra-1.0.10"
    "cassandra-1.0.5"
    "cassandra-1.0.7"
    "cassandra-1.1.10"
    "cassandra-1.1.11"
    "cassandra-1.1.5"
    "cassandra-1.2.0"
    "cassandra-1.2.1"
    "cassandra-1.2.10"
    "cassandra-1.2.15"
    "cassandra-1.2.4"
    "cassandra-1.2.7"
    "cassandra-1.2.8"
    "cassandra-2.0.1"
    "cassandra-2.0.4"

    "hadoop-0.21.0"
    "hadoop-0.23.0"
    "hadoop-0.23.6"
    "hadoop-1.2.0"
    "hadoop-2.0.0-alpha"
    "hadoop-2.0.2-alpha"
    "hadoop-2.0.3-alpha"
    "hadoop-2.0.4-alpha"
    "hadoop-2.1.1-beta"
    "hadoop-2.2.0"
    "hadoop-2.3.0"
    "hadoop-2.6.0"

    "hbase-0.90.0"
    "hbase-0.92.0"
    "hbase-0.94.0"
    "hbase-0.95.0"
    "hbase-0.96.1"
    "hbase-0.98.0"

    "zookeeper-3.3.0"
    "zookeeper-3.5.0-alpha"
)


# 先构造要下载的 URL / 文件名列表
urls_to_download=()
filenames_to_download=()
folders_to_download=()

for index in {1..$#urls}; do
    folder="${folders[$index]}"
    if [ -d "$folder" ]; then
        echo "Folder $folder already exists. Skipping..."
    else
        urls_to_download+=("${urls[$index]}")
        filenames_to_download+=("${filenames[$index]}")
        folders_to_download+=("$folder")
    fi
done

echo "Check over!"

# 如果没有需要下载的就退出
if [ ${#urls_to_download[@]} -eq 0 ]; then
    echo "All folders already exist. Nothing to download."
    exit 0
fi

echo "Start downloading..."

# 批量下载（从数组传给 wget -i -）
# printf "%s\n" "${urls_to_download[@]}" | xargs -n 1 -P 4 wget -c -i - -nv --show-progress

# 批量
printf "%s\n" "${urls_to_download[@]}" | aria2c -x 16 -s 16 -j 8 -i -


# 解压并删除压缩包
for i in {1..$#filenames_to_download}; do
    filename="${filenames_to_download[$i]}"
    folder="${folders_to_download[$i]}"
    mkdir -p "$folder"

    echo "Decompressing $filename..."
    extension="${filename##*.}"
    if [ "$extension" = "gz" ] || [ "$extension" = "tgz" ]; then
        tar -xzf "$filename" -C "$folder" --strip-components 1
    elif [ "$extension" = "zip" ]; then
        unzip -q "$filename" -d "$folder"
    else
        echo "Unknown extension: $extension. Skipping..."
    fi

    echo "Deleting $filename..."
    rm -f "$filename"
done

echo "All files are downloaded and decompressed!"

