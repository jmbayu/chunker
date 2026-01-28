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

        header_text = self.text[node.start_byte:header_end]
        current_chunk_text = header_text
        last_stmt_end = header_end
        part = 1

        for stmt in body_node.children:
            # Include everything from the end of the last statement (or header) to the end of this statement
            stmt_full_text = self.text[last_stmt_end:stmt.end_byte]

            if estimate_tokens(current_chunk_text + stmt_full_text) > MAX_TOKENS:
                if current_chunk_text != header_text:
                    # Emit current chunk
                    chunks.append(
                        CodeChunk(
                            text=current_chunk_text,
                            metadata={
                                "type": "function_part",
                                "part": part,
                                "file": self.file_path,
                            }
                        )
                    )
                    part += 1
                    # Start new chunk with header and this statement
                    current_chunk_text = header_text + stmt_full_text
                else:
                    # First statement is already too big, we must include it
                    current_chunk_text += stmt_full_text
            else:
                current_chunk_text += stmt_full_text

            last_stmt_end = stmt.end_byte

        if current_chunk_text != header_text:
            chunks.append(
                CodeChunk(
                    text=current_chunk_text,
                    metadata={
                        "type": "function_part",
                        "part": part,
                        "file": self.file_path,
                    }
                )
            )

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


class HybridChunkPipeline:
    def __init__(
        self,
        parser,
        language_name: str,
        source: str,
        file_path: str | None = None,
    ):
        self.parser = parser
        self.language_name = language_name
        self.source_str = source
        self.source_bytes = source.encode()
        self.file_path = file_path
        self.rules = LANGUAGE_RULES.get(language_name, {})
        self.tree = self.parser.parse(self.source_bytes)
        self.chunks = []
        self.placeholder_idx = 0

    def _get_placeholder(self) -> str:
        predefined = ["abc", "xyz", "def", "ghi"]
        if self.placeholder_idx < len(predefined):
            p = predefined[self.placeholder_idx]
        else:
            p = f"id_{self.placeholder_idx}"
        self.placeholder_idx += 1
        return p

    def run(self) -> List[CodeChunk]:
        self.chunks = []
        self.placeholder_idx = 0
        root_text = self._traverse(self.tree.root_node)

        root_chunk = CodeChunk(
            text=root_text,
            metadata={"type": "file", "file": self.file_path}
        )
        return [root_chunk] + list(reversed(self.chunks))

    def _traverse(self, node) -> str:
        if node.type == self.rules.get("function") or node.type == self.rules.get("class"):
            block_node = next((c for c in node.children if c.type == self.rules.get("block")), None)
            if block_node:
                processed_body = ""
                last_end = block_node.start_byte
                for child in block_node.children:
                    processed_body += self.source_str[last_end:child.start_byte]
                    processed_body += self._traverse(child)
                    last_end = child.end_byte
                processed_body += self.source_str[last_end:block_node.end_byte]

                header = self.source_str[node.start_byte:block_node.start_byte]
                full_text = header + processed_body

                self.chunks.append(CodeChunk(text=full_text, metadata={"type": node.type, "file": self.file_path}))

                p = self._get_placeholder()

                # If header ends with whitespace (indentation), just append placeholder.
                # Otherwise, add some indentation.
                if header.endswith(" "):
                    return header + "-> chunk " + p + "\n"
                else:
                    return header + "    -> chunk " + p + "\n"

        if node.child_count == 0:
            return self.source_str[node.start_byte:node.end_byte]

        res = ""
        last_end = node.start_byte
        for child in node.children:
            res += self.source_str[last_end:child.start_byte]
            res += self._traverse(child)
            last_end = child.end_byte
        res += self.source_str[last_end:node.end_byte]
        return res
