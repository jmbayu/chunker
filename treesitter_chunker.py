from typing import List, Dict, Any
from chunks import CodeChunk

MAX_TOKENS = 400


LANGUAGE_RULES = {
    "python": {
        "function": ["function_definition"],
        "class": ["class_definition"],
        "nested_blocks": [
            "function_definition",
            "class_definition",
            "if_statement",
            "for_statement",
            "while_statement",
            "with_statement",
            "try_statement",
        ],
        "import": [
            "import_statement",
            "import_from_statement",
        ],
        "block": ["block"],
    },
    "javascript": {
        "function": ["function_declaration"],
        "class": ["class_declaration"],
        "nested_blocks": [
            "function_declaration",
            "class_declaration",
            "if_statement",
            "for_statement",
            "while_statement",
            "try_statement",
        ],
        "block": ["statement_block"],
    },
}

def estimate_tokens(text: str) -> int:
    return len(text) // 4  # Rough estimate: 1 token ~ 4 characters

class TreeSitterChunker:
    def __init__(
        self,
        parser,
        language_name: str,
        source: str,
        file_path: str | None = None,
    ):
        self.parser = parser
        self.rules = LANGUAGE_RULES[language_name]
        self.source_bytes = source.encode("utf-8")
        self.text = source
        self.tree = self.parser.parse(self.source_bytes)
        self.file_path = file_path

    def chunk(self) -> List[CodeChunk]:
        chunks = []
        root = self.tree.root_node

        for node in root.children:
            if node.type in self.rules["function"]:
                chunks.extend(self._chunk_function(node))

            elif (
                self.rules.get("class")
                and node.type in self.rules["class"]
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

        block_types = self.rules["block"]
        for child in node.children:
            if child.type in block_types:
                body_node = child
                header_end = child.start_byte
                break

        if not body_node:
            return [self._make_chunk(node, "function")]

        header_text = self.source_bytes[node.start_byte:header_end].decode("utf-8")
        current_chunk_text = header_text
        last_stmt_end = header_end
        part = 1

        for stmt in body_node.children:
            # Include everything from the end of the last statement (or header) to the end of this statement
            stmt_full_text = self.source_bytes[last_stmt_end:stmt.end_byte].decode("utf-8")

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
        return self.source_bytes[node.start_byte:node.end_byte].decode("utf-8")

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
    def __init__(self, parser, language_name: str, source: str, file_path: str | None = None):
        self.parser = parser
        self.language_name = language_name
        self.source_bytes = source.encode("utf-8")
        self.file_path = file_path
        self.tree = self.parser.parse(self.source_bytes)
        self.rules = LANGUAGE_RULES.get(language_name, LANGUAGE_RULES["python"])
        self.chunks = []
        self.chunk_counter = 0

    def chunk(self) -> List[CodeChunk]:
        self.chunks = []
        self.chunk_counter = 0
        root_node = self.tree.root_node

        children = [c for c in root_node.children if c.type != 'ERROR']
        notable_types = self.rules.get("function", []) + self.rules.get("class", [])

        if len(children) == 1 and children[0].type in notable_types:
            root_content = self._recursive_chunk(children[0], is_nested=False)
            root_chunk = CodeChunk(text=root_content, metadata={"type": "root", "file": self.file_path})
            self.chunks.append(root_chunk)
        else:
            root_text = ""
            last_end = 0
            for node in children:
                root_text += self.source_bytes[last_end:node.start_byte].decode("utf-8")
                if node.type in notable_types:
                    root_text += self._process_as_nested(node, is_nested=False)
                else:
                    root_text += self.source_bytes[node.start_byte:node.end_byte].decode("utf-8")
                last_end = node.end_byte
            root_text += self.source_bytes[last_end:].decode("utf-8")

            root_chunk = CodeChunk(text=root_text, metadata={"type": "root", "file": self.file_path})
            self.chunks.append(root_chunk)

        self.chunks.sort(key=lambda c: -1 if c.metadata.get("type") == "root" else 
                         int(c.metadata.get("id", "chunk_999999").split("_")[1]))
        return self.chunks

    def _process_as_nested(self, node, is_nested: bool) -> str:
        chunk_id = f"chunk_{self.chunk_counter}"
        self.chunk_counter += 1

        header = self._get_header(node)
        placeholder = f"{header}-> {chunk_id}"

        content = self._recursive_chunk(node, is_nested=True)
        
        # Dedent nested functions to remove parent indentation
        if is_nested:
            content = self._dedent(content)
            
        self.chunks.append(CodeChunk(text=content, metadata={"id": chunk_id, "type": node.type, "file": self.file_path}))
        return placeholder

    def _dedent(self, text: str) -> str:
        """Remove common indentation from all lines except the first."""
        lines = text.split('\n')
        if len(lines) <= 1:
            return text
        
        # Find indentation of the second line (first line of body)
        # This is the base indentation we want to keep
        body_indent = None
        for line in lines[1:]:
            if line.strip():
                body_indent = len(line) - len(line.lstrip(' '))
                break
        
        if body_indent is None or body_indent == 0:
            return text
        
        # Calculate how much to dedent: we want to reduce by 4 spaces
        # (the parent function's indentation level)
        dedent_amount = 4
        
        # Remove dedent_amount from all lines except first
        result = [lines[0]]
        for line in lines[1:]:
            if line.strip():
                spaces = len(line) - len(line.lstrip(' '))
                result.append(line[min(dedent_amount, spaces):])
            else:
                result.append(line)
        
        return '\n'.join(result)

    def _recursive_chunk(self, node, is_nested: bool) -> str:
        nested_types = self.rules.get("nested_blocks", [])
        to_chunk = []

        def find_to_chunk(curr):
            if curr != node and curr.type in nested_types:
                to_chunk.append(curr)
                return
            for child in curr.children:
                find_to_chunk(child)

        find_to_chunk(node)

        res = ""
        curr_pos = node.start_byte
        for tc_node in to_chunk:
            if tc_node.start_byte < curr_pos:
                continue
            res += self.source_bytes[curr_pos:tc_node.start_byte].decode("utf-8")
            res += self._process_as_nested(tc_node, is_nested=True)
            curr_pos = tc_node.end_byte
        res += self.source_bytes[curr_pos:node.end_byte].decode("utf-8")

        return res

    def _get_header(self, node) -> str:
        block_types = self.rules.get("block", [])
        for child in node.children:
            if child.type in block_types:
                return self.source_bytes[node.start_byte:child.start_byte].decode("utf-8")
        return self.source_bytes[node.start_byte:node.end_byte].decode("utf-8").split('\n')[0]
