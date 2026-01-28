import unittest
from unittest.mock import patch
from tree_sitter_language_pack import get_parser
from treesitter_chunker import TreeSitterChunker

class TestTreeSitterChunker(unittest.TestCase):
    def test_chunk_count_with_small_max_tokens(self):
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

        # We want exactly 3 chunks.
        # 1. import os
        # 2. main part 1
        # 3. main part 2
        # (The if __name__ block is ignored by the current implementation)

        # Based on estimates:
        # 'import os' is 9 chars -> 2 tokens
        # 'def main():\n' is 12 chars -> 3 tokens
        # '    def helper():\n        return 42\n' is ~39 chars -> 9 tokens
        # Total for part 1: 3 + 9 = 12 tokens

        # '    \n    x = helper()\n' is ~18 chars -> 4 tokens
        # '    print(x)\n' is 13 chars -> 3 tokens
        # Total for part 2: 3 (header) + 4 + 3 = 10 tokens

        # Setting MAX_TOKENS to 12 should make 'main' split after the first statement.
        with patch('treesitter_chunker.MAX_TOKENS', 12):
            chunker = TreeSitterChunker(
                parser=parser,
                language_name="python",
                source=code,
                file_path="test.py"
            )
            chunks = chunker.chunk()

            for i, c in enumerate(chunks):
                print(f"Chunk {i+1} metadata: {c.metadata}")
                print(f"Chunk {i+1} text:\n{c.text}")
                print("-" * 20)

            self.assertEqual(len(chunks), 3)

            # Verify types
            self.assertEqual(chunks[0].metadata['type'], 'import')
            self.assertEqual(chunks[1].metadata['type'], 'function_part')
            self.assertEqual(chunks[2].metadata['type'], 'function_part')

            # Verify content of first chunk
            self.assertIn("import os", chunks[0].text)

            # Verify both parts of main have the header
            self.assertTrue(chunks[1].text.startswith("def main():"))
            self.assertTrue(chunks[2].text.startswith("def main():"))

if __name__ == "__main__":
    unittest.main()
