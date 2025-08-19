import javalang
import os
import json
import re
from typing import Dict, List, Optional, Any, Set, Tuple
from collections import defaultdict


# 检查javalang版本
def get_javalang_version():
    try:
        return tuple(map(int, javalang.__version__.split('.')))
    except:
        return (0, 13, 0)


JAVALANG_VERSION = get_javalang_version()


# 完全自定义Name类，解决javalang.tree.Name兼容性问题
class Name:
    def __init__(self, value):
        if isinstance(value, str):
            self.value = value
            self.parts = value.split('.')  # 按.拆分名称部分
        elif isinstance(value, list):
            self.parts = value
            self.value = ".".join(value)
        else:
            self.value = str(value)
            self.parts = [str(value)]


# 替换javalang的Name类
import javalang.tree

javalang.tree.Name = Name

# Java核心包和类映射
JAVA_CORE_PACKAGES = {
    'java.lang', 'java.util', 'java.io', 'java.net', 'java.nio',
    'java.sql', 'java.math', 'java.time', 'java.text', 'java.rmi',
    'java.security', 'java.awt', 'javax', 'sun', 'com.sun', 'org.omg'
}

JAVA_CORE_CLASSES = {
    'System': 'java.lang.System',
    'Thread': 'java.lang.Thread',
    'Object': 'java.lang.Object',
    'String': 'java.lang.String',
    'Integer': 'java.lang.Integer',
    'List': 'java.util.List',
    'Map': 'java.util.Map',
    'Set': 'java.util.Set',
    'ArrayList': 'java.util.ArrayList',
    'HashMap': 'java.util.HashMap',
    'PrintStream': 'java.io.PrintStream'
}


class JavaTypeResolver:
    """类型解析器"""

    def __init__(self, project_classes):
        self.type_cache = {}
        self.wildcard_imports_cache = defaultdict(set)
        self.project_classes = project_classes

    def resolve_type(self, simple_name: str, imports: List,
                     current_package: str, current_class: str,
                     inner_classes: List[str], class_declarations: List[str]) -> str:
        cache_key = (simple_name, tuple(imports), current_package, current_class,
                     tuple(inner_classes), tuple(class_declarations))
        if cache_key in self.type_cache:
            return self.type_cache[cache_key]

        # 优先识别Java核心类（保持不变）
        if simple_name in JAVA_CORE_CLASSES:
            self.type_cache[cache_key] = JAVA_CORE_CLASSES[simple_name]
            return JAVA_CORE_CLASSES[simple_name]

        # 内部类（确保外部类是全路径）
        if simple_name in inner_classes:
            # current_class是全路径（如org.apache.cassandra.gms.Gossiper）
            result = f"{current_class}${simple_name}"
            self.type_cache[cache_key] = result
            return result

        # 当前文件顶层类（拼接当前包名，确保全路径）
        if simple_name in class_declarations:
            result = f"{current_package}.{simple_name}" if current_package else simple_name
            self.type_cache[cache_key] = result
            return result

        # 单类型导入（直接使用导入的全路径）
        for imp in imports:
            if not imp.static and not imp.wildcard:
                imp_class_name = imp.path.split('.')[-1]
                if imp_class_name == simple_name:
                    self.type_cache[cache_key] = imp.path  # imp.path是全路径（如org.apache.cassandra.gms.EndPointState）
                    return imp.path

        # 通配符导入（从项目类缓存中匹配全路径）
        for imp in imports:
            if not imp.static and imp.wildcard:
                package = imp.path[:-2]  # 去除通配符"*"
                # 检查项目中该包下是否存在目标类
                if package in self.project_classes and simple_name in self.project_classes[package]:
                    result = f"{package}.{simple_name}"
                    self.type_cache[cache_key] = result
                    return result

        # 当前包下的类（拼接当前包名）
        if current_package:
            # 检查当前包是否在项目类中
            if current_package in self.project_classes and simple_name in self.project_classes[current_package]:
                result = f"{current_package}.{simple_name}"
                self.type_cache[cache_key] = result
                return result

        # 无法解析时仍返回全路径格式（避免简单类名）
        result = f"unknown.package.{simple_name}" if not current_package else f"{current_package}.{simple_name}"
        self.type_cache[cache_key] = result
        return result

    def add_wildcard_types(self, package: str, classes: Set[str]):
        self.wildcard_imports_cache[package].update(classes)


class JavaCodeAnalyzer:
    def __init__(self):
        self.project_classes = defaultdict(set)
        self.type_resolver = JavaTypeResolver(self.project_classes)
        self.logger_classes = {
            'org.slf4j.Logger', 'org.apache.log4j.Logger',
            'java.util.logging.Logger', 'org.apache.commons.logging.Log',
            'org.slf4j.LoggerFactory', 'org.apache.log4j.LogManager'
        }
        self.log_level_methods = {'info', 'debug', 'warn', 'error', 'trace', 'fatal'}
        self.file_cache = {}
        self.inner_classes = defaultdict(list)
        # 新增：存储变量的格式化信息 (scope -> var_name -> (template, variables))
        self.variable_formats = defaultdict(lambda: defaultdict(lambda: (None, [])))
        # 新增：存储变量的字符串初始值 (scope -> var_name -> string_value)
        self.variable_string_values = defaultdict(lambda: defaultdict(str))

    def analyze_project(self, project_path: str) -> List[Dict[str, Any]]:
        self._collect_project_classes(project_path)
        result = []
        for root, _, files in os.walk(project_path):
            for file in files:
                if file.endswith('.java') and "Test" not in file:
                    if file == "Gossiper.java":
                        print("start！")
                    file_path = os.path.join(root, file)
                    try:
                        analysis = self.analyze_file(file_path)
                        if analysis:
                            result.extend(analysis)
                    except Exception as e:
                        print(f"解析文件 {file_path} 出错: {str(e)}")
        return result

    def _collect_project_classes(self, project_path: str):
        for root, _, files in os.walk(project_path):
            for file in files:
                if file.endswith('.java'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            code = f.read()
                        tree = javalang.parse.parse(code)

                        package_name = tree.package.name if tree.package else ""
                        for type_decl in tree.types:
                            if isinstance(type_decl, javalang.tree.ClassDeclaration):
                                class_name = type_decl.name
                                full_name = f"{package_name}.{class_name}" if package_name else class_name
                                self.project_classes[package_name].add(class_name)
                                self._collect_inner_classes(type_decl, full_name)
                    except Exception as e:
                        print(f"收集类信息失败 {file_path}: {str(e)}")

    def _collect_inner_classes(self, type_decl, outer_class_full_name: str):
        if not hasattr(type_decl, 'body'):
            return
        for decl in type_decl.body:
            if isinstance(decl, javalang.tree.ClassDeclaration):
                inner_name = decl.name
                self.inner_classes[outer_class_full_name].append(inner_name)
                self._collect_inner_classes(decl, f"{outer_class_full_name}${inner_name}")

    def analyze_file(self, file_path: str) -> List[Dict[str, Any]]:
        if file_path in self.file_cache:
            return self.file_cache[file_path]

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            tree = javalang.parse.parse(code)
        except Exception as e:
            print(f"解析代码失败 {file_path}: {str(e)}")
            return []

        current_package = tree.package.name if tree.package else ""
        class_declarations = [t.name for t in tree.types if isinstance(t, javalang.tree.ClassDeclaration)]

        result = []
        for type_decl in tree.types:
            if isinstance(type_decl, javalang.tree.ClassDeclaration):
                class_info = self._analyze_class(
                    type_decl, file_path, tree.imports, current_package, class_declarations
                )
                result.append(class_info)

        self.file_cache[file_path] = result
        return result

    def _analyze_class(self, class_decl: javalang.tree.ClassDeclaration,
                       file_path: str, imports: List,
                       current_package: str, class_declarations: List[str]) -> Dict[str, Any]:
        class_name = class_decl.name
        full_class_name = f"{current_package}.{class_name}" if current_package else class_name
        current_inner_classes = self.inner_classes.get(full_class_name, [])

        class_info = {
            "class_name": full_class_name,
            "location": file_path,
            "methods": [],
            "inner_classes": current_inner_classes
        }

        field_types = self._collect_field_types(class_decl, imports, current_package, full_class_name,
                                                current_inner_classes, class_declarations)

        # 收集字段的字符串初始值
        for field in class_decl.fields:
            field_type_name = self._get_type_name(field.type.name)
            field_type = self.type_resolver.resolve_type(
                field_type_name, imports, current_package, full_class_name,
                current_inner_classes, class_declarations
            )
            for declarator in field.declarators:
                if field_type == "java.lang.String" and hasattr(declarator, 'initializer') and declarator.initializer:
                    str_value = self._parse_string_literal(declarator.initializer)
                    if str_value:
                        self.variable_string_values[full_class_name][declarator.name] = str_value

        for method in class_decl.methods:
            method_full_name = f"{full_class_name}#{method.name}"
            method_info = {method_full_name: {"calls": [], "logs": []}}

            # 安全处理方法体（关键修复：防止method.body为None）
            if method.body:
                symbol_table = {k: {"type": v["type"], "string_template": v.get("string_template")}
                                for k, v in field_types.items()}
                self._add_method_parameters_to_symbol_table(method, symbol_table, imports, current_package,
                                                            full_class_name, current_inner_classes, class_declarations)

                # 安全获取方法体语句（处理空块和非BlockStatement类型）
                if isinstance(method.body, javalang.tree.BlockStatement):
                    method_statements = self._safe_iterable(method.body.statements)
                else:
                    method_statements = self._safe_iterable(method.body)

                calls, logs = self._analyze_statements(
                    method_statements,
                    imports, current_package, full_class_name,
                    current_inner_classes, class_declarations, symbol_table, method_full_name
                )
                method_info[method_full_name]["calls"] = calls
                method_info[method_full_name]["logs"] = logs

            class_info["methods"].append(method_info)

        self._process_initializers(class_decl, class_info, field_types, imports,
                                   current_package, full_class_name, current_inner_classes, class_declarations)

        return class_info

    def _build_variable_info(self, node, scope, class_name, symbol_table, imports, current_package, inner_classes,
                             class_declarations):
        """递归构建变量信息，包括字符串值和格式化信息"""
        if isinstance(node, list):
            for item in node:
                self._build_variable_info(item, scope, class_name, symbol_table, imports, current_package,
                                          inner_classes, class_declarations)
            return

        # 处理局部变量声明
        if isinstance(node, javalang.tree.LocalVariableDeclaration):
            var_type_name = self._get_type_name(node.type.name)
            var_type = self.type_resolver.resolve_type(
                var_type_name, imports, current_package, class_name,
                inner_classes, class_declarations
            )
            for declarator in node.declarators:
                var_name = declarator.name
                # 处理字符串初始化值
                if var_type == "java.lang.String" and hasattr(declarator, 'initializer') and declarator.initializer:
                    str_value = self._parse_string_literal(declarator.initializer)
                    if str_value:
                        self.variable_string_values[scope][var_name] = str_value
                    # 处理String.format初始化
                    if isinstance(declarator.initializer, javalang.tree.MethodInvocation):
                        qualifier = declarator.initializer.qualifier
                        if qualifier and self._get_caller_name(
                                qualifier) == "String" and declarator.initializer.member == "format":
                            if hasattr(declarator.initializer, 'arguments') and len(
                                    declarator.initializer.arguments) >= 1:
                                format_template = self._parse_format_template(declarator.initializer.arguments[0],
                                                                              scope, class_name)
                                format_vars = self._parse_format_variables(declarator.initializer.arguments[1:], scope,
                                                                           class_name, symbol_table)
                                self.variable_formats[scope][var_name] = (format_template, format_vars)

        # 处理赋值语句
        elif isinstance(node, javalang.tree.Assignment):
            left_expr = getattr(node, 'operandl', getattr(node, 'left', None))
            right_expr = getattr(node, 'operandr', getattr(node, 'right', None))

            if isinstance(left_expr, javalang.tree.MemberReference):
                # 处理字段赋值
                if left_expr.qualifier and self._get_caller_name(left_expr.qualifier) == "this":
                    field_name = left_expr.member
                    if field_name in symbol_table and symbol_table[field_name]["type"] == "java.lang.String":
                        str_value = self._parse_string_literal(right_expr)
                        if str_value:
                            self.variable_string_values[class_name][field_name] = str_value
            elif hasattr(left_expr, 'name'):
                # 处理变量赋值
                var_name = left_expr.name
                if var_name in symbol_table and symbol_table[var_name]["type"] == "java.lang.String":
                    str_value = self._parse_string_literal(right_expr)
                    if str_value:
                        self.variable_string_values[scope][var_name] = str_value

        # 递归处理子节点
        for child in self._get_all_children(node):
            self._build_variable_info(child, scope, class_name, symbol_table, imports, current_package, inner_classes,
                                      class_declarations)

    def _get_all_children(self, node):
        """获取节点的所有子节点（包括嵌套在列表中的子节点）"""
        children = []
        if hasattr(node, 'children'):
            for child in node.children:
                if isinstance(child, list):
                    # 遍历列表中的每个项目
                    for list_item in child:
                        if isinstance(list_item, javalang.tree.Node):
                            children.append(list_item)
                # 检查当前child是否为Node类型
                elif isinstance(child, javalang.tree.Node):
                    children.append(child)
        # 特殊处理ForStatement：避免访问不存在的init属性，直接解析其结构
        elif isinstance(node, javalang.tree.ForStatement):
            # for循环的三个部分：初始化、条件、更新
            if hasattr(node, 'control'):
                control = node.control
                if isinstance(control, javalang.tree.ForControl):
                    # 添加初始化部分（如变量声明）
                    if hasattr(control, 'init'):
                        children.extend(control.init)
                    # 添加条件部分
                    if hasattr(control, 'condition') and control.condition:
                        children.append(control.condition)
                    # 添加更新部分
                    if hasattr(control, 'update'):
                        children.extend(control.update)
            # 添加循环体
            if hasattr(node, 'body'):
                children.append(node.body)
        return children

    def _parse_string_literal(self, node) -> Optional[str]:
        """解析节点为字符串字面量值"""
        if isinstance(node, javalang.tree.Literal) and isinstance(node.value, str) and node.value.startswith('"'):
            return node.value.strip('"')
        return None

    def _parse_format_template(self, template_node, scope, class_name) -> str:
        """解析String.format的模板字符串"""
        if isinstance(template_node, javalang.tree.Literal):
            return self._parse_string_literal(template_node) or ""
        # 处理变量引用的模板
        if hasattr(template_node, 'name'):
            var_name = template_node.name
            if var_name in self.variable_string_values[scope]:
                return self.variable_string_values[scope][var_name]
            if var_name in self.variable_string_values[class_name]:
                return self.variable_string_values[class_name][var_name]
        return ""

    def _parse_format_variables(self, var_nodes, scope, class_name, symbol_table) -> List[str]:
        """解析String.format的参数变量"""
        vars_list = []
        for node in var_nodes:
            vars_list.append(self._parse_var_expression(node, scope, class_name, symbol_table))
        return vars_list

    def _process_initializers(self, class_decl, class_info, field_types, imports,
                              current_package, full_class_name, inner_classes, class_declarations):
        initializers = []
        if hasattr(class_decl, 'initializers'):
            initializers = class_decl.initializers
        elif hasattr(class_decl, 'block'):
            initializers = [class_decl.block]
        elif hasattr(class_decl, 'body'):
            for decl in class_decl.body:
                if isinstance(decl, javalang.tree.BlockStatement):
                    initializers.append(decl)

        for idx, initializer in enumerate(initializers):
            if hasattr(initializer, 'body') and initializer.body:
                init_body = initializer.body
                init_statements = init_body.statements if hasattr(init_body, 'statements') else []
            else:
                init_statements = []

            init_full_name = f"{full_class_name}#initializer_{idx}"
            init_info = {init_full_name: {"calls": [], "logs": []}}
            symbol_table = {k: {"type": v["type"], "string_template": v.get("string_template")}
                            for k, v in field_types.items()}
            calls, logs = self._analyze_statements(
                init_statements,  # 传入statements列表而非BlockStatement
                imports, current_package, full_class_name,
                inner_classes, class_declarations, symbol_table, init_full_name
            )
            init_info[init_full_name]["calls"] = calls
            init_info[init_full_name]["logs"] = logs
            class_info["methods"].append(init_info)

    def _collect_field_types(self, class_decl, imports, current_package, full_class_name, inner_classes,
                             class_declarations):
        field_types = {}
        for field in class_decl.fields:
            field_type_name = self._get_type_name(field.type.name)
            field_type = self.type_resolver.resolve_type(
                field_type_name, imports, current_package, full_class_name,
                inner_classes, class_declarations
            )

            for declarator in field.declarators:
                if field_type == "java.lang.String" and hasattr(declarator, 'initializer') and declarator.initializer:
                    field_types[declarator.name] = {
                        "type": field_type,
                        "string_template": self._parse_string_expression(declarator.initializer)
                    }
                else:
                    field_types[declarator.name] = {"type": field_type, "string_template": None}
        return field_types

    def _add_method_parameters_to_symbol_table(self, method, symbol_table, imports, current_package, full_class_name,
                                               inner_classes, class_declarations):
        for param in method.parameters:
            param_type_name = self._get_type_name(param.type.name)
            param_type = self.type_resolver.resolve_type(
                param_type_name, imports, current_package, full_class_name,
                inner_classes, class_declarations
            )
            symbol_table[param.name] = {"type": param_type, "string_template": None}

    def _safe_iterable(self, obj):
        """确保对象可迭代，将None转换为空列表，非迭代对象包装为列表"""
        if obj is None:
            return []
        if isinstance(obj, (list, tuple, javalang.ast.NodeList)):
            return obj
        return [obj]

    def _analyze_statements(self, statements: List,
                            imports: List, current_package: str, current_class: str,
                            inner_classes: List[str], class_declarations: List[str],
                            symbol_table: Dict[str, Any], scope: str) -> Tuple[
        List[Dict[str, Any]], List[Dict[str, Any]]]:
        calls = []
        logs = []

        # 安全处理顶层语句列表（防止None）
        for item in self._safe_iterable(statements):
            # 处理嵌套列表（数组套数组）
            if isinstance(item, (list, tuple, javalang.ast.NodeList)):
                nested_calls, nested_logs = self._analyze_statements(
                    item, imports, current_package, current_class,
                    inner_classes, class_declarations, symbol_table.copy(), scope
                )
                calls.extend(nested_calls)
                logs.extend(nested_logs)
                continue

            stmt = item
            if stmt is None:
                continue  # 跳过None元素

            # 处理变量声明
            if isinstance(stmt, javalang.tree.LocalVariableDeclaration):
                self._process_variable_declaration(
                    stmt, symbol_table, imports, current_package, current_class,
                    inner_classes, class_declarations
                )

            # 提取表达式中的方法调用
            expr = self._get_expression_from_statement(stmt)
            if isinstance(expr, javalang.tree.MethodInvocation):
                call_info = self._process_method_invocation(
                    expr, symbol_table, imports, current_package, current_class,
                    inner_classes, class_declarations
                )
                if call_info:
                    calls.append(call_info)

                log_info = self._check_log_statement(
                    expr, symbol_table, imports, current_package, current_class,
                    inner_classes, class_declarations, scope
                )
                if log_info:
                    logs.append(log_info)

            # 处理if/else语句
            if isinstance(stmt, javalang.tree.IfStatement):
                # 安全处理then块
                then_stmt = self._safe_iterable(stmt.then_statement)
                for then_item in then_stmt:
                    then_stmts = then_item.statements if isinstance(then_item, javalang.tree.BlockStatement) else [
                        then_item]
                    then_calls, then_logs = self._analyze_statements(
                        then_stmts, imports, current_package, current_class,
                        inner_classes, class_declarations, symbol_table.copy(), scope
                    )
                    calls.extend(then_calls)
                    logs.extend(then_logs)

                # 安全处理else块
                else_stmt = self._safe_iterable(stmt.else_statement)
                for else_item in else_stmt:
                    if isinstance(else_item, javalang.tree.IfStatement):
                        else_stmts = [else_item]
                    else:
                        else_stmts = else_item.statements if isinstance(else_item, javalang.tree.BlockStatement) else [
                            else_item]
                    else_calls, else_logs = self._analyze_statements(
                        else_stmts, imports, current_package, current_class,
                        inner_classes, class_declarations, symbol_table.copy(), scope
                    )
                    calls.extend(else_calls)
                    logs.extend(else_logs)

            # 处理for循环
            elif isinstance(stmt, javalang.tree.ForStatement):
                # 安全处理循环控制部分
                if hasattr(stmt, 'control') and stmt.control:
                    control = stmt.control
                    if isinstance(control, javalang.tree.ForControl):
                        # 处理初始化部分
                        for init in self._safe_iterable(control.init):
                            init_expr = self._get_expression_from_statement(init)
                            if isinstance(init_expr, javalang.tree.MethodInvocation):
                                init_call = self._process_method_invocation(init_expr, symbol_table, imports,
                                                                            current_package, current_class,
                                                                            inner_classes, class_declarations)
                                if init_call:
                                    calls.append(init_call)
                        # 处理条件部分
                        cond_expr = self._get_expression_from_statement(control.condition)
                        if isinstance(cond_expr, javalang.tree.MethodInvocation):
                            cond_call = self._process_method_invocation(cond_expr, symbol_table, imports,
                                                                        current_package, current_class, inner_classes,
                                                                        class_declarations)
                            if cond_call:
                                calls.append(cond_call)
                        # 处理更新部分
                        for update in self._safe_iterable(control.update):
                            update_expr = self._get_expression_from_statement(update)
                            if isinstance(update_expr, javalang.tree.MethodInvocation):
                                update_call = self._process_method_invocation(update_expr, symbol_table, imports,
                                                                              current_package, current_class,
                                                                              inner_classes, class_declarations)
                                if update_call:
                                    calls.append(update_call)

                # 安全处理循环体
                loop_body = self._safe_iterable(stmt.body)
                for body_item in loop_body:
                    loop_stmts = body_item.statements if isinstance(body_item, javalang.tree.BlockStatement) else [
                        body_item]
                    loop_calls, loop_logs = self._analyze_statements(
                        loop_stmts, imports, current_package, current_class,
                        inner_classes, class_declarations, symbol_table.copy(), scope
                    )
                    calls.extend(loop_calls)
                    logs.extend(loop_logs)

            # 处理try-catch-finally
            elif isinstance(stmt, javalang.tree.TryStatement):
                # 安全处理try块
                try_block = self._safe_iterable(stmt.block)
                for block_item in try_block:
                    try_stmts = block_item.statements if hasattr(block_item, 'statements') else []
                    try_calls, try_logs = self._analyze_statements(
                        try_stmts, imports, current_package, current_class,
                        inner_classes, class_declarations, symbol_table.copy(), scope
                    )
                    calls.extend(try_calls)
                    logs.extend(try_logs)

                # 安全处理catch块
                for catch in self._safe_iterable(stmt.catches):
                    catch_stmts = catch.block.statements if (catch.block and hasattr(catch.block, 'statements')) else []
                    catch_calls, catch_logs = self._analyze_statements(
                        catch_stmts, imports, current_package, current_class,
                        inner_classes, class_declarations, symbol_table.copy(), scope
                    )
                    calls.extend(catch_calls)
                    logs.extend(catch_logs)

                # 安全处理finally块
                finally_block = self._safe_iterable(stmt.finally_block)
                for fb_item in finally_block:
                    finally_stmts = fb_item.statements if hasattr(fb_item, 'statements') else []
                    finally_calls, finally_logs = self._analyze_statements(
                        finally_stmts, imports, current_package, current_class,
                        inner_classes, class_declarations, symbol_table.copy(), scope
                    )
                    calls.extend(finally_calls)
                    logs.extend(finally_logs)

            # 处理普通块语句
            elif self._is_block_statement(stmt):
                block_stmts = self._safe_iterable(getattr(stmt, 'statements', None))
                block_calls, block_logs = self._analyze_statements(
                    block_stmts, imports, current_package, current_class,
                    inner_classes, class_declarations, symbol_table.copy(), scope
                )
                calls.extend(block_calls)
                logs.extend(block_logs)

        return calls, logs

    def _process_variable_declaration(self, var_decl, symbol_table, imports, current_package, current_class,
                                      inner_classes, class_declarations):
        var_type_name = self._get_type_name(var_decl.type.name)
        # 解析变量类型（包括自定义类，如EndPointState）
        var_type = self.type_resolver.resolve_type(
            var_type_name, imports, current_package, current_class,
            inner_classes, class_declarations
        )

        for declarator in var_decl.declarators:
            if isinstance(declarator, javalang.tree.VariableDeclarator):
                var_name = declarator.name
                # 记录所有类型的变量（不仅限于String）
                symbol_table[var_name] = {
                    "type": var_type,
                    "string_template": self._parse_string_expression(declarator.initializer)
                    if hasattr(declarator, 'initializer') and declarator.initializer and var_type == "java.lang.String"
                    else None
                }

    def _parse_string_expression(self, expr) -> Optional[str]:
        """
        专项优化：递归解析多层字符串拼接
        处理形如 "a" + b + "c" + d 的嵌套拼接，返回 "a{}c{}"
        """
        # 1. 字符串字面量直接返回
        if isinstance(expr, javalang.tree.Literal) and isinstance(expr.value, str) and expr.value.startswith('"'):
            return expr.value.strip('"')

        # 2. 处理+拼接（核心优化：递归解析嵌套拼接）
        if isinstance(expr, javalang.tree.BinaryOperation) and expr.operator == '+':
            # 获取左右操作数（兼容不同属性名）
            left_expr = getattr(expr, 'operandl', getattr(expr, 'left', None))
            right_expr = getattr(expr, 'operandr', getattr(expr, 'right', None))

            if not left_expr or not right_expr:
                return "{}"  # 无效表达式返回占位符

            # 递归解析左右两边
            left_str = self._parse_string_expression(left_expr)
            right_str = self._parse_string_expression(right_expr)

            # 组合结果
            if left_str is not None and right_str is not None:
                return left_str + right_str
            elif left_str is not None:
                return left_str + "{}"
            elif right_str is not None:
                return "{}" + right_str
            else:
                return "{}"

        # 3. 处理String.format调用
        if isinstance(expr, javalang.tree.MethodInvocation):
            qualifier = expr.qualifier
            if qualifier and self._get_caller_name(qualifier) == "String" and expr.member == "format":
                # 修复：确保arguments是可迭代对象（处理None）
                arguments = expr.arguments or []
                if len(arguments) >= 1:
                    format_str = self._parse_string_expression(arguments[0])
                    if format_str:
                        return re.sub(r'%[sdcf]', '{}', format_str)
                return "{}"

        # 4. 其他表达式（变量、方法调用等）视为占位符
        return None

    def _get_initializer_type(self, initializer, imports, current_package, current_class, inner_classes,
                              class_declarations):
        if isinstance(initializer, javalang.tree.ClassCreator) and hasattr(initializer, 'type'):
            type_name = self._get_type_name(initializer.type.name)
            return self.type_resolver.resolve_type(
                type_name, imports, current_package, current_class,
                inner_classes, class_declarations
            )
        return None

    def _process_method_invocation(self, invocation: javalang.tree.MethodInvocation,
                                   symbol_table: Dict[str, Any], imports: List,
                                   current_package: str, current_class: str,
                                   inner_classes: List[str], class_declarations: List[str]) -> Optional[Dict[str, Any]]:
        """记录所有方法调用，无论调用者类型（核心：不过滤任何调用）"""
        method_name = invocation.member
        line_number = invocation.position.line if hasattr(invocation, 'position') and invocation.position else None

        # 解析调用者类型（全路径）
        caller_type = self._resolve_caller_type(
            invocation.qualifier, symbol_table, imports, current_package, current_class,
            inner_classes, class_declarations
        )

        # 处理无显式调用者的方法（如this.method()或默认this调用）
        if not caller_type:
            # 默认为当前类（可能是this调用）
            caller_type = current_class

        # 记录全路径方法调用（格式：全限定类名#方法名）
        return {
            "callee": f"{caller_type}#{method_name}",
            "line": line_number
        }

    def _resolve_caller_type(self, caller, symbol_table: Dict[str, Any],
                             imports: List, current_package: str, current_class: str,
                             inner_classes: List[str], class_declarations: List[str]) -> Optional[str]:
        """解析调用者的全路径类型，支持所有形式的调用者"""
        # 1. 处理链式调用（如a.b().c()，解析外层调用者类型）
        if isinstance(caller, javalang.tree.MethodInvocation):
            return self._resolve_caller_type(
                caller.qualifier, symbol_table, imports, current_package, current_class,
                inner_classes, class_declarations
            )

        # 2. 处理成员引用（如obj.field或ClassName.staticField）
        if isinstance(caller, javalang.tree.MemberReference):
            qualifier = caller.qualifier
            member_name = caller.member
            # 解析限定符类型（如obj的类型）
            if qualifier:
                qualifier_type = self._resolve_caller_type(
                    qualifier, symbol_table, imports, current_package, current_class,
                    inner_classes, class_declarations
                )
                return qualifier_type
            # 无限定符的成员（如局部变量field）
            else:
                if member_name in symbol_table:
                    return symbol_table[member_name]["type"]

        # 3. 处理名称类型（如类名、变量名）
        if caller:
            caller_name = self._get_caller_name(caller)
            # 处理带包名的名称（如java.util.List）
            if '.' in caller_name:
                return caller_name  # 直接返回全路径
            # 从符号表查找（如局部变量/成员变量）
            if caller_name in symbol_table:
                return symbol_table[caller_name]["type"]
            # 解析为类类型（如自定义类）
            return self.type_resolver.resolve_type(
                caller_name, imports, current_package, current_class, inner_classes, class_declarations
            )

        # 4. 无调用者（如this调用，返回当前类）
        return current_class

    def _resolve_base_type(self, base_name: str, symbol_table, imports, current_package, current_class, inner_classes,
                           class_declarations):
        # 确保基础类型是全路径
        if base_name in symbol_table:
            return symbol_table[base_name]["type"]  # 符号表中存储全路径
        return self.type_resolver.resolve_type(
            base_name, imports, current_package, current_class, inner_classes, class_declarations
        )

    def _resolve_nested_caller(self, caller: javalang.tree.MethodInvocation, symbol_table, imports, current_package,
                               current_class, inner_classes, class_declarations):
        outer_caller = caller.qualifier
        return self._resolve_caller_type(outer_caller, symbol_table, imports, current_package, current_class,
                                         inner_classes, class_declarations)

    # 工具方法
    def _get_type_name(self, type_node) -> str:
        if isinstance(type_node, str):
            return type_node
        if isinstance(type_node, javalang.tree.Name):
            return ".".join(type_node.parts)
        if hasattr(type_node, 'value'):
            return type_node.value
        return str(type_node)

    def _get_caller_name(self, caller) -> str:
        if isinstance(caller, str):
            return caller
        if isinstance(caller, javalang.tree.Name):
            return ".".join(caller.parts)
        if hasattr(caller, 'value'):
            return caller.value
        return str(caller)

    def _get_expression_from_statement(self, stmt):
        if (JAVALANG_VERSION >= (0, 14, 0) and isinstance(stmt, javalang.tree.ExpressionStatement)):
            return stmt.expression
        if hasattr(stmt, 'expression'):
            return stmt.expression
        return stmt

    def _is_block_statement(self, stmt) -> bool:
        return isinstance(stmt, javalang.tree.BlockStatement) or \
            (hasattr(stmt, 'statements') and isinstance(stmt.statements, list))

    def _is_java_core_class(self, full_class_name: str) -> bool:
        for pkg in JAVA_CORE_PACKAGES:
            if full_class_name.startswith(f"{pkg}."):
                return True
        return False

    def _check_log_statement(self, invocation, symbol_table: Dict[str, Any], imports, current_package, current_class,
                             inner_classes, class_declarations, scope: str) -> Optional[Dict[str, Any]]:
        caller_type = self._resolve_caller_type(
            invocation.qualifier, symbol_table, imports, current_package, current_class,
            inner_classes, class_declarations
        )
        if not caller_type or caller_type not in self.logger_classes:
            return None

        method_name = invocation.member
        if method_name not in self.log_level_methods:
            return None

        if hasattr(invocation, 'arguments') and invocation.arguments:
            return self._extract_log_info(invocation, scope, current_class, symbol_table)
        return None

    def _extract_log_info(self, invocation, scope: str, class_name: str, symbol_table: Dict[str, Any]) -> Dict[
        str, Any]:
        """提取日志详细信息，包括模板和变量"""
        args = invocation.arguments or []  # 确保args不为None
        log_line = invocation.position.line if hasattr(invocation, 'position') and invocation.position else -1
        level = invocation.member
        variables = []

        # 处理单参数日志（核心：支持单参数是多层拼接的情况）
        if len(args) == 1:
            template_arg = args[0]
            # 直接解析整个拼接表达式为模板
            base_template = self._parse_log_template(template_arg, scope, class_name, symbol_table)
            # 提取所有变量（通过判断模板中的{}数量确定）
            var_count = base_template.count("{}")
            # 生成变量列表（实际变量名可通过进一步解析获取，此处简化为占位符索引）
            variables = [f"var_{i + 1}" for i in range(var_count)]
            return {
                'template': base_template,
                'variables': variables,
                'level': level,
                'line': log_line
            }

        # 多参数日志处理（保持不变）
        template_arg = args[0]
        var_args = args[1:]
        base_template = self._parse_log_template(template_arg, scope, class_name, symbol_table)

        for var_arg in var_args:
            var_value, is_string_var = self._get_string_var_value(var_arg, scope, class_name, symbol_table)
            if is_string_var and var_value:
                base_template = base_template.replace("{}", var_value, 1)
            else:
                var_expr = self._parse_var_expression(var_arg, scope, class_name, symbol_table)
                variables.append(var_expr)

        return {
            'template': base_template,
            'variables': variables,
            'level': level,
            'line': log_line
        }

    def _parse_log_template(self, template_node, scope: str, class_name: str, symbol_table: Dict[str, Any]) -> str:
        """解析日志模板，处理字符串、变量引用、方法调用等"""
        # 1. 处理字符串字面量（如 "Entering safe mode."）
        if isinstance(template_node, javalang.tree.Literal) and isinstance(template_node.value,
                                                                           str) and template_node.value.startswith('"'):
            return template_node.value.strip('"')

        # 2. 处理方法调用（如 block.getBlock()）
        elif isinstance(template_node, javalang.tree.MethodInvocation):
            qualifier_str = ""
            if template_node.qualifier:
                qualifier_str = self._parse_log_template(template_node.qualifier, scope, class_name, symbol_table)
            method_name = template_node.member
            args_str = [self._parse_log_template(arg, scope, class_name, symbol_table) for arg in
                        template_node.arguments]
            args_combined = ", ".join(args_str)
            return f"{qualifier_str}.{method_name}({args_combined})" if qualifier_str else f"{method_name}({args_combined})"

        # 3. 处理成员引用（如 lowResourcesMsg 或 obj.field）
        elif isinstance(template_node, javalang.tree.MemberReference):
            var_name = template_node.member
            # 检查是否是已记录的字符串变量（如果是字符串则直接返回值，否则返回占位符）
            if var_name in self.variable_string_values[scope]:
                return self.variable_string_values[scope][var_name]
            if var_name in self.variable_string_values[class_name]:
                return self.variable_string_values[class_name][var_name]
            return "{}"  # 非字符串变量返回占位符

        # 4. 处理字符串拼接（核心修复：支持多层嵌套的+操作）
        elif isinstance(template_node, javalang.tree.BinaryOperation) and template_node.operator == '+':
            # 兼容不同javalang版本的属性名（operandl/left, operandr/right）
            left_expr = getattr(template_node, 'operandl', getattr(template_node, 'left', None))
            right_expr = getattr(template_node, 'operandr', getattr(template_node, 'right', None))

            if not left_expr or not right_expr:
                return "{}"  # 无效表达式返回占位符

            # 递归解析左右两边的表达式（关键：无论左右是字符串还是变量，都完整解析）
            left_part = self._parse_log_template(left_expr, scope, class_name, symbol_table)
            right_part = self._parse_log_template(right_expr, scope, class_name, symbol_table)

            # 拼接左右结果（左边可能是字符串+占位符，右边可能是占位符+字符串）
            return f"{left_part}{right_part}"

        # 5. 处理变量引用（如直接变量名，如endpoint、FatClientTimeout_）
        elif hasattr(template_node, 'name'):
            var_name = template_node.name
            # 检查是否是已记录的字符串变量
            if var_name in self.variable_string_values[scope]:
                return self.variable_string_values[scope][var_name]
            if var_name in self.variable_string_values[class_name]:
                return self.variable_string_values[class_name][var_name]
            # 非字符串变量返回占位符
            return "{}"

        # 其他情况：判断是否为变量表达式，是则返回占位符
        if self._is_variable_expression(template_node, scope, class_name, symbol_table):
            return "{}"
        return str(template_node)

    def _get_string_var_value(self, var_node, scope: str, class_name: str, symbol_table: Dict[str, Any]) -> Tuple[
        Optional[str], bool]:
        """解析变量值，判断是否为字符串变量"""
        # 1. 处理字符串字面量
        if isinstance(var_node, javalang.tree.Literal) and isinstance(var_node.value,
                                                                      str) and var_node.value.startswith('"'):
            return var_node.value.strip('"'), True

        # 2. 处理成员引用（如 obj.field 或 field）
        if isinstance(var_node, javalang.tree.MemberReference):
            qualifier_value = None
            is_qualifier_string = False
            if var_node.qualifier:
                qualifier_value, is_qualifier_string = self._get_string_var_value(
                    var_node.qualifier, scope, class_name, symbol_table
                )

            member_name = var_node.member

            # 情况1：无限定符（如 field）
            if not var_node.qualifier:
                if member_name in self.variable_string_values[scope]:
                    return self.variable_string_values[scope][member_name], True
                if member_name in self.variable_string_values[class_name]:
                    return self.variable_string_values[class_name][member_name], True

            # 情况2：有限定符且是字符串
            elif is_qualifier_string and qualifier_value:
                return f"{qualifier_value}.{member_name}", False

            # 情况3：有限定符且是对象
            else:
                obj_name = qualifier_value if qualifier_value else str(var_node.qualifier)
                obj_type = symbol_table.get(obj_name, {}).get("type") or self._resolve_type_from_name(obj_name,
                                                                                                      class_name)
                if obj_type and member_name in self.variable_string_values.get(obj_type, {}):
                    return self.variable_string_values[obj_type][member_name], True

            return None, False

        # 3. 处理局部变量引用
        if hasattr(var_node, 'name'):
            var_name = var_node.name
            if var_name in self.variable_string_values[scope]:
                return self.variable_string_values[scope][var_name], True

        # 4. 处理字符串拼接
        if isinstance(var_node, javalang.tree.BinaryOperation) and var_node.operator == '+':
            left_val, left_is_str = self._get_string_var_value(
                getattr(var_node, 'operandl', getattr(var_node, 'left', None)),
                scope, class_name, symbol_table
            )
            right_val, right_is_str = self._get_string_var_value(
                getattr(var_node, 'operandr', getattr(var_node, 'right', None)),
                scope, class_name, symbol_table
            )
            if left_is_str and right_is_str and left_val and right_val:
                return left_val + right_val, True

        # 非字符串变量
        return None, False

    def _parse_var_expression(self, var_node, scope: str, class_name: str, symbol_table: Dict[str, Any]) -> str:
        """解析非字符串变量表达式"""
        # 处理字符串拼接中的变量部分
        if isinstance(var_node, javalang.tree.BinaryOperation) and var_node.operator == '+':
            left_expr = getattr(var_node, 'operandl', getattr(var_node, 'left', None))
            right_expr = getattr(var_node, 'operandr', getattr(var_node, 'right', None))

            left_is_var = self._is_variable_expression(left_expr, scope, class_name, symbol_table)
            right_is_var = self._is_variable_expression(right_expr, scope, class_name, symbol_table)

            if left_is_var:
                return self._parse_var_expression(left_expr, scope, class_name, symbol_table)
            elif right_is_var:
                return self._parse_var_expression(right_expr, scope, class_name, symbol_table)
            return f"{self._parse_var_expression(left_expr, scope, class_name, symbol_table)} + {self._parse_var_expression(right_expr, scope, class_name, symbol_table)}"

        # 处理方法调用
        elif isinstance(var_node, javalang.tree.MethodInvocation):
            qualifier = self._parse_var_expression(var_node.qualifier, scope, class_name,
                                                   symbol_table) if var_node.qualifier else ""
            args = [self._parse_var_expression(arg, scope, class_name, symbol_table) for arg in var_node.arguments]
            args_str = ", ".join(args)
            return f"{qualifier}.{var_node.member}({args_str})" if qualifier else f"{var_node.member}({args_str})"

        # 处理字符串字面量
        elif isinstance(var_node, javalang.tree.Literal) and isinstance(var_node.value,
                                                                        str) and var_node.value.startswith('"'):
            return var_node.value.strip('"')

        # 处理成员引用
        elif isinstance(var_node, javalang.tree.MemberReference):
            qualifier = self._parse_var_expression(var_node.qualifier, scope, class_name,
                                                   symbol_table) if var_node.qualifier else ""
            return f"{qualifier}.{var_node.member}" if qualifier else var_node.member

        # 处理变量引用
        elif hasattr(var_node, 'name'):
            return var_node.name

        # 其他类型
        return str(var_node)

    def _is_variable_expression(self, node, scope: str, class_name: str, symbol_table: Dict[str, Any]) -> bool:
        """判断节点是否为变量表达式（非字符串字面量）"""
        # 字符串字面量不是变量

        if isinstance(node, javalang.tree.MemberReference):
            return True

        if isinstance(node, javalang.tree.Literal) and isinstance(node.value, str) and node.value.startswith('"'):
            return False

        # 变量引用是变量
        if hasattr(node, 'name'):
            return True

        # 方法调用（如obj.getName()）是变量
        if isinstance(node, javalang.tree.MethodInvocation):
            return True

        # 二元运算（非字符串拼接）是变量
        if isinstance(node, javalang.tree.BinaryOperation):
            return True


        return False

    def _resolve_type_from_name(self, name: str, class_name: str) -> Optional[str]:
        """从名称解析类型（辅助方法）"""
        if '$' in class_name:
            outer_class = class_name.split('$')[0]
            if name in self.inner_classes.get(outer_class, []):
                return f"{outer_class}${name}"
        return None


if __name__ == "__main__":
    with open("parsed_enhanced_logs_general.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        version = item["version"]
        # if os.path.exists(f"tree\\{version}.json"):
        #     continue
        if version != "hadoop-1.2.0":
            continue
        analyzer = JavaCodeAnalyzer()
        project_path = f"source/{version}"  # 替换为实际项目路径
        print(f"开始分析项目: {project_path}")
        result = analyzer.analyze_project(project_path)

        with open(f"tree\\{version}.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"分析完成，结果已保存到 {version}.json")
