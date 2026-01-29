from typing import List, Dict, Any
import re
from chunks import CodeChunk

class CodeChunker:
    """ Unified chunker that uses Tree-sitter to semantically partition source code. """

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

    def __init__(self, parser, language_name: str, source: str, file_path: str | None = None):
        self.parser = parser
        self.language_name = language_name
        self.source_bytes = source.encode("utf-8")
        self.file_path = file_path
        self.tree = self.parser.parse(self.source_bytes)
        self.rules = self.LANGUAGE_RULES.get(language_name, self.LANGUAGE_RULES["python"])
        self.chunks: List[CodeChunk] = []
        self.root_id: str | None = None
        self._id_sequence = 0

    def chunk(self) -> List[CodeChunk]:
        """Main entry point to perform hierarchical chunking."""
        self.chunks = []
        self._id_sequence = 0
        root_node = self.tree.root_node
        children = [c for c in root_node.children if c.type != "ERROR"]
        notable_types = set(self.rules.get("function", []) + self.rules.get("class", []))
        self.root_id = self.file_path or "<stdin>"

        root_text, child_ids = self._build_root(children, notable_types)
        root_metadata = {
            "id": self.root_id,
            "type": "root",
            "file": self.file_path,
            "language": self.language_name,
            "parent_id": None,
            "child_ids": child_ids,
            "start_byte": 0,
            "end_byte": len(self.source_bytes),
            "start_line": 1,
            "end_line": root_node.end_point[0] + 1,
        }
        self.chunks.append(CodeChunk(text=root_text, metadata=root_metadata))

        self.chunks.sort(key=self._sort_key)
        return self.chunks

    def _sort_key(self, chunk: CodeChunk):
        is_root = 0 if chunk.metadata.get("type") == "root" else 1
        return (is_root, chunk.metadata.get("start_byte", 0))

    def _build_root(self, children, notable_types):
        root_parts = []
        child_ids: List[str] = []
        last_end = 0
        for node in children:
            root_parts.append(self._slice_source(last_end, node.start_byte))
            if node.type in notable_types:
                placeholder, child_id = self._build_chunk(node, self.root_id)
                root_parts.append(placeholder)
                child_ids.append(child_id)
            else:
                root_parts.append(self._slice_source(node.start_byte, node.end_byte))
            last_end = node.end_byte
        root_parts.append(self._slice_source(last_end, len(self.source_bytes)))
        return "".join(root_parts), child_ids

    def _build_chunk(self, node, parent_id: str | None):
        chunk_id = self._make_chunk_id(node, parent_id)
        raw_label = self._extract_label(node)
        header = self._get_header(node)
        indent_prefix = self._get_indent_prefix(node)
        content, child_ids = self._extract_node_content(node, chunk_id)
        if indent_prefix:
            content = self._dedent_by_prefix(content, indent_prefix)
        placeholder = self._format_placeholder(header, chunk_id)
        metadata: Dict[str, Any] = {
            "id": chunk_id,
            "type": node.type,
            "file": self.file_path,
            "language": self.language_name,
            "parent_id": parent_id,
            "child_ids": child_ids,
            "start_byte": node.start_byte,
            "end_byte": node.end_byte,
            "start_line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
        }
        if raw_label:
            metadata["label"] = raw_label
        self.chunks.append(CodeChunk(text=content, metadata=metadata))
        return placeholder, chunk_id

    def _get_indent_prefix(self, node) -> str:
        """Find the actual whitespace prefix before the node on its starting line."""
        start_byte = node.start_byte
        line_start = start_byte
        while line_start > 0 and self.source_bytes[line_start-1] not in (ord('\n'), ord('\r')):
            line_start -= 1

        prefix = self.source_bytes[line_start:start_byte].decode("utf-8")
        if prefix.strip() == "":
            return prefix
        return ""

    def _dedent_by_prefix(self, text: str, prefix: str) -> str:
        """Remove the parent's indentation prefix from every line."""
        if not prefix:
            return text
        lines = text.split('\n')
        if len(lines) == 1:
            return lines[0][len(prefix):] if lines[0].startswith(prefix) else lines[0]
        adjusted = []
        for line in lines:
            if line.startswith(prefix):
                adjusted.append(line[len(prefix):])
            else:
                adjusted.append(line)
        return '\n'.join(adjusted)

    def _get_header(self, node) -> str:
        """Captures the header of the node (before its main block), stripped of trailing whitespace."""
        block_types = self.rules.get("block", [])
        for child in node.children:
            if child.type in block_types:
                header = self._slice_source(node.start_byte, child.start_byte)
                return header.rstrip()
        fallback = self._slice_source(node.start_byte, node.end_byte).split('\n')[0]
        return fallback.rstrip()

    def _extract_node_content(self, node, chunk_id: str):
        targets = self._find_nested_targets(node)
        pieces = []
        child_ids: List[str] = []
        curr_pos = node.start_byte
        for target in targets:
            if target.start_byte < curr_pos:
                continue
            pieces.append(self._slice_source(curr_pos, target.start_byte))
            placeholder, child_id = self._build_chunk(target, chunk_id)
            pieces.append(placeholder)
            child_ids.append(child_id)
            curr_pos = target.end_byte
        pieces.append(self._slice_source(curr_pos, node.end_byte))
        return "".join(pieces), child_ids

    def _find_nested_targets(self, node):
        nested_types = set(self.rules.get("nested_blocks", []))
        if not nested_types:
            return []

        targets = []

        def visit(curr):
            for child in curr.children:
                if child.type == "ERROR":
                    continue
                if child.type in nested_types:
                    targets.append(child)
                    continue
                visit(child)

        visit(node)
        return sorted(targets, key=lambda n: n.start_byte)

    def _format_placeholder(self, header: str, chunk_id: str) -> str:
        line = header.rstrip()
        if not line:
            return f"# chunk:{chunk_id}"
        suffix = f"# chunk:{chunk_id}"
        if line.endswith(":"):
            return f"{line} {suffix}"
        return f"{line}  {suffix}"

    def _make_chunk_id(self, node, parent_id: str | None) -> str:
        label = self._extract_label(node)
        identifier = self._sanitize_identifier(label) if label else None
        if identifier is None:
            identifier = f"{node.type}_{self._next_counter()}"
        if not parent_id:
            return identifier
        if self.root_id and parent_id == self.root_id:
            return f"{parent_id}::{identifier}"
        return f"{parent_id}.{identifier}"

    def _extract_label(self, node) -> str:
        for field in ("name", "identifier"):
            field_node = node.child_by_field_name(field)
            if field_node is not None:
                return self._slice_source(field_node.start_byte, field_node.end_byte).strip()
        return ""

    def _sanitize_identifier(self, label: str) -> str | None:
        cleaned = re.sub(r"\s+", "_", label.strip())
        cleaned = re.sub(r"[^0-9A-Za-z_]+", "_", cleaned)
        cleaned = cleaned.strip("_")
        return cleaned or None

    def _slice_source(self, start: int, end: int) -> str:
        if start >= end:
            return ""
        return self.source_bytes[start:end].decode("utf-8")

    def _next_counter(self) -> int:
        current = self._id_sequence
        self._id_sequence += 1
        return current
