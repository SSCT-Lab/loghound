import logging
import os
import re
import json
import docx
from typing import Dict, List, Any


class WordLogExtractor:
    """从Word文档中精准提取日志行的类"""

    # 进一步优化的日志行正则表达式模式
    LOG_PATTERN = re.compile(
        r"""
        ^\s*
        (?:
            # 模式1: 时间戳 [标识1] - 日志级别 [标识2] - 消息
            \d{4}[-\//]\d{2}[-\//]\d{2}\s+\d{2}:\d{2}:\d{2}[\.,]\d+\s*
            \[[^\]]+\]\s*-\s*
            (FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
            \[[^\]]+\]\s*-\s*
        )
        |
        (?:
            # 模式2: [线程信息] 时间戳 日志级别 ... (支持多空格)
            \[\w+(?:[:/]\S+)*\]\s*
            (?:\d{4}[-\//](?:\d{2}[-\//]\d{2}|\w{3}\s+\d{2})|\d{2}[-\//]\d{2}[-\//]\d{2}|\d{1,2}:\d{2}:\d{2})\s+
            \d{2}:\d{2}:\d{2}[\.,]\d+\s+
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
        )
        |
        (?:
            # 模式3: 时间戳 日志级别 [线程信息] ... (支持多空格)
            (?:\d{4}[-\//](?:\d{2}[-\//]\d{2}|\w{3}\s+\d{2})|\d{2}[-\//]\d{2}[-\//]\d{2}|\d{1,2}:\d{2}:\d{2})\s+
            \d{2}:\d{2}:\d{2}[\.,]\d+\s+
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
            \[\w+(?:[:/]\S+)*\]\s+
        )
        |
        (?:
            # 模式4: 日志级别 [线程信息] 时间戳 ... (支持多空格)
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
            \[\w+(?:[:/]\S+)*\]\s+
            (?:\d{4}[-\//](?:\d{2}[-\//]\d{2}|\w{3}\s+\d{2})|\d{2}[-\//]\d{2}[-\//]\d{2}|\d{1,2}:\d{2}:\d{2})\s+
            \d{2}:\d{2}:\d{2}[\.,]\d+\s+
        )
        |
        (?:
            # 模式5: 完整时间戳 日志级别 类名: ... (支持多空格)
            (?:\d{4}[-\//](?:\d{2}[-\//]\d{2}|\w{3}\s+\d{2})|\d{2}[-\//]\d{2}[-\//]\d{2}|\d{1,2}:\d{2}:\d{2})\s+
            \d{2}:\d{2}:\d{2}[\.,]\d+\s+
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
            (?:\w+\.|org\.apache\.hadoop\.)[^\s:]+\s*:\s*
        )
        |
        (?:
            # 模式6: 日志级别 类名: ... (支持多空格)
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
            (?:\w+\.|org\.apache\.hadoop\.)[^\s:]+\s*:\s*
        )
        |
        (?:
            # 模式7: Zookeeper特殊格式: - 日志级别 [线程信息] ... (支持多空格)
            -\s*
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
            \[\w+(?:[:/]\S+)*\]\s+
        )
        |
        (?:
            # 模式8: 时间戳|组件|日志级别|消息 (支持多空格)
            (?:\d{4}[-\//](?:\d{2}[-\//]\d{2}|\w{3}\s+\d{2})|\d{2}[-\//]\d{2}[-\//]\d{2}|\d{1,2}:\d{2}:\d{2})\s+
            \d{2}:\d{2}:\d{2}[\.,]\d+\|
            [^\|]+\|
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\|
        )
        |
        (?:
            # 模式9: 时间戳 - 日志级别 [线程信息] ... (支持多空格)
            (?:\d{4}[-\//](?:\d{2}[-\//]\d{2}|\w{3}\s+\d{2})|\d{2}[-\//]\d{2}[-\//]\d{2}|\d{1,2}:\d{2}:\d{2})\s+
            \d{2}:\d{2}:\d{2}[\.,]\d+\s*-\s*
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
            \[\w+(?:[:/]\S+)*\]\s+
        )
        |
        (?:
            # 模式10: 日志文件前缀:时间戳 日志级别 ... (支持多空格)
            [\w\.]+\.log(?:\.\d+)?(?:-[^\s:]+)?:
            (?:\d{4}[-\//](?:\d{2}[-\//]\d{2}|\w{3}\s+\d{2})|\d{2}[-\//]\d{2}[-\//]\d{2}|\d{1,2}:\d{2}:\d{2})\s+
            \d{2}:\d{2}:\d{2}[\.,]\d+\s*-\s*
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
        )
        |
        (?:
            # 模式11: 月份缩写 日期, 年份 时间 日志级别 ... (支持多空格)
            \w{3}\s+\d{2},\s+\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+(?:AM|PM)\s+
            [\w\.]+\s+
            (?:FATAL|ERROR|WARN|INFO|DEBUG|TRACE|SEVERE)\s+
        )
        .*
        $
        """,
        re.VERBOSE | re.IGNORECASE | re.MULTILINE
    )

    # 堆栈跟踪正则表达式模式
    STACK_TRACE_PATTERN = re.compile(
        r"""
        ^\s*
        (?:
            # 模式1: 异常类名开头（支持前导空格和制表符）
            (java\.\w+|\w+\.\w+Exception)(?::\s+.+)?$
        )
        |
        (?:
            # 模式2: at 开头的方法调用（支持不同缩进）
            ^\s*at\s+.+?\(.*?\)$
        )
        |
        (?:
            # 模式3: Caused by: 异常（支持不同缩进）
            ^\s*Caused by:\s+.+?Exception(?::\s+.+)?$
        )
        |
        (?:
            # 模式4: ... 数字 more（支持不同缩进）
            ^\s*\.\.\.+\s+\d+\s+more$
        )
        |
        (?:
            # 模式5: Exception in thread "..." 格式
            ^\s*Exception in thread\s+"[^\"]+"\s+.+?Exception(?::\s+.+)?$
        )
        |
        (?:
            # 模式6: 版本信息行 (如: ~[zookeeper-3.5.0.jar:3.5.0--1])
            ^\s*~?\s*\[[^\]]+\]$
        )
        """,
        re.VERBOSE | re.MULTILINE
    )

    def extract_logs_and_stack_traces_and_description(self, file_path: str) -> Dict[str, List[str]]:
        """
        从Word文档中提取日志和堆栈跟踪（支持更多格式）

        参数:
            file_path: Word文档路径

        返回:
            包含日志和堆栈跟踪的字典
        """
        try:
            doc = docx.Document(file_path)
            paragraphs = [para.text.strip() for para in doc.paragraphs]

            title = paragraphs[0].strip() if len(paragraphs) > 1 else ""
            description = paragraphs[1].strip() if len(paragraphs) > 1 else ""
            logs = []
            stack_traces = []
            current_stack = []

            for line in paragraphs:
                # 处理全角空格转换为半角空格
                line = line.replace('　', ' ')

                # 检查是否为日志行（允许行首空格）
                if self.LOG_PATTERN.match(line):
                    if current_stack:
                        stack_traces.append("\n".join(current_stack))
                        current_stack = []
                    logs.append(line.strip())  # 去除前后空格
                # 检查是否为堆栈跟踪行
                elif self.STACK_TRACE_PATTERN.match(line):
                    current_stack.append(line.strip())  # 去除前后空格
                # 非日志行但可能属于堆栈跟踪的异常行
                elif current_stack and line.strip():
                    # 检查是否包含异常相关关键词
                    if any(keyword in line for keyword in ["Exception", "Error", "at "]) or \
                            line.strip().startswith("\tat ") or \
                            re.search(r"\b\w+Exception\b", line):
                        current_stack.append(line.strip())

            # 处理最后一个可能的堆栈跟踪
            if current_stack:
                stack_traces.append("\n".join(current_stack))

            return {
                "title": title,
                "description": description,
                "logs": logs,
                "stack_traces": stack_traces
            }

        except Exception as e:
            print(f"Error processing Word document '{file_path}': {e}")
            return {"logs": [], "stack_traces": []}


class LogBatchProcessor:
    """批量处理Word文档日志和堆栈跟踪的类"""

    def __init__(self, log_extractor: WordLogExtractor):
        """
        初始化日志批量处理器

        参数:
            log_extractor: 日志提取器实例
        """
        self.log_extractor = log_extractor

    def process_directory(self, directory: str) -> List[Dict[str, Any]]:
        """
        递归处理目录中的所有Word文档

        参数:
            directory: 目录路径

        返回:
            包含每个文件日志和堆栈跟踪信息的列表
        """
        results = []

        for root, _, files in os.walk(directory):
            for filename in files:
                if filename.endswith(('.docx', '.doc')):
                    file_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(file_path, directory)

                    # 提取日志和堆栈跟踪
                    extraction = self.log_extractor.extract_logs_and_stack_traces_and_description(file_path)

                    results.append({
                        "file": relative_path,
                        "title": extraction['title'],
                        "Description": extraction['description'],
                        "logs": extraction["logs"],
                        "stack_traces": extraction["stack_traces"]
                    })

        return results

    def save_to_json(self, results: List[Dict[str, Any]], output_path: str) -> None:
        """
        将处理结果保存到JSON文件

        参数:
            results: 处理结果列表
            output_path: 输出JSON文件路径
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"结果已保存到 {output_path}")
        except Exception as e:
            print(f"Error saving JSON file: {e}")


def parse(bug_reports):
    """The process of batch processing document logs"""
    word_extractor = WordLogExtractor()

    # 创建日志批量处理器
    batch_processor = LogBatchProcessor(word_extractor)

    # 要处理的目录路径
    input_directory = bug_reports

    # 输出JSON文件路径
    output_json = "structuration_info.json"

    results = batch_processor.process_directory(input_directory)
    batch_processor.save_to_json(results, output_json)

    total_logs = sum(len(r["logs"]) for r in results)
    total_stacks = sum(len(r["stack_traces"]) for r in results)
    logging.info(f"共处理 {len(results)} 个Word文档，提取了 {total_logs} 条日志和 {total_stacks} 个堆栈跟踪")
    print(f"共处理 {len(results)} 个Word文档，提取了 {total_logs} 条日志和 {total_stacks} 个堆栈跟踪")
    return output_json