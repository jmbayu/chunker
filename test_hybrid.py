import unittest
from tree_sitter_languages import get_parser
from treesitter_chunker import CodeChunker

class TestHybridChunker(unittest.TestCase):
    def test_user_example(self):
        # We use a slightly modified version of example.py to match the user's assert structure
        source = """import os

def main():
    def helper():
        return 42

    x = helper()
    print(x)

if __name__ == "__main__":
    main()
"""

        parser = get_parser("python")
        pipeline = CodeChunker(
            parser=parser,
            language_name="python",
            source=source,
            file_path="test.py"
        )
        chunks = pipeline.chunk()

        for i, c in enumerate(chunks):
            print(f"CHUNK {i}:")
            print(f"'{c.text}'")
            print("-" * 20)

        self.assertEqual(len(chunks), 3)

        # Chunk 0: Root
        # Note: the placeholder will be "def main(): -> chunk_0"
        # The source has "def main():\n"
        # _get_header returns "def main():\n    " (because the block starts with indentation)
        # .rstrip() makes it "def main():"

        expected_chunk_0 = """import os

def main():
    -> chunk_0

if __name__ == "__main__":
    main()
"""
        self.assertEqual(chunks[0].text.strip(), expected_chunk_0.strip())

        # Chunk 1: main
        expected_chunk_1 = """
def main():
    def helper():
        -> chunk_1

    x = helper()
    print(x)
"""
        self.assertEqual(chunks[1].text.strip(), expected_chunk_1.strip())

        # Chunk 2: helper
        expected_chunk_2 = """def helper():
    return 42"""

        self.assertEqual(chunks[2].text.strip(), expected_chunk_2.strip())

    def test_multibyte_characters(self):
        source = """def hello():
    # Hello 🌍
    def internal():
        return "👋"
    return internal()"""

        parser = get_parser("python")
        pipeline = CodeChunker(
            parser=parser,
            language_name="python",
            source=source,
            file_path="multibyte.py"
        )
        chunks = pipeline.chunk()

        self.assertEqual(len(chunks), 2)
        # Check root chunk has placeholder
        self.assertIn("def internal():\n        -> chunk_0", chunks[0].text)
        # Check internal chunk has correct content
        self.assertIn('return "👋"', chunks[1].text)

if __name__ == "__main__":
    unittest.main()
