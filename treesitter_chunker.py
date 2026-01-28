# treesitter_chunker.py
from typing import List
from chunks import CodeChunk

MAX_TOKENS = 400


LANGUAGE_RULES = {
    "python": {
        "function": "function_definition",
        "class": "class_definition",
        "import": [
            "import_statement",
            "import_from_statement",
        ],
        "block": "block",
    },
    "javascript": {
        "function": "function_declaration",
        "class": "class_declaration",
        "block": "statement_block",
    },
}

def estimate_tokens(text: str) -> int:
    return len(text) // 4  # Rough estimate: 1 token ~ 4 characters

class TreeSitterChunker:
    def __init__(
        self,
        parser,              # <-- parser, not Language
        language_name: str,
        source: str,
        file_path: str | None = None,
    ):
        self.parser = parser
        self.rules = LANGUAGE_RULES[language_name]
        self.source = source.encode()
        self.text = source
        self.tree = self.parser.parse(self.source)
        self.file_path = file_path

    def chunk(self) -> List[CodeChunk]:
        chunks = []
        root = self.tree.root_node

        for node in root.children:
            if node.type == self.rules["function"]:
                chunks.extend(self._chunk_function(node))

            elif (
                self.rules.get("class")
                and node.type == self.rules["class"]
            ):
                chunks.append(self._make_chunk(node, "class"))

            elif (
                self.rules.get("import")
                and node.type in self.rules["import"]
            ):
                chunks.append(self._make_chunk(node, "import"))

        return chunks

    # ---------------------------
    # Function chunking
    # ---------------------------
    def _chunk_function(self, node) -> List[CodeChunk]:
        text = self._node_text(node)

        if estimate_tokens(text) <= MAX_TOKENS:
            return [self._make_chunk(node, "function")]

        return self._split_large_function(node)

    def _split_large_function(self, node) -> List[CodeChunk]:
        chunks = []
        header_end = None
        body_node = None

        for child in node.children:
            if child.type == self.rules["block"]:
                body_node = child
                header_end = child.start_byte
                break

        if not body_node:
            return [self._make_chunk(node, "function")]

        header = self.text[node.start_byte:header_end]

        part = 1
        for stmt in body_node.children:
            candidate = header + self._node_text(stmt)

            if estimate_tokens(candidate) > MAX_TOKENS:
                chunks.append(
                    CodeChunk(
                        text=candidate,
                        metadata={
                            "type": "function_part",
                            "part": part,
                            "file": self.file_path,
                        }
                    )
                )
                part += 1

        return chunks

    # ---------------------------
    # Helpers
    # ---------------------------
    def _node_text(self, node) -> str:
        return self.text[node.start_byte:node.end_byte]

    def _make_chunk(self, node, chunk_type: str) -> CodeChunk:
        return CodeChunk(
            text=self._node_text(node),
            metadata={
                "type": chunk_type,
                "file": self.file_path,
                "start_byte": node.start_byte,
                "end_byte": node.end_byte,
            }
        )
