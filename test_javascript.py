import unittest
from tree_sitter_languages import get_parser
from treesitter_chunker import CodeChunker

class TestJavaScriptIndentation(unittest.TestCase):
    def test_messy_javascript(self):
        source = """function foo() {
  if (true) {
console.log("hi");
  }
}"""
        parser = get_parser("javascript")
        chunker = CodeChunker(parser, "javascript", source)
        chunks = chunker.chunk()

        # Root chunk should have placeholder
        # The header for 'if' is 'if (true) '
        self.assertIn('if (true) -> chunk_0', chunks[0].text)

        # if chunk should be dedented relative to 'if' (prefix '  ')
        expected_if = 'if (true) {\nconsole.log("hi");\n}'
        self.assertEqual(chunks[1].text.strip(), expected_if)

    def test_tab_indentation(self):
        source = "function bar() {\n\tif (true) {\n\t\tconsole.log('tab');\n\t}\n}"
        parser = get_parser("javascript")
        chunker = CodeChunker(parser, "javascript", source)
        chunks = chunker.chunk()

        # 'if' has prefix '\t'
        expected_if = "if (true) {\n\tconsole.log('tab');\n}"
        self.assertEqual(chunks[1].text.strip(), expected_if)

if __name__ == "__main__":
    unittest.main()
