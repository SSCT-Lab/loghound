import json
import os.path
import re
import sys
from typing import List


def extract_classes_and_content_from_log(logs):
    """
    通过解析对应的数据集，获取日志相关的类名
    :param log_text: 日志信息
    :return: 相关类
    """
    pattern = r'(INFO|DEBUG|WARN|ERROR)\s+([a-zA-Z0-9_.]+):(.*)'
    classes_content = []
    # for line in log_text.split('\n'):
    for line in logs:
        match = re.search(pattern, line)
        if match:
            level = match.group(1)
            full_class_name = match.group(2)
            content = match.group(3)
            if not full_class_name.startswith('org.apache.'):
                full_class_name = 'org.apache.hadoop.' + full_class_name
            classes_content.append({
                'class': full_class_name,
                'type': level,
                'content': content
            })
    return list(classes_content)


def parse_class_names(logs: List[str]) -> List[str]:
    """
    从特定格式的日志数组中解析类名

    参数:
    logs (List[str]): 包含日志条目的列表

    返回:
    List[str]: 解析出的类名列表
    """
    parsed_logs = []

    # 模式1: 匹配 "ClassName.java (line XYZ)" 格式并提取行号
    pattern1 = re.compile(r'([A-Z][A-Za-z0-9_]*)\.java\s+\(line\s+(\d+)\)')
    # 模式2: 匹配包名格式，提取最后一部分类名
    pattern2 = re.compile(r'\s([A-Za-z_][A-Za-z0-9_.]*):')
    # 模式3: 匹配嵌套在方括号中的类名
    pattern3 = re.compile(r'\[([A-Z][A-Za-z0-9_.]*)\]')
    # 模式4: 匹配日志级别
    level_pattern = re.compile(r'^\s*(INFO|ERROR|DEBUG|WARN|TRACE|FATAL)\s*')
    # 模式5: 匹配时间戳
    timestamp_pattern = re.compile(r'\d{4}(-\d{2}){2} (\d{2}:){2}\d{2},\d+')

    for log in logs:
        log = log.strip()
        if not log:
            continue

        # 提取日志级别
        level_match = level_pattern.search(log)
        level = level_match.group(1) if level_match else "UNKNOWN"

        # 提取类名
        class_name = None
        class_pattern_match = None
        line_number = None

        # 先尝试模式1
        match = pattern1.search(log)
        if match:
            class_name = match.group(1)
            line_number = match.group(2)
            class_pattern_match = match
        else:
            # 尝试模式2
            match = pattern2.search(log)
            if match:
                full_name = match.group(1)
                class_name = full_name.split('.')[-1]
                class_pattern_match = match
            else:
                # 尝试模式3
                match = pattern3.search(log)
                if match:
                    class_name_candidate = match.group(1)
                    # 确保提取的是类名而不是线程名
                    if '.' in class_name_candidate:
                        class_name = class_name_candidate.split('.')[-1]
                        class_pattern_match = match

        # 如果找不到类名，设为UNKNOWN
        if not class_name:
            class_name = "UNKNOWN"

        # 提取内容
        content = log

        # 移除级别前缀
        if level_match:
            content = content[level_match.end():].strip()

        # 移除时间戳
        timestamp_match = timestamp_pattern.search(content)
        if timestamp_match:
            content = content[timestamp_match.end():].strip()

        # 移除类名相关部分
        if class_pattern_match:
            content = content.replace(class_pattern_match.group(0), '').strip()

        # 移除方括号中的线程信息 [thread_name]
        thread_pattern = re.compile(r'^\[\s*[^]]+\s*\]\s*')
        thread_match = thread_pattern.search(content)
        if thread_match:
            content = content[thread_match.end():].strip()

        parsed_logs.append({
            'class': class_name,
            'type': level,
            'line': line_number,
            'content': content
        })

    return parsed_logs


def parse_cassandra_log(contents, call_graph):
    for content in contents:
        clazz_name = content['class']
        for clz, data in call_graph.items():
            if clazz_name == clz.split('.')[-1]:
                content['class'] = clz
    return contents


def parse_log_methods_cassandra(content, call_graph):
    """
    专用于Cassandra 通过类来去解析日志文件中的调用方法。
    Args:
        content: 日志涉及的类。
        call_graph: 调用图
    Returns:
        list: 调用方法列表。
    """
    methods_log = {
        'method': "",
        'callee': []
    }
    clazz_name = content['class']
    for clz, clz_data in call_graph.items():
        if clazz_name == clz.split('.')[-1]:
            clz_methods = clz_data['methods']
            # 遍历涉及日志的类的所有方法，找出匹配的日志对应的方法
            for method in clz_methods:
                for method_name, method_data in method.items():
                    logs = method_data['logs']
                    if len(logs) != 0:
                        matched = match_log_event(content['type'], content['content'].strip(), logs)
                        # 如果匹配到目标日志，则将该方法及涉及到的调用方法存入methods_log
                        if matched:
                            methods_log['method'] = method_name
                            for call in method_data['calls']:
                                methods_log['callee'].append(call['callee'])
                                # print(call['callee'])
    return methods_log


def parse_log_methods(content, call_graph):
    """
    通过类来去解析日志文件中的调用方法。
    Args:
        content: 日志涉及的类。
        call_graph: 调用图
    Returns:
        list: 调用方法列表。
    """

    methods_log = {
        'method': "",
        'callee': []
    }
    clazz_name = content['class']
    # clazz_name = content
    if clazz_name not in call_graph:
        return methods_log
    clz = call_graph[clazz_name]
    clz_methods = clz['methods']
    # 遍历涉及日志的类的所有方法，找出匹配的日志对应的方法
    for method in clz_methods:
        for method_name, data in method.items():
            logs = data['logs']
            if len(logs) != 0:
                matched = match_log_event(content['type'], content['content'].strip(), logs)
                # 如果匹配到目标日志，则将该方法及涉及到的调用方法存入methods_log
                if matched:
                    methods_log['method'] = method_name
                    for call in data['calls']:
                        methods_log['callee'].append(call['callee'])
                        # print(call['callee'])
    return methods_log


def match_log_event(level, log, log_events):
    """
    通过日志事件模板匹配对应的日志内容
    :param level: 日志级别
    :param log: 日志信息
    :param log_events: 日志模板
    :return: 匹配成功与否
    """
    try:
        for event in log_events:
            if len(event['template']) == 0 or event['template'] == "{}":
                return False

            event_level = event['level']
            if level.lower() != event_level.lower():
                continue
            log_event = event['template'].replace('{}', '(.*)')
            match = re.match(log_event, log)
            if match:
                return True
    except Exception as e:
        print(e)
        print(event['template'])

    return False


def reconstruct_execution_paths(log_methods, call_graph):
    """
    根据日志涉及的方法，重构日志的执行路径
    :param log_methods: 打印出日志涉及的方法
    :param call_graph: 完整的调用图
    :return: 多条执行路径
    """
    # 过滤掉空方法
    valid_methods = [m for m in log_methods if m['method']]

    # 深度优先搜索函数
    def dfs(method_full_name, visited):
        if method_full_name in visited:
            return None
        visited = visited.union({method_full_name})

        # 解析类名和方法名
        if '#' not in method_full_name:
            return {method_full_name: []}  # 处理没有类名的方法

        class_name, method_simple_name = method_full_name.split('#', 1)

        path = {method_full_name: []}

        # 在调用图中查找类和方法
        if class_name in call_graph:
            class_info = call_graph[class_name]
            # 查找类中的方法
            for method_entry in class_info.get('methods', []):
                for method_entry_name, method_data in method_entry.items():
                    if method_entry_name == method_full_name:
                        callees = method_data['calls']
                        for callee in callees:
                            # 构建被调用者的完整名称
                            callee_full_name = callee['callee']

                            # 递归构建子路径
                            sub_path = dfs(callee_full_name, visited)
                            if sub_path:
                                path[method_full_name].append(sub_path)
                        break  # 找到方法后跳出循环

        return path

    # 为每个有效方法构建执行路径
    execution_paths = []
    for method in valid_methods:
        method_name = method['method']
        path = dfs(method_name, set())
        if path:
            execution_paths.append(path)

    return execution_paths


def generate_call_graph(data):
    try:
        title = data['title']
        if os.path.exists(f"call_graph/{title}-path.json"):
            print(f"{title}的调用图已存在")
            return json.load(open(f"call_graph/{title}-path.json", 'r', encoding='utf-8'))

        logs = data['logs']
        version = data['version']
        if title.startswith("HDFS") or title.startswith("MAPREDUCE"):
            version = version.replace("MAPREDUCE", "hadoop")
            version = version.replace("HDFS", "hadoop")
        print(version)
        print("正在解析日志文件...")
        # 提取类名和日志信息
        classes = extract_classes_and_content_from_log(logs)
        # 输出结果
        print(f"从文件 '{file_path}' 中提取到 {len(classes)} 个类名：")
        print(classes)
        print("正在解析调用树...")
        if len(logs) == 0:
            print(f"{title}没有找到日志")
            return {}

        if os.path.exists(f'full_info/{version}.json'):
            print(f"full_info/{version}.json 文件不存在，无法加载完整的AST......")
            return {}

        print("读取AST，从而识别调用树.....")
        with open(f'full_info/{version}.json', 'r', encoding='utf-8') as file:
            call_graph = json.load(file)

        methods = []
        if title.startswith('Cassandra'):
            print("正在解析Cassandra日志...")
            for clazz in classes:
                method_log = parse_log_methods_cassandra(clazz, call_graph)
                methods.append(method_log)
        else:
            print("正在解析其他日志...")
            for clazz in classes:
                method_log = parse_log_methods(clazz, call_graph)
                methods.append(method_log)

        print(methods)
        print("正在构建执行路径...")
        execution_paths = reconstruct_execution_paths(methods, call_graph)
        print(f"构建了 {len(execution_paths)} 条执行路径")

        with open(f'call_graph/{title}-path.json', 'w', encoding='utf-8') as f:
            json.dump(execution_paths, f, indent=2, ensure_ascii=False)
            print(f"已保存到文件 '{f.name}'")

        return execution_paths
    except FileNotFoundError:
        print(f"错误：找不到文件 '{file_path}'")
        sys.exit(1)
    except Exception as e:
        print(f"发生未知错误：{e}")
        sys.exit(1)


if __name__ == '__main__':
    file_path = r'parsed_enhanced_logs.json'
    generate_call_graph(file_path)