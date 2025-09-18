import re
import docx
from process import param_lib


class LogExtractor:
    """Accurately extract the class of log rows"""

    LOG_PATTERN = param_lib.LOG_PATTERN

    STACK_TRACE_PATTERN = param_lib.STACK_TRACE_PATTERN

    def extract_logs_and_stack_traces_and_description(self, file_path):
        """
        Extract logs, stack traces and description

        param:
            file_path: file path

        return:
            A dictionary containing logs and stack traces
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
                # Convert full-width Spaces to half-width Spaces
                line = line.replace('　', ' ')

                # Check if it is a log line
                if self.LOG_PATTERN.match(line):
                    if current_stack:
                        stack_traces.append("\n".join(current_stack))
                        current_stack = []
                    logs.append(line.strip())  # Remove the Spaces before and after
                # Check if it is a stack trace row
                elif self.STACK_TRACE_PATTERN.match(line):
                    if "Caused by" in line:
                        match = re.match(r"Caused by:.*", line)
                        current_stack.append(match.group(0))
                    else:
                        current_stack.append(line.strip())
                # Abnormal rows that are not log lines but may belong to stack traces
                elif current_stack and line.strip():
                    # Check if there are any keywords related to anomalies
                    if any(keyword in line for keyword in ["Exception", "Error", "at "]) or \
                            line.strip().startswith("\tat ") or \
                            re.search(r"\b\w+Exception\b", line):
                        current_stack.append(line.strip())

            # Handle the last possible stack trace
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
