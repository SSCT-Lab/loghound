import os
import json
import javalang
from javalang.tree import MethodDeclaration, ClassDeclaration, MethodInvocation, VariableDeclaration, Member, \
    ConstantDeclaration, LocalVariableDeclaration, FieldDeclaration
from collections import defaultdict


class HadoopASTParser:
    def __init__(self, source_dir):
        self.source_dir = source_dir
        self.class_map = {}  # 存储类名到类信息的映射
        self.method_calls = defaultdict(list)  # 存储方法调用关系
        self.method_locations = {}  # 存储方法的位置信息
        self.method_variables = defaultdict(dict)  # 存储方法的变量信息
        self.class_variables = defaultdict(dict)  # 存储类的成员变量信息
        self.inheritance_relations = {}  # 存储继承关系
        self.interface_relations = {}  # 存储接口实现关系
        self.parameter_info = defaultdict(list)  # 存储形参和传参信息
        self.method_logs = defaultdict(list)  # 存储方法内的日志语句
    def parse_source_files(self):
        """遍历并解析所有Java源文件"""
        for root, _, files in os.walk(self.source_dir):
            for file in files:
                if file.endswith('.java') and "Test" not in file:
                    file_path = os.path.join(root, file)
                    self._parse_java_file(file_path)

    def _parse_java_file(self, file_path):
        """解析单个Java文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            tree = javalang.parse.parse(content)
            package_name = self._extract_package_name(tree)
            self._extract_classes_and_methods(tree, package_name, file_path)
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")

    def _extract_package_name(self, tree):
        """提取包名"""
        if tree.package:
            return tree.package.name
        return ""

    def _extract_classes_and_methods(self, tree, package_name, file_path):
        """提取类和方法信息"""
        for _, node in tree.filter(ClassDeclaration):
            class_name = f"{package_name}.{node.name}"
            self.class_map[class_name] = node
            self._extract_class_variables(node, class_name, file_path)
            # 记录继承的父类
            parent = node.extends.name if node.extends else ""
            self.inheritance_relations[class_name] = parent
            # 记录实现的接口
            interfaces = [i.name for i in node.implements] if node.implements else []
            self.interface_relations[class_name] = interfaces
            for method in node.methods:
                method_key = f"{class_name}#{method.name}({self._get_method_signature(method)})"
                self.method_locations[method_key] = {
                    'file': file_path,
                    'line': method.position.line if method.position else -1
                }
                self._extract_method_calls(method, method_key, class_name)
                self._extract_method_variables(method, method_key, class_name)
                self._extract_method_logs(method, method_key)

    def _get_method_signature(self, method):
        """获取方法签名（参数类型列表）"""
        return ', '.join([param.type.name for param in method.parameters])

    def _extract_method_calls(self, method, caller_method_key, caller_class_name):
        """提取方法内部的所有调用"""
        for _, node in method.filter(MethodInvocation):
            if node.qualifier:
                # 处理静态调用或其他类的实例调用
                callee_class_name = self._resolve_class_name(node.qualifier, caller_class_name)
                callee_method_name = node.member
                callee_method_key = f"{callee_class_name}#{callee_method_name}()"
                self.method_calls[caller_method_key].append({
                    'callee': callee_method_key,
                    'line': node.position.line if node.position else -1
                })
            else:
                # 处理当前类的方法调用
                callee_method_key = f"{caller_class_name}#{node.member}()"
                self.method_calls[caller_method_key].append({
                    'callee': callee_method_key,
                    'line': node.position.line if node.position else -1
                })

    def _resolve_class_name(self, qualifier, caller_class_name):
        """解析类名（处理内部类、静态导入等复杂情况）"""
        # 简化实现，实际场景中可能需要更复杂的解析逻辑
        if '.' in qualifier:
            parts = qualifier.split('.')
            if parts[-1] in self.class_map:
                return parts[-1]
            return qualifier
        else:
            return f"{caller_class_name}.{qualifier}"

    def _extract_class_variables(self, class_node, class_name, file_path):
        """根据类型提取类的变量信息"""
        for _, node in class_node.filter(FieldDeclaration):
            for declarator in node.declarators:
                variable_name = declarator.name
                variable_type = node.type.name
                variable_line = node.position.line if node.position else -1
                self.class_variables[class_name][variable_name] = {
                    'type': variable_type,
                    'line': variable_line
                }

    def _extract_method_variables(self, method, method_key, class_name):
        """提取方法内部的所有变量声明，包括类成员变量"""
        # 先添加类的成员变量
        self.method_variables[method_key].update(self.class_variables[class_name])
        # 再添加方法内的局部变量
        for _, node in method.filter(VariableDeclaration):
            for declarator in node.declarators:
                variable_name = declarator.name
                variable_type = node.type.name
                variable_line = node.position.line if node.position else -1
                self.method_variables[method_key][variable_name] = {
                    'type': variable_type,
                    'line': variable_line
                }
        # 添加方法参数
        for param in method.parameters:
            param_name = param.name
            param_type = param.type.name
            param_line = param.position.line if param.position else -1
            self.method_variables[method_key][param_name] = {
                'type': param_type,
                'line': param_line
            }

    def _extract_method_logs(self, method, method_key):
        """提取方法内的日志语句"""
        log_methods = ['debug', 'info', 'warn', 'error']
        for _, node in method.filter(MethodInvocation):
            if node.qualifier and any(node.member == log_method for log_method in log_methods):
                if node.arguments[0].value:
                    log_statement = f"{node.qualifier}.{node.member}({str(node.arguments[0].value)})"
                else:
                    log_statement = ""
                log_line = node.position.line if node.position else -1
                self.method_logs[method_key].append({
                    'log': log_statement,
                    'line': log_line
                })

    def build_call_tree_by_class(self):
        """构建按类划分的调用树"""
        call_tree_by_class = {}
        for class_name, class_node in self.class_map.items():
            methods = []
            for method in class_node.methods:
                method_key = f"{class_name}#{method.name}({self._get_method_signature(method)})"
                method_info = {
                    method_key: {
                        "location": self.method_locations.get(method_key, {}),
                        "calls": self.method_calls.get(method_key, []),
                        "variables": self.method_variables.get(method_key, {}),
                        "logs": self.method_logs.get(method_key, [])
                    }
                }
                methods.append(method_info)
            call_tree_by_class[class_name] = {
                "method": methods,
                "parent": self.inheritance_relations.get(class_name, ""),
                "interface": self.interface_relations.get(class_name, [])
            }
        return call_tree_by_class

    def save_to_json(self, output_file):
        """将调用关系保存到JSON文件"""
        call_tree_by_class = self.build_call_tree_by_class()
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(call_tree_by_class, f, indent=2)
        print(f"Call tree saved to {output_file}")

    # def reconstruct_execution_path(self, stack_trace, output_file=None):
    #     """根据stack trace重建执行路径"""
    #     path = []
    #     for frame in stack_trace:
    #         method_key = self._find_method_key(frame)
    #         if method_key:
    #             path.append({
    #                 'method': method_key,
    #                 'location': self.method_locations.get(method_key, {})
    #             })
    #     if output_file:
    #         with open(output_file, 'w', encoding='utf-8') as f:
    #             json.dump(path, f, indent=2)
    #         print(f"Execution path saved to {output_file}")
    #     return path
    #
    # def _find_method_key(self, frame):
    #     """根据stack frame查找方法键"""
    #     # 简化实现，实际场景中可能需要更复杂的匹配逻辑
    #     class_name = frame.get('class')
    #     method_name = frame.get('method')
    #     if not class_name or not method_name:
    #         return None
    #     for key in self.method_locations:
    #         if key.startswith(f"{class_name}#{method_name}"):
    #             return key
    #     return None


if __name__ == "__main__":
    # 使用示例
    source_dir = r"hadoop-3.2.0-src/hadoop-3.2.0-src"
    output_file = "hadoop_call_tree_logs.json"
    # stack_trace_file = "sample_stack_trace.json"
    # path_output_file = "reconstructed_path.json"

    parser = HadoopASTParser(source_dir)
    parser.parse_source_files()
    parser.save_to_json(output_file)

    # 示例：从JSON文件读取stack trace并重建执行路径
    # try:
    #     with open(stack_trace_file, 'r', encoding='utf-8') as f:
    #         sample_stack_trace = json.load(f)
    #     parser.reconstruct_execution_path(sample_stack_trace, path_output_file)
    # except FileNotFoundError:
    #     print("Stack trace file not found. Skipping path reconstruction.")
