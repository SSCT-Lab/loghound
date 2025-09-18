import logging
import os
from process import process_tools, log_extract
logger = logging.getLogger(__name__)

class LogBatchProcessor:
    """A class for batch processing Word document logs and stack traces"""

    def __init__(self, log_extractor):
        """
        Initialize the log batch processor

        参数:
            log_extractor: Log extractor instance
        """
        self.log_extractor = log_extractor

    def process_directory(self, directory):
        """
        Recursively process all Word documents in the directory

        param:
            directory: directory path

        return:
            A list containing the log and stack trace information of each file
        """
        results = []

        for root, _, files in os.walk(directory):
            for filename in files:
                if filename.endswith(('.docx', '.doc')):
                    file_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(file_path, directory)

                    extraction = self.log_extractor.extract_logs_and_stack_traces_and_description(file_path)

                    results.append({
                        "file": relative_path,
                        "title": extraction['title'],
                        "Description": extraction['description'],
                        "logs": extraction["logs"],
                        "stack_traces": extraction["stack_traces"]
                    })

        return results


def parse(bug_reports):
    """The process of batch processing document logs"""
    word_extractor = log_extract.LogExtractor()

    batch_processor = LogBatchProcessor(word_extractor)

    input_directory = bug_reports

    output_json = "structuration_info.json"

    results = batch_processor.process_directory(input_directory)
    process_tools.save_to_json(results, output_json)

    total_logs = sum(len(r["logs"]) for r in results)
    total_stacks = sum(len(r["stack_traces"]) for r in results)
    logger.info(
        f"A total of {len(results)} Word documents were processed, and {total_logs} logs and {total_stacks} stack "
        f"traces were extracted")
    print(
        f"A total of {len(results)} Word documents were processed, and {total_logs} logs and {total_stacks} stack "
        f"traces were extracted")
    return output_json
