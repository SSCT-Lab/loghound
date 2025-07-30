#!/bin/bash

# urls
urls=(
    "https://archive.apache.org/dist/zookeeper/zookeeper-3.5.8/apache-zookeeper-3.5.8.tar.gz"
)

filenames=(
    "apache-zookeeper-3.5.8.tar.gz"
)

# folders name
folders=(
    "apache-zookeeper-3.5.8"
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
