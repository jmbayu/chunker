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
        expected_chunk_0 = """import os

def main(): # chunk:test.py::main

if __name__ == "__main__":
    main()
"""
        self.assertEqual(chunks[0].text.strip(), expected_chunk_0.strip())
        self.assertEqual(chunks[0].metadata["id"], "test.py")
        self.assertEqual(chunks[0].metadata["child_ids"], ["test.py::main"])

        # Chunk 1: main
        expected_chunk_1 = """def main():
    def helper(): # chunk:test.py::main.helper

    x = helper()
    print(x)
"""
        self.assertEqual(chunks[1].text.strip(), expected_chunk_1.strip())
        self.assertEqual(chunks[1].metadata["id"], "test.py::main")
        self.assertEqual(chunks[1].metadata["parent_id"], "test.py")
        self.assertEqual(chunks[1].metadata["child_ids"], ["test.py::main.helper"])

        # Chunk 2: helper
        expected_chunk_2 = """def helper():
    return 42"""

        self.assertEqual(chunks[2].text.strip(), expected_chunk_2.strip())
        self.assertEqual(chunks[2].metadata["id"], "test.py::main.helper")
        self.assertEqual(chunks[2].metadata["parent_id"], "test.py::main")

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

        self.assertEqual(len(chunks), 3)
        # Root chunk should reference the outer function chunk
        self.assertIn("# chunk:multibyte.py::hello", chunks[0].text)
        self.assertEqual(chunks[0].metadata["child_ids"], ["multibyte.py::hello"])
        # First child chunk should reference nested function
        self.assertIn("# chunk:multibyte.py::hello.internal", chunks[1].text)
        self.assertEqual(chunks[1].metadata["child_ids"], ["multibyte.py::hello.internal"])
        self.assertEqual(chunks[1].metadata["parent_id"], "multibyte.py")
        # Nested chunk should preserve multibyte characters
        self.assertIn('return "👋"', chunks[2].text)
        self.assertEqual(chunks[2].metadata["parent_id"], "multibyte.py::hello")

if __name__ == "__main__":
    unittest.main()
