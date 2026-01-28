# Code Chunking Refactor Improvements

This document outlines the improvements made to the code chunking tool.

## 1. Unified Architecture
- **Consolidation**: Merged `TreeSitterChunker` and `HybridChunkPipeline` into a single, cohesive `CodeChunker` class. This eliminates redundancy and provides a single, well-defined entry point for semantic code chunking.
- **Lean Implementation**: Removed duplicate logic for Tree-sitter initialization, node traversal, and rule handling. The new implementation is more concise and easier to maintain.

## 2. Dynamic Indentation Handling
- **Smart Dedenting**: Replaced the hardcoded 4-space dedent logic with a dynamic approach. The tool now detects the actual indentation level of a code block in the source file and removes exactly that amount from the chunk.
- **Valid Code Chunks**: Chunks now start at column 0 while preserving their internal relative indentation, making them more readable and easier to use in RAG pipelines or for code analysis.
- **Deep Nesting Support**: The dynamic dedenting works correctly across any number of nesting levels (e.g., functions within functions within classes), ensuring that each chunk is properly formatted regardless of its depth in the original source.

## 3. Improved Recursive Logic
- **Clean Slicing**: Refactored the recursive node processing to use a cleaner, more linear approach for extracting text between nested blocks and placeholders.
- **Robust Headers**: Improved the `_get_header` method to accurately capture the declaration part of a node (e.g., `def foo():`) without including unnecessary trailing whitespace or messing up placeholder placement.
- **Consistent Placeholders**: Ensured that placeholders are inserted at the correct indentation level in parent chunks, matching the original source structure.

## 4. Expanded Language Support
- **Comprehensive Rules**: Updated `LANGUAGE_RULES` for Python and JavaScript to include more statement types for nesting, such as `async` definitions, `match/switch` statements, `try/except/finally`, and `with` blocks.
- **Unified notable types**: Standardized which types are treated as major chunks (functions and classes) vs. which are traversed recursively.

## 5. Better Metadata and Sorting
- **Rich Metadata**: Consistently include `id`, `type`, `file`, `start_byte`, and `end_byte` in chunk metadata.
- **Natural Sorting**: Implemented a robust sorting mechanism that keeps the `root` chunk first and subsequent chunks in the order they were discovered, matching the logical flow of the code.
