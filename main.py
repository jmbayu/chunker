# main.py
from tree_sitter_languages import get_parser
from treesitter_chunker import CodeChunker

example_file_path = "./example.py"

parser = get_parser("python")

with open(example_file_path) as f:
    source = f.read()

pipeline = CodeChunker(
    parser=parser,
    language_name="python",
    source=source,
    file_path=example_file_path,
)

chunks = pipeline.chunk()

for c in chunks:
    print(f"METADATA: {c.metadata}")
    print(c.text)
    print("=" * 50)
