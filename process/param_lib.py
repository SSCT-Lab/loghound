import re

java_keywords = [
        'abstract', 'assert', 'boolean', 'break', 'byte', 'case', 'catch', 'char',
        'class', 'const', 'continue', 'default', 'do', 'double', 'else', 'enum',
        'extends', 'final', 'finally', 'float', 'for', 'goto', 'if', 'implements',
        'import', 'instanceof', 'int', 'interface', 'long', 'native', 'new',
        'package', 'private', 'protected', 'public', 'return', 'short', 'static',
        'strictfp', 'super', 'switch', 'synchronized', 'this', 'throw', 'throws',
        'transient', 'try', 'void', 'volatile', 'while'
    ]

go_keywords = [
    'break', 'default', 'func', 'interface', 'select', 'case', 'defer', 'go',
    'map', 'struct', 'chan', 'else', 'goto', 'package', 'switch', 'const',
    'fallthrough', 'if', 'range', 'type', 'continue', 'for', 'import',
    'return', 'var'
]

javascript_keywords = [
    'break', 'case', 'catch', 'class', 'const', 'continue', 'debugger', 'default',
    'delete', 'do', 'else', 'export', 'extends', 'finally', 'for', 'function',
    'if', 'import', 'in', 'instanceof', 'let', 'new', 'return', 'super',
    'switch', 'this', 'throw', 'try', 'typeof', 'var', 'void', 'while', 'with',
    'yield'
]

stop_words = ['public', 'class', 'void', 'new', 'if', 'else', 'for', 'while', 'return',
                  '{', '}', '(', ')', ';', '...']

LOG_PATTERN = re.compile(
        r"""
        ^\s*
        (?:
            \d{4}[-\//]\d{2}[-\//]\d{2}\s+\d{2}:\d{2}:\d{2}[\.,]\d+\s*
            \[[^\]]+\]\s*-\s*
            (FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
            \[[^\]]+\]\s*-\s*
        )
        |
        (?:
            \[\w+(?:[:/]\S+)*\]\s*
            (?:\d{4}[-\//](?:\d{2}[-\//]\d{2}|\w{3}\s+\d{2})|\d{2}[-\//]\d{2}[-\//]\d{2}|\d{1,2}:\d{2}:\d{2})\s+
            \d{2}:\d{2}:\d{2}[\.,]\d+\s+
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
        )
        |
        (?:
            (?:\d{4}[-\//](?:\d{2}[-\//]\d{2}|\w{3}\s+\d{2})|\d{2}[-\//]\d{2}[-\//]\d{2}|\d{1,2}:\d{2}:\d{2})\s+
            \d{2}:\d{2}:\d{2}[\.,]\d+\s+
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
            \[\w+(?:[:/]\S+)*\]\s+
        )
        |
        (?:
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
            \[\w+(?:[:/]\S+)*\]\s+
            (?:\d{4}[-\//](?:\d{2}[-\//]\d{2}|\w{3}\s+\d{2})|\d{2}[-\//]\d{2}[-\//]\d{2}|\d{1,2}:\d{2}:\d{2})\s+
            \d{2}:\d{2}:\d{2}[\.,]\d+\s+
        )
        |
        (?:
            (?:\d{4}[-\//](?:\d{2}[-\//]\d{2}|\w{3}\s+\d{2})|\d{2}[-\//]\d{2}[-\//]\d{2}|\d{1,2}:\d{2}:\d{2})\s+
            \d{2}:\d{2}:\d{2}[\.,]\d+\s+
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
            (?:\w+\.|org\.apache\.hadoop\.)[^\s:]+\s*:\s*
        )
        |
        (?:
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
            (?:\w+\.|org\.apache\.hadoop\.)[^\s:]+\s*:\s*
        )
        |
        (?:
            -\s*
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
            \[\w+(?:[:/]\S+)*\]\s+
        )
        |
        (?:
            (?:\d{4}[-\//](?:\d{2}[-\//]\d{2}|\w{3}\s+\d{2})|\d{2}[-\//]\d{2}[-\//]\d{2}|\d{1,2}:\d{2}:\d{2})\s+
            \d{2}:\d{2}:\d{2}[\.,]\d+\|
            [^\|]+\|
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\|
        )
        |
        (?:
            (?:\d{4}[-\//](?:\d{2}[-\//]\d{2}|\w{3}\s+\d{2})|\d{2}[-\//]\d{2}[-\//]\d{2}|\d{1,2}:\d{2}:\d{2})\s+
            \d{2}:\d{2}:\d{2}[\.,]\d+\s*-\s*
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
            \[\w+(?:[:/]\S+)*\]\s+
        )
        |
        (?:
            [\w\.]+\.log(?:\.\d+)?(?:-[^\s:]+)?:
            (?:\d{4}[-\//](?:\d{2}[-\//]\d{2}|\w{3}\s+\d{2})|\d{2}[-\//]\d{2}[-\//]\d{2}|\d{1,2}:\d{2}:\d{2})\s+
            \d{2}:\d{2}:\d{2}[\.,]\d+\s*-\s*
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
        )
        |
        (?:
            \w{3}\s+\d{2},\s+\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+(?:AM|PM)\s+
            [\w\.]+\s+
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
        )
        .*
        $
        """,
        re.VERBOSE | re.IGNORECASE | re.MULTILINE
    )


STACK_TRACE_PATTERN = re.compile(
        r"""
        ^\s*
        (?:
            (java\.\w+|\w+\.\w+Exception)(?::\s+.+)?$
        )
        |
        (?:
            ^\s*at\s+.+?\(.*?\)$
        )
        |
        (?:
            ^\s*Caused by:\s+.+?Exception(?::\s+.+)?$
        )
        |
        (?:
            ^\s*\.\.\.+\s+\d+\s+more$
        )
        |
        (?:
            ^\s*Exception in thread\s+"[^\"]+"\s+.+?Exception(?::\s+.+)?$
        )
        |
        (?:
            ^\s*~?\s*\[[^\]]+\]$
        )
        """,
        re.VERBOSE | re.MULTILINE
    )