#!/usr/bin/env zsh
# Bash may causes some unexpected errors

# urls
urls=(
    "https://archive.apache.org/dist/cassandra/0.6.5/apache-cassandra-0.6.5-src.tar.gz",
    "https://archive.apache.org/dist/cassandra/0.7.0/apache-cassandra-0.7.0-beta1-src.tar.gz",
    "https://archive.apache.org/dist/cassandra/0.8.0/apache-cassandra-0.8.0-beta1-src.tar.gz",
    "https://archive.apache.org/dist/cassandra/1.0.0/apache-cassandra-1.0.0-rc2-src.tar.gz",
    "https://archive.apache.org/dist/cassandra/1.2.0/apache-cassandra-1.2.0-src.tar.gz",
    "https://archive.apache.org/dist/cassandra/2.0.0/apache-cassandra-2.0.0-src.tar.gz",
    "https://archive.apache.org/dist/hadoop/common/hadoop-0.21.0/hadoop-0.21.0.tar.gz",
    "https://archive.apache.org/dist/hadoop/common/hadoop-0.22.0/hadoop-0.22.0.tar.gz",
    "https://archive.apache.org/dist/hadoop/common/hadoop-0.23.0/hadoop-0.23.0.tar.gz",
    "https://archive.apache.org/dist/hadoop/common/hadoop-1.2.0/hadoop-1.2.0.tar.gz",
    "https://archive.apache.org/dist/hadoop/common/hadoop-2.0.0-alpha/hadoop-2.0.0-alpha-src.tar.gz",
    "https://archive.apache.org/dist/hadoop/common/hadoop-2.1.1-beta/hadoop-2.1.1-beta-src.tar.gz",
    "https://archive.apache.org/dist/hadoop/common/hadoop-2.2.0/hadoop-2.2.0-src.tar.gz",
    "https://archive.apache.org/dist/hadoop/common/hadoop-2.3.0/hadoop-2.3.0-src.tar.gz",
    "https://archive.apache.org/dist/hadoop/common/hadoop-2.6.0/hadoop-2.6.0-src.tar.gz",
    "https://archive.apache.org/dist/hbase/hbase-0.90.0/hbase-0.90.0.tar.gz",
    "https://archive.apache.org/dist/hbase/hbase-0.92.0/hbase-0.92.0.tar.gz",
    "https://archive.apache.org/dist/hbase/hbase-0.94.0/hbase-0.94.0.tar.gz",
    "https://archive.apache.org/dist/hbase/hbase-0.95.0/hbase-0.95.0-src.tar.gz",
    "https://archive.apache.org/dist/hbase/hbase-0.96.1/hbase-0.96.1-src.tar.gz",
    "https://archive.apache.org/dist/hbase/hbase-0.98.0/hbase-0.98.0-src.tar.gz",
    "https://github.com/apache/zookeeper/archive/refs/tags/release-3.3.0.tar.gz",
    "https://archive.apache.org/dist/zookeeper/zookeeper-3.5.0-alpha/zookeeper-3.5.0-alpha.tar.gz"
)

filenames=(
    "apache-cassandra-0.6.5-src.tar.gz",
    "apache-cassandra-0.7.0-beta1-src.tar.gz",
    "apache-cassandra-0.8.0-beta1-src.tar.gz",
    "apache-cassandra-1.0.0-rc2-src.tar.gz",
    "apache-cassandra-1.2.0-src.tar.gz",
    "apache-cassandra-2.0.0-src.tar.gz",
    "hadoop-0.21.0.tar.gz",
    "hadoop-0.22.0.tar.gz",
    "hadoop-0.23.0.tar.gz",
    "hadoop-1.2.0.tar.gz",
    "hadoop-2.0.0-alpha-src.tar.gz",
    "hadoop-2.1.1-beta-src.tar.gz",
    "hadoop-2.2.0-src.tar.gz",
    "hadoop-2.3.0-src.tar.gz",
    "hadoop-2.6.0-src.tar.gz",
    "hbase-0.90.0.tar.gz",
    "hbase-0.92.0.tar.gz",
    "hbase-0.94.0.tar.gz",
    "hbase-0.95.0.tar.gz",
    "hbase-0.96.1.tar.gz",
    "hbase-0.98.0.tar.gz",
    "release-3.3.0.tar.gz",
    "zookeeper-3.5.0-alpha.tar.gz"
)

# folders name
folders=(
    "cassandra-0.6.5",
    "cassandra-0.7.0-beta1",
    "cassandra-0.8.0-beta1",
    "cassandra-1.0.0-rc2",
    "cassandra-1.2.0",
    "cassandra-2.0.0",
    "hadoop-0.21.0",
    "hadoop-0.22.0",
    "hadoop-0.23.0",
    "hadoop-1.2.0",
    "hadoop-2.0.0-alpha",
    "hadoop-2.1.1-beta",
    "hadoop-2.2.0",
    "hadoop-2.3.0",
    "hadoop-2.6.0",
    "hbase-0.90.0",
    "hbase-0.92.0",
    "hbase-0.94.0",
    "hbase-0.95.0",
    "hbase-0.96.1",
    "hbase-0.98.0",
    "zookeeper-3.3.0",
    "zookeeper-3.5.0"
)

for index in "${!urls[@]}"; do
    url="${urls[$index]}"
    filename="${filenames[$index]}"
    folder="${folders[$index]}"

    if [ -d "$folder" ]; then
        echo "Folder $folder already exists. Skipping download and decompression..."
    else

        echo "Downloading $filename..."
        wget "$url"


        extension="${filename##*.}"


        echo "Decompressing $filename..."
        if [ "$extension" == "gz" ]; then
            tar -xzvf "$filename"
        elif [ "$extension" == "zip" ]; then
            unzip "$filename"
            elif [ "$extension" == "tgz" ]; then
                        tar -xzvf "$filename"
        else
            echo "Unknown file extension: $extension. Skipping decompression..."
        fi


        echo "Deleting $filename..."
        rm "$filename"
    fi
done

echo "All files are downloaded and decompressed!"
