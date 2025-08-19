import csv
import json
import os
import glob

# 存储方法覆盖率和覆盖测试的字典
input_dir = "/Users/linzheyuan/loghound/tgt_sys/coverage_out"

for csv_file in glob.glob(os.path.join(input_dir, "ha021-new_coverage.csv")):
    method_coverage_and_tests = {}
    print(f"Processing {csv_file}...")
    # 假设数据存储在一个名为 input_data.csv 的文件中，你可以根据实际情况修改
    # with open(csv_file, "r", encoding="utf-8") as file:
    #     reader = csv.reader(file)
    #     next(reader)
    #     for row in reader:
    #         method_sig = row[1]
    #         internal_covered = int(row[2])
    #         internal_total = int(row[3])
    #         covering_test_full = row[4]
    #         # 去除测试名称中 @ 符号后的调用点位信息
    #         covering_test = covering_test_full.split('@')[0]
    #
    #         coverage = 0 if internal_total == 0 else internal_covered / internal_total
    #
    #         if method_sig not in method_coverage_and_tests:
    #             method_coverage_and_tests[method_sig] = {
    #                 'coverage': coverage,
    #                 'tests': [covering_test]
    #             }
    #         else:
    #             # 保留最大覆盖率（避免被后一个覆盖掉更高的值）
    #             method_coverage_and_tests[method_sig]["coverage"] = max(
    #                 method_coverage_and_tests[method_sig]["coverage"], coverage
    #             )
    #             method_coverage_and_tests[method_sig]["tests"].append(covering_test)
    #
    #         # 准备要输出到 JSON 文件的数据
    #         output_data = []
    #         for method_sig, info in method_coverage_and_tests.items():
    #             output_data.append({
    #                 "method_sig": method_sig,
    #                 "coverage": info["coverage"],
    #                 "covering_tests": list(set(info["tests"]))  # 去重
    #             })
    #         # 利用 file.name 获取当前输入 CSV 的完整路径
    #         csv_path = file.name
    #         csv_dir = "/Users/linzheyuan/loghound/tgt_sys/coverage_out/json"
    #         csv_base = os.path.splitext(os.path.basename(csv_path))[0]
    #
    #         # 1) 先生成“单文件 JSON”
    #         single_json_path = os.path.join(csv_dir, f"{csv_base}_method_coverage.json")
    #
    #         # 将数据输出到 JSON 文件
    #         with open(single_json_path, 'w', encoding='utf-8') as json_file:
    #             json.dump(output_data, json_file, ensure_ascii=False, indent=4)
    with open(csv_file, "r", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader)  # 跳过表头

        # 遍历一次，边累积边更新
        for row in reader:
            method_sig = row[1]
            internal_covered = int(row[2])
            internal_total = int(row[3])
            covering_test_full = row[4]
            covering_test = covering_test_full.split('@')[0]

            coverage = 0 if internal_total == 0 else internal_covered / internal_total

            if method_sig not in method_coverage_and_tests:
                method_coverage_and_tests[method_sig] = {
                    'coverage': coverage,
                    'tests': {covering_test}  # 用 set 避免重复
                }
            else:
                method_coverage_and_tests[method_sig]['coverage'] = max(
                    method_coverage_and_tests[method_sig]['coverage'], coverage
                )
                method_coverage_and_tests[method_sig]['tests'].add(covering_test)

    # 遍历完成后统一准备输出
    output_data = [
        {
            "method_sig": method_sig,
            "coverage": info["coverage"],
            "covering_tests": list(info["tests"])
        }
        for method_sig, info in method_coverage_and_tests.items()
    ]

    # 利用 file.name 获取路径
    csv_path = file.name
    csv_dir = "/Users/linzheyuan/loghound/tgt_sys/coverage_out/json_new"
    os.makedirs(csv_dir, exist_ok=True)  # 确保输出目录存在
    csv_base = os.path.splitext(os.path.basename(csv_path))[0]

    # 单文件 JSON
    single_json_path = os.path.join(csv_dir, f"{csv_base}_method_coverage.json")
    with open(single_json_path, 'w', encoding='utf-8') as json_file:
        json.dump(output_data, json_file, ensure_ascii=False, indent=4)

