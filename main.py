# main.py
from tree_sitter_language_pack import get_parser
from treesitter_chunker import TreeSitterChunker

example_file_path = "./example.py"

parser = get_parser("python")

with open(example_file_path) as f:
    source = f.read()

pipeline = TreeSitterChunker(
    parser=parser,
    language_name="python",
    source=source,
    file_path=example_file_path,
)

chunks = pipeline.chunk()

for c in chunks:
    print("METADATA:", c.metadata)
    print(c.text)
    print("=" * 50)
