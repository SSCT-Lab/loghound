import os
from collections import defaultdict
from javalang import parse, tree, tokenizer
from analyzer import tools
from analyzer.type_resolver import JavaTypeResolver
import logging

logger = logging.getLogger(__name__)


class JavaCodeAnalyzer:
    def __init__(self, source_dir):
        self.source_dir = source_dir
        self.class_locations = {}
        self.class_imports = defaultdict()
        self.results = defaultdict(lambda: {
            "location": {"file": "", "line": 0},
            "methods": [],
        })
        self.project_classes = defaultdict(set)
        self.inner_classes = defaultdict(list)
        self.type_resolver = JavaTypeResolver(self.project_classes)
        self.imports = defaultdict(list)
        self.class_declarations = defaultdict(list)
        self.package_name = defaultdict(str)
        self.method_variables = defaultdict(dict)
        self.return_type = defaultdict(dict)
        self.simple_to_full_name = defaultdict(str)
        self.field_types = defaultdict(dict)
        self.variable_string_values = defaultdict(dict)

    def analyze(self):
        logger.info("collecting project classes and preprocessing the required content")
        self.collect_project_classes(self.source_dir)
        logger.info("processing methods")
        self.process_methods(self.source_dir)

        return self.results

    def collect_project_classes(self, project_path):
        for root, _, files in os.walk(project_path):
            for file in files:
                if file.endswith('.java') and "Test" not in file:
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        tokens = list(tokenizer.tokenize(content))

                        ast = parse.parse(content)

                        package_name = ""
                        if ast.package:
                            package_name = ast.package.name

                        imports = ast.imports
                        class_declarations = [class_decl.name for _, class_decl in ast.filter(tree.ClassDeclaration)]

                        for _, class_decl in ast.filter(tree.ClassDeclaration):
                            class_name = class_decl.name
                            qualified_name = f"{package_name}.{class_name}" if package_name else class_name
                            logger.info(f"collecting {qualified_name}")

                            self.imports[qualified_name] = imports
                            self.class_declarations[qualified_name] = class_declarations
                            self.package_name[qualified_name] = package_name
                            self.project_classes[package_name].add(class_name)
                            self.collect_inner_classes(class_decl, qualified_name)
                            self.collect_return_type(class_decl, qualified_name)
                            self.simple_to_full_name[class_name] = qualified_name

                            current_inner_classes = self.inner_classes.get(qualified_name, [])

                            line = tools.find_node_line(tokens, class_decl)

                            self.class_locations[qualified_name] = {
                                "file": file_path,
                                "line": line
                            }
                            self.class_imports[qualified_name] = imports

                            self.results[qualified_name]["location"] = {
                                "file": file_path,
                                "line": line
                            }

                            for _, field_decl in class_decl.filter(tree.FieldDeclaration):
                                field_type = self.type_resolver.resolve_type(field_decl.type.name, imports,
                                                                             package_name,
                                                                             qualified_name,
                                                                             current_inner_classes, class_declarations)
                                for declarator in field_decl.declarators:
                                    field_name = declarator.name
                                    logger.info(f"collecting {qualified_name}.{field_name}")
                                    self.field_types[qualified_name][field_name] = field_type
                                    self._record_string_values(field_type, declarator, qualified_name, field_name)

                    except Exception as e:
                        logger.error(f"Failed to collect such information {file_path}: {str(e)}")

    def collect_return_type(self, class_decl, full_class_name):
        """collection the return type of the methods"""
        for method_decl in class_decl.methods:
            method_name = method_decl.name
            return_type = method_decl.return_type
            if not self.return_type[full_class_name]:
                self.return_type[full_class_name] = dict()
            if return_type:
                self.return_type[full_class_name][method_name] = return_type.name

    def collect_inner_classes(self, type_decl, outer_class_full_name):
        if not hasattr(type_decl, 'body'):
            return
        for decl in type_decl.body:
            if isinstance(decl, tree.ClassDeclaration):
                inner_name = decl.name
                self.inner_classes[outer_class_full_name].append(inner_name)
                self.collect_inner_classes(decl, f"{outer_class_full_name}${inner_name}")

    def process_methods(self, project_path):
        for root, _, files in os.walk(project_path):
            for file in files:
                if file.endswith('.java') and "Test" not in file:
                    file_path = os.path.join(root, file)
                    self.analyze_methods(file_path)

    def analyze_methods(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tokens = list(tokenizer.tokenize(content))
            ast = parse.parse(content)

            package_name = ""
            if ast.package:
                package_name = ast.package.name

            # Handle the methods in each class
            seen_class = set()
            for _, class_decl in ast.filter(tree.ClassDeclaration):
                class_name = class_decl.name
                for _, inner_class_decl in class_decl.filter(tree.ClassDeclaration):
                    inner_class_name = inner_class_decl.name
                    seen_class.add(inner_class_name)
                    if inner_class_name != class_name:
                        inner_class_name = class_name + "$" + inner_class_decl.name
                    self.analyze_methods_from_class(inner_class_decl, package_name, tokens, file_path, inner_class_name)
                break
        except Exception as e:
            print(f"Error analyzing methods in {file_path}: {e}")

    def analyze_methods_from_class(self, class_decl, package_name, tokens, file_path, class_name):
        qualified_class_name = f"{package_name}.{class_name}" if package_name else class_name
        imports = self.imports.get(qualified_class_name, [])
        class_declarations = self.class_declarations.get(qualified_class_name, [])
        current_inner_classes = self.inner_classes.get(qualified_class_name, [])

        # Handle each method in the class
        for method_decl in class_decl.methods:
            method_name = method_decl.name
            method_signature = f"{qualified_class_name}#{method_name}"

            # Find the line number of the method declaration
            method_line = tools.find_node_line(tokens, method_decl)

            # Create the method scope
            method_scope = f"{qualified_class_name}#{method_name}"

            logger.info(f"analyze method: {method_signature}")

            # Processing method parameters
            if method_decl.parameters:
                for param in method_decl.parameters:
                    logger.info(f"collecting parameters: {param.name}")
                    param_type = self.type_resolver.resolve_type(param.type.name, imports, package_name,
                                                                 qualified_class_name, current_inner_classes,
                                                                 class_declarations)
                    self._resolve_variable_type(method_signature, param.name, param_type)

            # Analyze the method body and construct the variable type mapping
            if method_decl.body:
                for _, method_local_variable in method_decl.filter(tree.LocalVariableDeclaration):
                    variable_type = self.type_resolver.resolve_type(method_local_variable.type.name, imports,
                                                                    package_name, qualified_class_name,
                                                                    current_inner_classes, class_declarations)

                    for declarator in method_local_variable.declarators:
                        variable_name = declarator.name
                        logger.info(f"collecting variable: {variable_name}")
                        self._resolve_variable_type(method_signature, variable_name, variable_type)
                        self._record_string_values(variable_type, declarator, qualified_class_name,
                                                   variable_name)

            calls = []
            logs = []

            if method_decl.body:
                for _, method_invocation in method_decl.filter(tree.MethodInvocation):
                    if tools.is_log_method(method_invocation):
                        logger.info(f"collecting log from the method: {method_signature}")
                        logs.append(
                            self._extract_method_logs(method_invocation, method_signature,
                                                      qualified_class_name))

                    line = tools.find_node_line(tokens, method_invocation)

                    # Parse the method call and try to find the complete class name
                    callee = self._resolve_method_invocation(
                        method_invocation,
                        qualified_class_name,
                        method_scope
                    )

                    if callee and not any(call_item.get('callee') == callee for call_item in calls):
                        calls.append({
                            "callee": callee,
                            "line": line
                        })

            self.results[qualified_class_name]["methods"].append({
                method_signature: {
                    "location": {
                        "file": file_path,
                        "line": method_line
                    },
                    "calls": list(calls),
                    "logs": logs
                }
            })

    def _resolve_variable_type(self, method_signature, variable_name, variable_type):
        if self.method_variables[method_signature]:
            self.method_variables[method_signature][variable_name] = variable_type
        else:
            self.method_variables[method_signature] = dict()
            self.method_variables[method_signature][variable_name] = variable_type

    def _record_string_values(self, variable_type, declarator, qualified_name, field_name):
        if variable_type == "java.lang.String":
            if declarator.initializer and isinstance(declarator.initializer, tree.Literal):
                self.variable_string_values[qualified_name][field_name] = declarator.initializer.value.strip('"')
            elif declarator.initializer and isinstance(declarator.initializer,
                                                       tree.MethodInvocation) and declarator.initializer.qualifier == "String":
                str_value = ""
                for arg in declarator.initializer.arguments:
                    if isinstance(arg, tree.Literal):
                        str_value += tools.replace_placeholders(arg.value.strip('"'))
                self.variable_string_values[qualified_name][field_name] = str_value

    def _resolve_qualifier_type(self, qualifier, scope, class_name):
        """Parse the type of the qualifier"""
        if not qualifier:
            return class_name

        parts = qualifier.split('.')

        if len(parts) == 1:
            return self._process_simple_variable(parts[0], scope, class_name)
        else:
            return self._process_complex_variable(parts, scope, class_name)

    def _process_simple_variable(self, var_name, scope, class_name):
        if tools.contains(self.method_variables, scope):
            if tools.contains(self.method_variables[scope], var_name):
                return self.method_variables[scope][var_name]

            elif tools.contains(self.field_types, class_name):
                if tools.contains(self.field_types[class_name], var_name):
                    return self.field_types[class_name][var_name]

        return self.type_resolver.resolve_type(var_name, self.imports[class_name], self.package_name[class_name],
                                               class_name, self.inner_classes[class_name],
                                               self.class_declarations[class_name])

    def _process_complex_variable(self, parts, scope, class_name):
        base = parts[0]
        flag = True
        if tools.contains(self.method_variables, scope):
            if tools.contains(self.method_variables[scope], base):
                base = self.method_variables[scope][base]
                flag = False

        if flag and tools.contains(self.field_types, class_name):
            if tools.contains(self.field_types[class_name], base):
                base = self.field_types[class_name][base]

        # Search for field types step by step
        for part in parts[1:]:
            if tools.contains(self.return_type, base):
                current_type = self.return_type[base].get(part)
                if current_type:
                    base = self.simple_to_full_name[current_type]
                else:
                    return base
            else:
                return base
        return base

    def _resolve_method_invocation(self, method_invocation, current_class, scope):
        """Parse the method call and try to find the complete class name"""
        qualifier = method_invocation.qualifier
        method_name = method_invocation.member

        # Handling Special Cases: this and super
        if qualifier in ['this', 'super']:
            return f"{current_class}#{method_name}"

        # Try to parse the actual type of the qualifier
        resolved_type = self._resolve_qualifier_type(qualifier, scope, current_class)
        if resolved_type:
            return f"{resolved_type}#{method_name}"

        # Unable to parse, return unknown
        return f"{current_class}.unknown#{method_name}"

    def _extract_method_logs(self, node, method_key, class_name):
        """Extract the log statements within the method and handle multi-parameter situations"""
        log_line = node.position.line if node.position else -1
        level = node.member

        # Single-parameter log processing (such as log.info(e))
        if len(node.arguments) == 1:
            template_arg = node.arguments[0]
            # Parse the template and automatically replace the variable with {}
            base_template = self.parse_log_template(template_arg, method_key, class_name)

            return {
                'template': base_template,
                'level': level,
                'line': log_line
            }

        # Multi-parameter log processing
        template_arg = node.arguments[0]
        var_args = node.arguments[1:]
        base_template = self.parse_log_template(template_arg, method_key, class_name)
        base_template = tools.replace_placeholders(base_template)
        if level == 'error':
            return {
                'template': base_template,
                'level': level,
                'line': log_line
            }
        for var_arg in var_args:
            value = self.parse_log_template(var_arg, method_key, class_name)
            base_template = base_template.replace("{}", value, 1)

        return {
            'template': base_template,
            'level': level,
            'line': log_line
        }

    def parse_log_template(self, template_node, scope, class_name):
        """Parse the log template, with a focus on handling local variables of the MemberReference type"""
        # 1. Handle string literals
        if isinstance(template_node, tree.Literal):
            return template_node.value.strip('"')

        # 2. Processing method calls (such as String.format())
        elif isinstance(template_node, tree.MethodInvocation) and template_node.qualifier == "String":
            args_str = []
            for arg in template_node.arguments:
                args_str.append(self.parse_log_template(arg, scope, class_name))
            base_str = tools.replace_placeholders(args_str[0])

            return base_str

        # 3. Handle local variable references (MemberReference type)
        elif isinstance(template_node, tree.MemberReference):
            var_name = template_node.member
            # Check if it is a recorded string variable
            if var_name in self.variable_string_values[class_name]:
                return self.variable_string_values[class_name][var_name]
            return "{}"

        # 4. Handling string concatenation (such as a + b) Handling string concatenation
        elif isinstance(template_node, tree.BinaryOperation) and template_node.operator == '+':
            # Recursively parse the left and right sides
            left_part = self.parse_log_template(template_node.operandl, scope, class_name)
            right_part = self.parse_log_template(template_node.operandr, scope, class_name)
            return f"{left_part}{right_part}"

        # 5. Handle other variable reference types
        elif hasattr(template_node, 'name'):
            var_name = template_node.name
            # String variables retain their values, while other variables are converted to {}
            if var_name in self.variable_string_values[scope]:
                return self.variable_string_values[scope][var_name]
        else:
            return "{}"


if __name__ == '__main__':
    import json

    list_dir = os.listdir("../project_sc")
    for file in list_dir:
        if os.path.exists(rf"E:\Code\loghound\process\ProcessData\tree\{file}.json"):
            continue
        print(f"Processing : {file}")
        source_code = os.path.join("../project_sc", file)
        analyzer = JavaCodeAnalyzer(source_code)
        res = analyzer.analyze()
        with open(f"../process/ProcessData/tree/{file}.json", "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)
