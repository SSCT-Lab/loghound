import logging

logger = logging.getLogger(__name__)

# Java core package and class mapping
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
    'Long': 'java.lang.Long',
    'List': 'java.util.List',
    'Map': 'java.util.Map',
    'Set': 'java.util.Set',
    'ArrayList': 'java.util.ArrayList',
    'HashMap': 'java.util.HashMap',
    'PrintStream': 'java.io.PrintStream'
}


class JavaTypeResolver:
    """type parser"""

    def __init__(self, project_classes):
        self.type_cache = {}
        self.wildcard_imports_cache = dict()
        self.project_classes = project_classes

    def resolve_type(self, simple_name, imports,
                     current_package, current_class,
                     inner_classes, class_declarations):
        logger.info(f"Resolving type: simple_name={simple_name}, current_class={current_class}")

        cache_key = (simple_name, tuple(imports), current_package, current_class,
                     tuple(inner_classes), tuple(class_declarations))
        if cache_key in self.type_cache:
            return self.type_cache[cache_key]

        # give priority to identifying Java core classes
        if simple_name in JAVA_CORE_CLASSES:
            self.type_cache[cache_key] = JAVA_CORE_CLASSES[simple_name]
            return JAVA_CORE_CLASSES[simple_name]

        # inner class
        if simple_name in inner_classes:
            result = f"{current_class}${simple_name}"
            self.type_cache[cache_key] = result
            return result

        # The top-level class of the current file
        if simple_name in class_declarations:
            result = f"{current_package}.{simple_name}" if current_package else simple_name
            self.type_cache[cache_key] = result
            return result

        # Single-type import
        for imp in imports:
            if not imp.static and not imp.wildcard:
                imp_class_name = imp.path.split('.')[-1]
                if imp_class_name == simple_name:
                    self.type_cache[cache_key] = imp.path
                    return imp.path

        # wildcard import
        for imp in imports:
            if not imp.static and imp.wildcard:
                package = imp.path[:-2]  # Remove the wildcard "*"
                # Check whether the target class exists under this package in the project
                if package in self.project_classes and simple_name in self.project_classes[package]:
                    result = f"{package}.{simple_name}"
                    self.type_cache[cache_key] = result
                    return result

        # The classes under the current package
        if current_package:
            # Check whether the current package is in the project class
            if current_package in self.project_classes and simple_name in self.project_classes[current_package]:
                result = f"{current_package}.{simple_name}"
                self.type_cache[cache_key] = result
                return result

        # When parsing is not possible, it still returns the full-path format
        result = f"unknown.package.{simple_name}" if not current_package else f"{current_package}.{simple_name}"
        self.type_cache[cache_key] = result
        return result
