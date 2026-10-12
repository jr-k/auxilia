from enum import Enum


class WorkspaceEventKind(str, Enum):
    threads = "threads"
    runs = "runs"
    prompt_queue = "prompt_queue"
    trigger_history = "trigger_history"
