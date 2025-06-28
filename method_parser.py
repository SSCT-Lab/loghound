import os
import re
import json
import argparse
from collections import defaultdict
from pathlib import Path
from javalang import parse, tree, tokenizer
from javalang.tree import MethodInvocation, Member, Literal, BinaryOperation


class HadoopCodeAnalyzer:
    def __init__(self, source_dir):
        self.source_dir = source_dir
        self.class_locations = {}  # 存储类的位置信息
        self.class_imports = defaultdict(list)  # 存储每个文件的import语句
        self.class_hierarchy = {}  # 存储类的继承关系
        self.results = defaultdict(lambda: {
            "location": {"file": "", "line": 0},
            "methods": [],
            "interfaces": [],
            "parent": ""
        })
        # 定义日志方法列表，用于过滤
        self.LOG_METHODS = {'info', 'debug', 'warn', 'error', 'trace', 'fatal'}
        # 存储变量类型映射 (scope -> variable name -> type)
        self.variable_types = defaultdict(lambda: defaultdict(str))
        # 存储字段类型映射 (class name -> field name -> type)
        self.field_types = defaultdict(lambda: defaultdict(str))

    def analyze(self):
        """分析指定目录下的所有Java源文件"""
        # 第一遍扫描：收集类的位置、导入、继承和字段信息
        for root, _, files in os.walk(self.source_dir):
            for file in files:
                if file.endswith('.java') and re.match(".*Test.*", file) is None:  # 跳过测试文件
                    file_path = os.path.join(root, file)
                    self._process_file(file_path)

        # 第二遍扫描：分析方法和调用，构建变量类型映射
        for root, _, files in os.walk(self.source_dir):
            for file in files:
                if file.endswith('.java') and re.match(".*Test.*", file) is None:  # 跳过测试文件
                    file_path = os.path.join(root, file)
                    self._analyze_methods(file_path)

        return self.results

    def _process_file(self, file_path):
        """处理单个Java文件，提取类信息、导入、继承和字段信息"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tokens = list(tokenizer.tokenize(content))
            ast = parse.parse(content)

            # 提取包名
            package_name = ""
            if ast.package:
                package_name = ast.package.name

            # 提取import语句
            imports = []
            for import_decl in ast.imports:
                imports.append(import_decl.path)

            # 处理每个类
            for _, class_decl in ast.filter(tree.ClassDeclaration):
                class_name = class_decl.name
                qualified_name = f"{package_name}.{class_name}" if package_name else class_name

                # 查找类声明的行号
                line = self._find_node_line(tokens, class_decl)

                self.class_locations[qualified_name] = {
                    "file": file_path,
                    "line": line
                }
                self.class_imports[qualified_name] = imports

                # 记录继承和接口实现
                parent = class_decl.extends.name if class_decl.extends else ""
                interfaces = [i.name for i in class_decl.implements] if class_decl.implements else []

                self.class_hierarchy[qualified_name] = {
                    "parent": parent,
                    "interfaces": interfaces
                }

                # 初始化结果
                self.results[qualified_name]["location"] = {
                    "file": file_path,
                    "line": line
                }
                self.results[qualified_name]["interfaces"] = interfaces
                self.results[qualified_name]["parent"] = parent

                # 提取字段类型
                for _, field_decl in class_decl.filter(tree.FieldDeclaration):
                    field_type = self._resolve_type(field_decl.type, qualified_name, imports)
                    for declarator in field_decl.declarators:
                        field_name = declarator.name
                        self.field_types[qualified_name][field_name] = field_type

        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    def _analyze_methods(self, file_path):
        """分析文件中的方法，提取方法调用和日志信息，构建变量类型映射"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tokens = list(tokenizer.tokenize(content))
            ast = parse.parse(content)

            # 提取包名
            package_name = ""
            if ast.package:
                package_name = ast.package.name

            # 处理每个类中的方法
            for _, class_decl in ast.filter(tree.ClassDeclaration):
                class_name = class_decl.name
                qualified_class_name = f"{package_name}.{class_name}" if package_name else class_name

                # 处理类中的每个方法
                for _, method_decl in class_decl.filter(tree.MethodDeclaration):
                    method_name = method_decl.name
                    method_signature = f"{qualified_class_name}#{method_name}()"

                    # 查找方法声明的行号
                    method_line = self._find_node_line(tokens, method_decl)

                    # 创建方法作用域
                    method_scope = f"{qualified_class_name}#{method_name}"
                    method_variable_types = defaultdict(str)

                    # 处理方法参数
                    if method_decl.parameters:
                        for param in method_decl.parameters:
                            param_type = self._resolve_type(param.type, qualified_class_name,
                                                            self.class_imports[qualified_class_name])
                            method_variable_types[param.name] = param_type

                    # 分析方法体，构建变量类型映射
                    if method_decl.body:
                        self._build_variable_types(method_decl.body, method_scope, qualified_class_name,
                                                   method_variable_types)

                    # 保存方法作用域的变量类型映射
                    self.variable_types[method_scope] = method_variable_types

                    # 分析方法体，提取调用和日志
                    calls = []
                    logs = []

                    if method_decl.body:
                        # 提取方法调用
                        for _, method_invocation in method_decl.filter(tree.MethodInvocation):
                            if method_invocation.qualifier:
                                # 排除日志方法
                                if self._is_log_method(method_invocation):
                                    continue

                                line = self._find_node_line(tokens, method_invocation)

                                # 解析方法调用，尝试找到完整的类名
                                callee = self._resolve_method_invocation(
                                    method_invocation,
                                    qualified_class_name,
                                    method_scope,
                                    self.class_imports[qualified_class_name]
                                )

                                if callee:
                                    calls.append({
                                        "callee": callee,
                                        "line": line
                                    })

                        # 提取日志信息
                        logs = self._extract_method_logs(method_decl, method_signature)

                    # 添加方法信息到结果
                    self.results[qualified_class_name]["methods"].append({
                        method_signature: {
                            "location": {
                                "file": file_path,
                                "line": method_line
                            },
                            "calls": calls,
                            "logs": logs
                        }
                    })

        except Exception as e:
            print(f"Error analyzing methods in {file_path}: {e}")

    def _build_variable_types(self, node, scope, class_name, variable_types):
        """递归构建变量类型映射"""
        if isinstance(node, tree.LocalVariableDeclaration):
            var_type = self._resolve_type(node.type, class_name, self.class_imports[class_name])
            for declarator in node.declarators:
                var_name = declarator.name
                variable_types[var_name] = var_type

                # 处理初始化表达式
                if declarator.initializer:
                    self._process_initializer(declarator.initializer, var_name, var_type, scope, class_name,
                                              variable_types)

        elif isinstance(node, tree.Assignment):
            if isinstance(node.expressionl, tree.MemberReference):
                # 处理字段赋值
                member = node.expressionl
                if member.qualifier == 'this':
                    field_name = member.member
                    if field_name in self.field_types[class_name]:
                        field_type = self.field_types[class_name][field_name]
                        self._process_initializer(node.expressionr, field_name, field_type, scope, class_name,
                                                  variable_types)
            elif isinstance(node.expressionl, tree.Name):
                # 处理变量赋值
                var_name = node.expressionl.name
                if var_name in variable_types:
                    var_type = variable_types[var_name]
                    self._process_initializer(node.expressionr, var_name, var_type, scope, class_name, variable_types)

        # 递归处理子节点
        if hasattr(node, 'children'):
            for child in node.children:
                if isinstance(child, list):
                    for item in child:
                        if isinstance(item, tree.Node):
                            self._build_variable_types(item, scope, class_name, variable_types)
                elif isinstance(child, tree.Node):
                    self._build_variable_types(child, scope, class_name, variable_types)

    def _process_initializer(self, initializer, var_name, var_type, scope, class_name, variable_types):
        """处理变量初始化表达式，更新类型映射"""
        if isinstance(initializer, tree.MethodInvocation):
            # 处理方法调用返回值
            if initializer.qualifier:
                # 尝试解析调用对象的类型
                obj_type = self._resolve_qualifier_type(initializer.qualifier, scope, class_name)
                if obj_type:
                    # 尝试查找方法返回类型（简化处理）
                    method_return_type = self._find_method_return_type(obj_type, initializer.member)
                    if method_return_type:
                        # 记录变量的实际类型
                        variable_types[var_name] = method_return_type
        elif isinstance(initializer, tree.Creator):
            # 处理对象创建
            created_type = self._resolve_type(initializer.type, class_name, self.class_imports[class_name])
            variable_types[var_name] = created_type

    def _find_method_return_type(self, class_name, method_name):
        """查找方法的返回类型（简化处理）"""
        # 在实际应用中，这需要更复杂的分析
        # 这里仅作为示例，返回一个默认值
        return class_name  # 简化处理，实际应该查找方法签名

    def _resolve_qualifier_type(self, qualifier, scope, class_name):
        """解析限定符的类型"""
        parts = qualifier.split('.')

        # 处理简单变量
        if len(parts) == 1:
            var_name = parts[0]
            # 先检查方法变量
            if var_name in self.variable_types[scope]:
                return self.variable_types[scope][var_name]
            # 再检查字段
            if var_name in self.field_types[class_name]:
                return self.field_types[class_name][var_name]

        # 处理复合情况，如 "obj.field"
        if len(parts) >= 2:
            base = parts[0]
            base_type = ""

            # 查找基础对象类型
            if base in self.variable_types[scope]:
                base_type = self.variable_types[scope][base]
            elif base in self.field_types[class_name]:
                base_type = self.field_types[class_name][base]

            # 逐级查找字段类型
            current_type = base_type
            for part in parts[1:]:
                if current_type and part in self.field_types[current_type]:
                    current_type = self.field_types[current_type][part]
                else:
                    break

            return current_type

        return None

    def _is_log_method(self, method_invocation):
        """判断是否为日志方法"""
        # 检查方法名是否为日志方法
        if method_invocation.member in self.LOG_METHODS:
            # 检查调用对象是否为日志对象
            qualifier = method_invocation.qualifier
            if qualifier.lower().startswith('log'):
                return True
        return False

    def _find_node_line(self, tokens, node):
        """查找AST节点在源代码中的行号"""
        if not tokens or not node:
            return 0

        # 尝试找到与节点位置匹配的token
        for token in tokens:
            if token.position and token.position.line <= node.position.line:
                line = token.position.line
            else:
                break

        return line

    def _resolve_method_invocation(self, method_invocation, current_class, scope, imports):
        """解析方法调用，尝试找到完整的类名"""
        qualifier = method_invocation.qualifier
        method_name = method_invocation.member

        # 处理特殊情况：this和super
        if qualifier in ['this', 'super']:
            return f"{current_class}#{method_name}()"

        # 尝试解析限定符的实际类型
        resolved_type = self._resolve_qualifier_type(qualifier, scope, current_class)
        if resolved_type:
            return f"{resolved_type}#{method_name}()"

        # 处理静态导入
        for imp in imports:
            if imp.endswith(f".{qualifier}"):
                return f"{imp}#{method_name}()"

        # 尝试通过类层次结构解析
        if qualifier in self.class_locations:
            return f"{qualifier}#{method_name}()"

        # 尝试通过包导入解析
        for imp in imports:
            if imp.endswith(f".{qualifier}"):
                return f"{imp}#{method_name}()"
            elif imp.endswith(".*"):
                base_package = imp.rsplit('.', 1)[0]
                possible_class = f"{base_package}.{qualifier}"
                if possible_class in self.class_locations:
                    return f"{possible_class}#{method_name}()"

        # 尝试作为内部类解析
        if '$' in current_class:
            outer_class = current_class.split('$')[0]
            possible_inner_class = f"{outer_class}${qualifier}"
            if possible_inner_class in self.class_locations:
                return f"{possible_inner_class}#{method_name}()"

        # 无法解析，返回最可能的形式
        return f"{current_class}.{qualifier}#{method_name}()"

    def _resolve_type(self, type_node, current_class, imports):
        """解析类型节点为完整类名"""
        if isinstance(type_node, tree.ReferenceType):
            name_parts = type_node.name.split('.')
            if len(name_parts) == 1:
                # 短名称，需要解析
                simple_name = name_parts[0]

                # 检查是否在导入中
                for imp in imports:
                    if imp.endswith(f".{simple_name}"):
                        return imp

                # 检查是否为内部类
                if '$' in current_class:
                    outer_class = current_class.split('$')[0]
                    possible_inner_class = f"{outer_class}${simple_name}"
                    if possible_inner_class in self.class_locations:
                        return possible_inner_class

                # 检查是否在当前包中
                current_package = current_class.rsplit('.', 1)[0]
                possible_class = f"{current_package}.{simple_name}"
                if possible_class in self.class_locations:
                    return possible_class

                # 检查是否为顶级类
                if simple_name in self.class_locations:
                    return simple_name

                # 无法解析，返回简单名称
                return simple_name
            else:
                # 长名称，直接返回
                return type_node.name
        elif hasattr(type_node, 'name'):
            return type_node.name

        return str(type_node)

    def _extract_method_logs(self, method, method_key):
        """提取方法内的日志语句"""
        logs = []
        log_methods = ['debug', 'info', 'warn', 'error']
        for _, node in method.filter(tree.MethodInvocation):
            if node.qualifier and any(node.member == log_method for log_method in log_methods):
                if node.arguments:
                    log_argument = node.arguments[0]
                    log_parts = self._parse_log_argument(log_argument)
                    log_line = node.position.line if node.position else -1
                    logs.append({
                        'template': log_parts['template'].replace('"', ''),
                        'variables': log_parts['variables'],
                        'level': node.member,
                        'line': log_line
                    })
        return logs

    def _parse_log_argument(self, argument):
        """解析日志参数，提取文本模板和变量引用"""
        if isinstance(argument, Literal):
            # 简单文本日志
            return {
                'template': argument.value,
                'variables': []
            }
        elif isinstance(argument, BinaryOperation) and argument.operator == '+':
            # 拼接表达式日志
            left = self._parse_log_argument(argument.operandl)
            right = self._parse_log_argument(argument.operandr)

            template = left['template'] + "{}" + right['template']
            variables = left['variables'] + right['variables']

            # 处理变量引用
            if isinstance(argument.operandl, Member):
                variables.append(argument.operandl.member)
            if isinstance(argument.operandr, Member):
                variables.append(argument.operandr.member)

            return {
                'template': template,
                'variables': variables
            }
        else:
            # 其他情况（如方法调用）
            return {
                'template': "",
                'variables': []
            }

    def _find_line_number(self, tokens, char_index, start_line):
        """根据字符索引找到行号"""
        current_line = start_line
        current_pos = 0

        for token in tokens:
            if token.position:
                current_line = token.position.line
                current_pos += len(token.value)
                if current_pos > char_index:
                    return current_line

        return current_line

def main():
    # parser = argparse.ArgumentParser(description='Hadoop Source Code Analyzer')
    # parser.add_argument('--source', required=True, help='Path to Hadoop source code directory')
    # parser.add_argument('--output', required=True, help='Output JSON file path')
    # args = parser.parse_args()
    source_dir = r"hadoop-2.0.0-alpha-src"
    output_file = "hadoop_2_0_tree.json"
    analyzer = HadoopCodeAnalyzer(source_dir)
    results = analyzer.analyze()

    # 保存结果到JSON文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # print(f"Analysis completed. Results saved to {args.output}")


if __name__ == "__main__":
    main()