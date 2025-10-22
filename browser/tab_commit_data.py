from dataclasses import dataclass

@dataclass
class CommitData:
    url: str
    scroll: int
    document_height: int
    display_list: list
    has_back_history: bool
    has_forward_history: bool
    has_ssl: bool

