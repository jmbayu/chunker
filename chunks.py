# chunks.py
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class CodeChunk:
    text: str
    metadata: Dict[str, Any]
