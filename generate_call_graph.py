import json
import re
import sys


def extract_classes_and_content_from_log(log_text):
    """
    通过解析对应的数据集，获取日志相关的类名
    :param log_text: 日志信息
    :return: 相关类
    """
    pattern = r'(INFO|DEBUG|WARN|ERROR)\s+([a-zA-Z0-9_.]+):(.*)'
    classes_content = []
    for line in log_text.split('\n'):
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


if __name__ == '__main__':
    file_path = r'MAPREDUCE-5169.txt'
    try:
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as file:
            datas = file.read()

        print("正在解析日志文件...")
        # 提取类名
        classes = extract_classes_and_content_from_log(datas)
        # 输出结果
        print(f"从文件 '{file_path}' 中提取到 {len(classes)} 个类名：")
        for i, cls in enumerate(classes, 1):
            print(f"{i}. {cls}")
        print("正在解析调用树...")

        with open('test.json', 'r', encoding='utf-8') as file:
            call_graph = json.load(file)

        methods = []
        for clazz in classes:
            method_log = parse_log_methods(clazz, call_graph)
            methods.append(method_log)

        print("正在构建执行路径...")
        execution_paths = reconstruct_execution_paths(methods, call_graph)
        print(execution_paths)

        with open(f'{file_path.split(".")[0]}-path.json', 'w', encoding='utf-8') as f:
            json.dump(execution_paths, f, indent=2, ensure_ascii=False)
        # print(methods.__getitem__(5))
        # log_event = [
        #     {
        #         "log": "Using keytab {}, for principal {}",
        #         "level": "info",
        #         "line": 164
        #     }
        # ]
        #
        # match_log_event('info', "Using keytab sdiagjopasjdg)_jwgiah, for principal jsiadoggiehgo8(", log_event)

    except FileNotFoundError:
        print(f"错误：找不到文件 '{file_path}'")
        sys.exit(1)
    except Exception as e:
        print(f"发生未知错误：{e}")
        sys.exit(1)
