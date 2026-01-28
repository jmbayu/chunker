from tree_sitter_languages import get_parser
from treesitter_chunker import CodeChunker
import unittest

class TestIndentation(unittest.TestCase):
    def test_two_space_indentation(self):
        source = """def foo():
  def bar():
    return 42
  return bar()
"""
        parser = get_parser("python")
        chunker = CodeChunker(parser, "python", source)
        chunks = chunker.chunk()

        self.assertEqual(len(chunks), 2)

        # Check bar's chunk
        bar_chunk = chunks[1]
        self.assertEqual(bar_chunk.metadata["type"], "function_definition")
        expected_bar = "def bar():\n  return 42"
        self.assertEqual(bar_chunk.text.strip(), expected_bar)

    def test_deep_nesting(self):
        source = """def a():
    def b():
        def c():
            return 1
        return c()
    return b()
"""
        parser = get_parser("python")
        chunker = CodeChunker(parser, "python", source)
        chunks = chunker.chunk()

        self.assertEqual(len(chunks), 3)

        # Chunk 2 should be 'c', dedented by 8 (since 'c' starts at col 8 in 'a')
        self.assertEqual(chunks[2].text.strip(), "def c():\n    return 1")

        # Chunk 1 should be 'b', dedented by 4
        # b starts at col 4.
        # Inside b, c started at col 8. After dedenting b by 4, c is at col 4.
        expected_b = """def b():
    def c():
        -> chunk_1
    return c()"""
        self.assertEqual(chunks[1].text.strip(), expected_b)

if __name__ == "__main__":
    unittest.main()
