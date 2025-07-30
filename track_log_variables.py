import os
import javalang
from collections import defaultdict

LOG_METHODS = {"info", "warn", "error", "debug", "trace"}

def find_java_files(root_dir):
    java_files = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".java"):
                java_files.append(os.path.join(root, file))
    return java_files

def extract_log_statements(tree):
    logs = []
    for path, node in tree.filter(javalang.tree.MethodInvocation):
        if node.qualifier and node.member.lower() in LOG_METHODS and node.qualifier.upper() == 'LOG':
            logs.append((path, node))
    return logs

def extract_variables_in_log(node):
    vars_in_log = set()

    def collect(expr):
        if isinstance(expr, javalang.tree.MemberReference):
            vars_in_log.add(expr.member)
        elif isinstance(expr, javalang.tree.BinaryOperation):
            collect(expr.operandl)
            collect(expr.operandr)
        elif isinstance(expr, javalang.tree.MethodInvocation):
            for arg in expr.arguments:
                collect(arg)
        elif isinstance(expr, javalang.tree.Cast):
            collect(expr.expression)
        elif isinstance(expr, javalang.tree.TernaryExpression):
            collect(expr.if_true)
            collect(expr.if_false)
        elif isinstance(expr, javalang.tree.ArraySelector):
            collect(expr.index)
            collect(expr.member)
        elif isinstance(expr, list):
            for child in expr:
                collect(child)
        elif hasattr(expr, 'children'):
            for child in expr.children:
                collect(child)

    for arg in node.arguments:
        collect(arg)

    return vars_in_log

def find_assignments_in_method(method_node, target_vars):
    results = defaultdict(list)

    def visit_statements(statements):
        if not statements:
            return
        for stmt in statements:
            if isinstance(stmt, javalang.tree.StatementExpression):
                expr = stmt.expression
                if isinstance(expr, javalang.tree.Assignment):
                    lhs = expr.expressionl
                    if isinstance(lhs, javalang.tree.MemberReference):
                        name = lhs.member
                        if name in target_vars:
                            results[name].append((stmt.position.line, expr))
            elif isinstance(stmt, javalang.tree.LocalVariableDeclaration):
                for declarator in stmt.declarators:
                    name = declarator.name
                    if name in target_vars:
                        results[name].append((stmt.position.line, declarator))
            elif isinstance(stmt, javalang.tree.IfStatement):
                visit_statements(stmt.then_statement.statements if stmt.then_statement else [])
                visit_statements(stmt.else_statement.statements if stmt.else_statement else [])
            elif isinstance(stmt, (javalang.tree.ForStatement, javalang.tree.WhileStatement)):
                visit_statements(stmt.body.statements if stmt.body else [])
            elif hasattr(stmt, 'statements'):
                visit_statements(stmt.statements)

    visit_statements(method_node.body)
    return results


def find_field_assignments(class_node, field_names):
    results = defaultdict(list)

    for _, method in class_node.filter((javalang.tree.ConstructorDeclaration, javalang.tree.MethodDeclaration)):
        def visit(statements):
            if not statements:
                return
            for stmt in statements:
                if isinstance(stmt, javalang.tree.StatementExpression):
                    expr = stmt.expression
                    if isinstance(expr, javalang.tree.Assignment):
                        lhs = expr.expressionl
                        if isinstance(lhs, javalang.tree.MemberReference):
                            name = lhs.member
                            if name in field_names:
                                results[name].append((stmt.position.line, expr))
                elif hasattr(stmt, 'statements'):
                    visit(stmt.statements)

        visit(method.body)

    return results


def analyze_java_file(filepath):
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        code = f.read()

    try:
        tree = javalang.parse.parse(code)
    except Exception as e:
        print(f"[ParseError] {filepath}: {e}")
        return

    for _, class_node in tree.filter(javalang.tree.ClassDeclaration):

        # 获取字段声明名集合
        class_fields = set()
        for _, decl in class_node.filter(javalang.tree.FieldDeclaration):
            for d in decl.declarators:
                class_fields.add(d.name)

        # 对每个方法分析日志变量使用情况
        for _, method_node in class_node.filter(javalang.tree.MethodDeclaration):
            if not method_node.body:
                continue

            log_calls = extract_log_statements(method_node)
            for path, log_node in log_calls:
                log_line = log_node.position.line if log_node.position else "unknown"
                vars_in_log = extract_variables_in_log(log_node)

                if not vars_in_log:
                    continue  # 跳过无变量的日志

                print(f"\nFile: {filepath}")
                print(f"Class: {class_node.name}  Method: {method_node.name}  Log Line: {log_line}")
                print(f"Variables in log: {', '.join(vars_in_log)}")

                method_assignments = find_assignments_in_method(method_node, vars_in_log)
                field_assignments = find_field_assignments(class_node, vars_in_log)

                # 方法参数识别
                param_names = {param.name for param in method_node.parameters}

                for var in vars_in_log:
                    matched = False

                    if var in param_names:
                        print(f"  [Parameter] {var} is a method parameter")
                        matched = True

                    if var in method_assignments:
                        for line, expr in method_assignments[var]:
                            print(f"  [Method Assignment] {var} assigned at line {line}: {expr}")
                            matched = True

                    if var in field_assignments:
                        for line, expr in field_assignments[var]:
                            print(f"  [Field Assignment] {var} assigned at line {line}: {expr}")
                            matched = True

                    if not matched:
                        print(f"  [Unresolved] {var} has no assignment found")

def main():
    root_dir = "tgt_sys/apache-zookeeper-3.5.8"
    java_files = find_java_files(root_dir)
    output_file = "log_variable_analysis.txt"

    with open(output_file, "w", encoding="utf-8") as out:
        for file in java_files:
            # 捕获每个文件分析中的所有打印内容
            try:
                original_stdout = os.sys.stdout
                os.sys.stdout = out
                analyze_java_file(file)
            except Exception as e:
                print(f"[Error] Analyzing {file} failed: {e}")
            finally:
                os.sys.stdout = original_stdout


if __name__ == "__main__":
    main()
