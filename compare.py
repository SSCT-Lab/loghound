import json

import pandas as pd
import re


def process_excel_file(file_path):
    try:
        # 读取Excel文件
        df = pd.read_excel(file_path)

        # 检查数据格式是否符合预期
        if 'title' not in df.columns or 'Components' not in df.columns:
            raise ValueError("Excel文件中未找到'title'或'Components'列")

        # 初始化结果列表
        result = []

        # 遍历每一行数据
        for index, row in df.iterrows():
            # 获取标题
            title = row['title']

            # 处理Methods列，将其分割为数组
            methods_str = str(row['Methods'])
            methods_list = [item.strip() for item in methods_str.split(',') if item.strip()]

            # 处理Components列，将其分割为数组
            components_str = str(row['Components'])
            components_list = [item.strip().replace("/", ".") for item in components_str.split(',') if item.strip()]

            classes_str = str(row["Classes"])
            classes_list = [item.strip() for item in classes_str.split(",") if item.strip()]
            # 提取类名和方法名
            # processed_methods = []
            # for method in methods_list:
            #     # 使用正则表达式匹配最后一个斜杠后的内容
            #     match = re.search(r'([^/]+)$', method)
            #     if match:
            #         processed_methods.append(match.group(1))
            #     else:
            #         # 如果没有匹配到，保留原始内容
            #         processed_methods.append(method)

            # 添加到结果列表
            result.append({
                "title": title,
                # "methods": processed_methods
                "methods": methods_list,
                "components": components_list,
                "classes": classes_list
            })

        return result

    except FileNotFoundError:
        print(f"错误：文件 '{file_path}' 未找到")
        return []
    except Exception as e:
        print(f"发生错误：{e}")
        return []


def process_ref_data(ref_data):
    for item in ref_data:
        item["methods"] = [method.replace("$", "#").split("/")[-1] for method in item["methods"]]

def process_json_file(file_path):
    """从JSON文件加载数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"错误：文件 '{file_path}' 未找到")
        return []
    except json.JSONDecodeError:
        print(f"错误：文件 '{file_path}' 不是有效的JSON格式")
        return []
    except Exception as e:
        print(f"发生错误：{e}")
        return []


def classify_by_system(titles):
    """
    根据title开头将其分类到不同系统类型

    返回:
    分类字典，键为系统类型，值为对应title列表
    """
    systems = {
        'Cassandra': [],
        'HDFS': [],
        'MAPREDUCE': [],
        'ZooKeeper': [],
        'HBase': [],
    }

    for title in titles:
        if title.startswith('CASSANDRA') or title.startswith('Cassandra'):
            systems['Cassandra'].append(title)
        elif title.startswith('HDFS'):
            systems['HDFS'].append(title)
        elif title.startswith('MAPREDUCE') or title.startswith('MAPREDUCE'):
            systems['MAPREDUCE'].append(title)
        elif title.startswith('ZOOKEEPER') or title.startswith('ZooKeeper'):
            systems['ZooKeeper'].append(title)
        elif title.startswith('HBASE') or title.startswith('HBase'):
            systems['HBase'].append(title)

    return systems


def compare(generated_data, reference_data):
    """
    对比两个数据集并计算Accuracy, Recall和F1 Score

    参数:
    generated_data: 生成的数据集，格式为[{"title": "xxx", "location": [...]}, ...]
    reference_data: 参考数据集，格式为[{"title": "xxx", "methods": [...], "components": [...]}, ...]

    返回:
    包含整体评估指标和每个title详细评估的字典
    """
    # 将数据转换为以title为键的字典，便于查找
    # generated_dict = {item['title']: set(item.get('FaultLocation', [])) for item in generated_data}
    # reference_dict = {item['title']: set(item.get('methods', [])) for item in reference_data}
    generated_dict = {item['title']: item.get('location', []) for item in generated_data}
    reference_dict = {item['title']: item.get('components', []) for item in reference_data}
    classes_dict = {item['title']: item.get('classes', []) for item in reference_data}
    # print(reference_dict)
    # 初始化各系统统计结果
    system_results = {
        'Cassandra': {'top1': 0, 'top3': 0, "top5": 0, 'total': 33, 'titles': 0},
        'HDFS': {'top1': 0, 'top3': 0, "top5": 0, 'total': 15, 'titles': 0},
        'MAPREDUCE': {'top1': 0, 'top3': 0, "top5": 0, 'total': 26, 'titles': 0},
        'ZooKeeper': {'top1': 0, 'top3': 0, "top5": 0, 'total': 8, 'titles': 0},
        'HBase': {'top1': 0, 'top3': 0, "top5": 0, 'total': 24, 'titles': 0},
        'Overall': {'top1': 0, 'top3': 0, "top5": 0, 'total': 106, 'titles': 0}
    }

    all_titles = reference_dict.keys()
    system_titles = classify_by_system(all_titles)
    error_res = []

    # 遍历每个title，按系统类型统计
    for system, titles in system_titles.items():
        system_results[system]['titles'] = len(titles)

        for title in titles:
            # 获取对应title的生成数据和参考数据，如果不存在则为空集
            gen_methods = generated_dict.get(title, set())
            ref_methods = reference_dict.get(title, set())

            correct_1 = 0
            correct_3 = 0
            correct_5 = 0
            # 计算正确匹配的项数
            for k, component in enumerate(gen_methods):
                component = component.replace("\\", ".").replace(".java", "")
                if k == 0 and check(component, ref_methods, classes_dict[title]):
                    correct_1 += 1
                    correct_3 += 1
                    correct_5 += 1
                    break
                elif 3 > k > 0 == correct_3 and check(component, ref_methods, classes_dict[title]):
                    correct_3 += 1
                    correct_5 += 1
                    break
                elif 3 <= k < 5 and check(component, ref_methods, classes_dict[title]) and correct_5 == 0:
                    correct_5 += 1
                # else:
                #     break
            # 更新系统统计
            if correct_1 == 0 and correct_3 == 0 and correct_5 == 0:
                error_res.append({
                    'title': title,
                    'generated_methods': gen_methods,
                    'reference_methods': ref_methods
                })
            system_results[system]['top1'] += correct_1
            system_results[system]['top3'] += correct_3
            system_results[system]['top5'] += correct_5
            # system_results[system]['total'] += len(gen_methods)

            # 更新总体统计
            system_results['Overall']['top1'] += correct_1
            system_results['Overall']['top3'] += correct_3
            system_results['Overall']['top5'] += correct_5
            # system_results['Overall']['total'] += len(gen_methods)
            system_results['Overall']['titles'] += 1

    # 计算各系统的匹配成功率
    for system, stats in system_results.items():
        if stats['total'] > 0:
            # print(stats['total'])
            stats['top1_match_rate'] = stats['top1'] / stats['total']
            stats['top3_match_rate'] = stats['top3'] / stats['total']
            stats['top5_match_rate'] = stats['top5'] / stats['total']
        else:
            stats['top1_match_rate'] = 0
            stats['top3_match_rate'] = 0
            stats['top5_match_rate'] = 0

    return system_results, error_res


def compare_methods(generated_data, reference_data):
    """
    对比两个数据集并计算Accuracy, Recall和F1 Score

    参数:
    generated_data: 生成的数据集，格式为[{"title": "xxx", "location": [...]}, ...]
    reference_data: 参考数据集，格式为[{"title": "xxx", "methods": [...], "components": [...]}, ...]

    返回:
    包含整体评估指标和每个title详细评估的字典
    """
    # 将数据转换为以title为键的字典，便于查找
    generated_dict = {item['title']: item.get('location', []) for item in generated_data}
    reference_dict = {item['title']: item.get('methods', []) for item in reference_data}
    # print(reference_dict)
    # 初始化各系统统计结果
    system_results = {
        'Cassandra': {'top1': 0, 'top3': 0, "top5": 0, 'total': 33, 'titles': 0},
        'HDFS': {'top1': 0, 'top3': 0, "top5": 0, 'total': 15, 'titles': 0},
        'MAPREDUCE': {'top1': 0, 'top3': 0, "top5": 0, 'total': 26, 'titles': 0},
        'ZooKeeper': {'top1': 0, 'top3': 0, "top5": 0, 'total': 8, 'titles': 0},
        'HBase': {'top1': 0, 'top3': 0, "top5": 0, 'total': 24, 'titles': 0},
        'Overall': {'top1': 0, 'top3': 0, "top5": 0, 'total': 106, 'titles': 0}
    }

    all_titles = reference_dict.keys()
    system_titles = classify_by_system(all_titles)
    error_res = []

    # 遍历每个title，按系统类型统计
    for system, titles in system_titles.items():
        system_results[system]['titles'] = len(titles)

        for title in titles:
            # 获取对应title的生成数据和参考数据，如果不存在则为空集
            gen_methods = generated_dict.get(title, set())
            ref_methods = reference_dict.get(title, set())

            correct_1 = 0
            correct_3 = 0
            correct_5 = 0
            # 计算正确匹配的项数
            for k, method in enumerate(gen_methods):
                method = method.replace("$", "\\").split("\\")[-1]
                if k == 0 and method in ref_methods:
                    correct_1 += 1
                    correct_3 += 1
                    correct_5 += 1
                    break
                elif 3 > k > 0 == correct_3 and method in ref_methods:
                    correct_3 += 1
                    correct_5 += 1
                    break
                elif 3 <= k < 5 and method in ref_methods and correct_5 == 0:
                    correct_5 += 1
                # else:
                #     break
            # 更新系统统计
            if correct_1 == 0 and correct_3 == 0 and correct_5 == 0:
                error_res.append({
                    'title': title,
                    'generated_methods': gen_methods,
                    'reference_methods': ref_methods
                })
            system_results[system]['top1'] += correct_1
            system_results[system]['top3'] += correct_3
            system_results[system]['top5'] += correct_5
            # system_results[system]['total'] += len(gen_methods)

            # 更新总体统计
            system_results['Overall']['top1'] += correct_1
            system_results['Overall']['top3'] += correct_3
            system_results['Overall']['top5'] += correct_5
            # system_results['Overall']['total'] += len(gen_methods)
            system_results['Overall']['titles'] += 1

    # 计算各系统的匹配成功率
    for system, stats in system_results.items():
        if stats['total'] > 0:
            # print(stats['total'])
            stats['top1_match_rate'] = stats['top1'] / stats['total']
            stats['top3_match_rate'] = stats['top3'] / stats['total']
            stats['top5_match_rate'] = stats['top5'] / stats['total']
        else:
            stats['top1_match_rate'] = 0
            stats['top3_match_rate'] = 0
            stats['top5_match_rate'] = 0

    return system_results, error_res


def check(component, ref_component, classes):
    """
    检查生成的方法是否与参考组件或类一致

    参数:
    component: 生成的方法
    ref_methods: 参考方法列表

    返回:
    True表示一致，False表示不一致
    """
    for ref_method in ref_component:
        # if component.startswith(ref_method):
        # if component == ref_method:
        components = component.split('.')
        refs = ref_method.split('.')
        if components[-1] == refs[-1] or components[-1] in classes or (len(components) >= 2 and components[-2] == refs[-1]):
            return True
    return False


def print_metrics(metrics):
    """格式化输出各系统类型的匹配成功率指标"""
    print("\n===== 各系统类型匹配成功率 =====")
    print(f"{'系统类型':<12} {'标题数量':<8} {'top1'} {'top3'} {'top5'}")
    print("-" * 35)

    # 按特定顺序输出主要系统
    systems_order = ['Cassandra', 'HDFS', 'MAPREDUCE', 'ZooKeeper', 'HBase', 'Other', 'Overall']

    for system in systems_order:
        if system in metrics:
            stats = metrics[system]
            print(f"{system:<12} {stats['titles']:<8} {stats['top1_match_rate']:.4f} {stats['top3_match_rate']:.4f} {stats['top5_match_rate']:.4f}")


if __name__ == "__main__":
    # 示例使用
    ref_file_path = 'dbugset_resolve.xlsx'
    gener_file_path = r'ProcessData/methods_total_scores/total_score.json'
    gener_file_path_wo_path = r'ProcessData/methods_total_scores/total_score_wo_path.json'
    generated_data = process_json_file(gener_file_path)
    generated_data_wo_path = process_json_file(gener_file_path_wo_path)
    reference_data = process_excel_file(ref_file_path)
    process_ref_data(reference_data)

    # print(reference_data)
    # print(generated_data)
    if reference_data and generated_data:
        # 对比并输出结果
        metrics, err_res = compare_methods(generated_data, reference_data)
        metrics_wo_path, err_res_wo_path = compare_methods(generated_data_wo_path, reference_data)
        print(metrics)
        print_metrics(metrics)
        print(err_res)

        print("====================================================================")
        print(metrics_wo_path)
        print_metrics(metrics_wo_path)
        print(err_res_wo_path)


    # if reference_data and generated_data:
    #     # 对比并输出结果
    #     metrics, err_res = compare(generated_data, reference_data)
    #     metrics_wo_path, err_res_wo_path = compare(generated_data_wo_path, reference_data)
    #     print(metrics)
    #     print_metrics(metrics)
    #     print(err_res)
    #
    #     print("====================================================================")
    #     print(metrics_wo_path)
    #     print_metrics(metrics_wo_path)
    #     print(err_res_wo_path)