from typing import List, Dict, Any
from chunks import CodeChunk

# Shared configuration
LANGUAGE_RULES = {
    "python": {
        "function": ["function_definition", "async_function_definition"],
        "class": ["class_definition"],
        "nested_blocks": [
            "function_definition",
            "async_function_definition",
            "class_definition",
            "if_statement",
            "for_statement",
            "while_statement",
            "with_statement",
            "try_statement",
            "match_statement",
            "async_with_statement",
            "async_for_statement",
        ],
        "import": [
            "import_statement",
            "import_from_statement",
        ],
        "block": ["block"],
    },
    "javascript": {
        "function": ["function_declaration", "method_definition"],
        "class": ["class_declaration"],
        "nested_blocks": [
            "function_declaration",
            "method_definition",
            "class_declaration",
            "if_statement",
            "for_statement",
            "while_statement",
            "try_statement",
            "with_statement",
            "switch_statement",
        ],
        "block": ["statement_block"],
    },
}

class CodeChunker:
    """ Unified chunker that uses Tree-sitter to semantically partition source code. """

    def __init__(self, parser, language_name: str, source: str, file_path: str | None = None):
        self.parser = parser
        self.language_name = language_name
        self.source_bytes = source.encode("utf-8")
        self.file_path = file_path
        self.tree = self.parser.parse(self.source_bytes)
        self.rules = LANGUAGE_RULES.get(language_name, LANGUAGE_RULES["python"])
        self.chunks: List[CodeChunk] = []
        self.chunk_counter = 0

    def chunk(self) -> List[CodeChunk]:
        """Main entry point to perform hierarchical chunking."""
        self.chunks = []
        self.chunk_counter = 0
        root_node = self.tree.root_node

        children = [c for c in root_node.children if c.type != 'ERROR']
        notable_types = self.rules.get("function", []) + self.rules.get("class", [])

        if len(children) == 1 and children[0].type in notable_types:
            root_content = self._recursive_chunk(children[0])
            root_chunk = CodeChunk(text=root_content, metadata={"type": "root", "file": self.file_path})
            self.chunks.append(root_chunk)
        else:
            root_text = ""
            last_end = 0
            for node in children:
                root_text += self.source_bytes[last_end:node.start_byte].decode("utf-8")
                if node.type in notable_types:
                    root_text += self._process_node(node, is_nested=False)
                else:
                    root_text += self.source_bytes[node.start_byte:node.end_byte].decode("utf-8")
                last_end = node.end_byte

            root_text += self.source_bytes[last_end:].decode("utf-8")
            self.chunks.append(CodeChunk(text=root_text, metadata={"type": "root", "file": self.file_path}))

        self.chunks.sort(key=self._sort_key)
        return self.chunks

    def _sort_key(self, chunk: CodeChunk):
        if chunk.metadata.get("type") == "root":
            return -1
        chunk_id = chunk.metadata.get("id", "chunk_999999")
        try:
            return int(chunk_id.split("_")[1])
        except (IndexError, ValueError):
            return 999999

    def _process_node(self, node, is_nested: bool) -> str:
        """Creates a chunk for the node and returns a placeholder."""
        chunk_id = f"chunk_{self.chunk_counter}"
        self.chunk_counter += 1

        header = self._get_header(node)
        placeholder = f"{header}-> {chunk_id}"

        # Get the indentation of the line where this node starts
        indent_amount = self._get_indentation(node)

        content = self._recursive_chunk(node)
        
        if is_nested and indent_amount > 0:
            content = self._dedent_by_amount(content, indent_amount)
            
        self.chunks.append(CodeChunk(
            text=content,
            metadata={
                "id": chunk_id,
                "type": node.type,
                "file": self.file_path,
                "start_byte": node.start_byte,
                "end_byte": node.end_byte
            }
        ))
        return placeholder

    def _get_indentation(self, node) -> int:
        """Find how many spaces are before the node on its starting line."""
        start_byte = node.start_byte
        line_start = start_byte
        while line_start > 0 and self.source_bytes[line_start-1] != ord('\n'):
            line_start -= 1

        prefix = self.source_bytes[line_start:start_byte].decode("utf-8")
        if prefix.strip() == "":
            return len(prefix)
        return 0

    def _dedent_by_amount(self, text: str, amount: int) -> str:
        """Remove a fixed amount of indentation from each line except the first."""
        lines = text.split('\n')
        if len(lines) <= 1:
            return text
        
        result = [lines[0]]
        for line in lines[1:]:
            if line.strip() == "":
                result.append("")
            else:
                # Remove up to 'amount' spaces
                spaces = 0
                while spaces < amount and spaces < len(line) and line[spaces] == ' ':
                    spaces += 1
                result.append(line[spaces:])
        return '\n'.join(result)

    def _recursive_chunk(self, node) -> str:
        """Extracts text of node, replacing nested sub-blocks with placeholders."""
        nested_types = self.rules.get("nested_blocks", [])
        to_chunk = []
        def find_nested(curr):
            if curr != node and curr.type in nested_types:
                to_chunk.append(curr)
                return
            for child in curr.children:
                find_nested(child)
        find_nested(node)

        res = ""
        curr_pos = node.start_byte
        for target in to_chunk:
            if target.start_byte < curr_pos:
                continue
            res += self.source_bytes[curr_pos:target.start_byte].decode("utf-8")
            res += self._process_node(target, is_nested=True)
            curr_pos = target.end_byte

        res += self.source_bytes[curr_pos:node.end_byte].decode("utf-8")
        return res

    def _get_header(self, node) -> str:
        """Captures the header of the node (before its main block)."""
        for child in node.children:
            if child.type in self.rules.get("block", []):
                return self.source_bytes[node.start_byte:child.start_byte].decode("utf-8")
        return self.source_bytes[node.start_byte:node.end_byte].decode("utf-8").split('\n')[0]
