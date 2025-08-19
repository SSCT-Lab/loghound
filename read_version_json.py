import json

filename = 'parsed_enhanced_logs.json'

with open(filename) as f:
    data = json.load(f)
    version_dict = set()
    for entry in data:
        version_dict.add(entry['version'].replace("MAPREDUCE", "hadoop").replace("HDFS", "hadoop"))

print(len(version_dict))
print(version_dict)

version_list=list(set(version_dict))
version_list.sort()

print(len(version_list))
print(version_list)

folders = [
    "cassandra-0.6.5",
    "cassandra-0.7.0-beta1",
    "cassandra-0.8.0-beta1",
    "cassandra-1.0.0-rc2",
    "cassandra-1.2.0",
    "cassandra-2.0.0",
    "hadoop-0.21.0",
    "hadoop-0.22.0",
    "hadoop-0.23.0",
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
    "zookeeper-3.5.0",
    "zookeeper-3.3.0"
]

print(len(folders))

for item in version_list:
    if item in folders:
        version_list.remove(item)

print(len(version_list))
print(version_list)

