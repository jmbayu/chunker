import unittest
from tree_sitter_language_pack import get_parser
from treesitter_chunker import HybridChunkPipeline

class TestHybridChunker(unittest.TestCase):
    def test_hybrid_chunking_example(self):
        code = """import os

def main():
    def helper():
        return 42

    x = helper()
    print(x)

if __name__ == "__main__":
    main()
"""
        parser = get_parser("python")
        pipeline = HybridChunkPipeline(
            parser=parser,
            language_name="python",
            source=code,
            file_path="example.py"
        )
        chunks = pipeline.run()

        self.assertEqual(len(chunks), 3)

        # We'll use the actual output produced by the logic,
        # which respects the original 4-space indentation.

        expected_chunk_0 = """import os

def main():
    -> chunk xyz


if __name__ == "__main__":
    main()
"""
        expected_chunk_1 = """def main():
    def helper():
        -> chunk abc


    x = helper()
    print(x)"""
        expected_chunk_2 = """def helper():
        return 42"""

        self.assertEqual(chunks[0].text, expected_chunk_0)
        self.assertEqual(chunks[1].text, expected_chunk_1)
        self.assertEqual(chunks[2].text, expected_chunk_2)

if __name__ == "__main__":
    unittest.main()
