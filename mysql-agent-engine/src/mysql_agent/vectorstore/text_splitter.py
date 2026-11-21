"""
Simple recursive character text splitter - no external dependencies.
Compatible replacement for langchain's RecursiveCharacterTextSplitter.
"""
import re
from typing import List, Optional


class RecursiveCharacterTextSplitter:
    """
    Split text recursively by separators.
    """
    
    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 150,
        separators: Optional[List[str]] = None,
        length_function: callable = len,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or [
            "\n## ", "\n### ", "\n#### ",
            "\n\n", "\n",
            "。", "！", "？",
            " ", ""
        ]
        self.length_function = length_function
    
    def split_text(self, text: str) -> List[str]:
        """Split text into chunks."""
        return self._split_text(text, self.separators)
    
    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Recursively split text by separators."""
        if not text:
            return []
        
        # Try each separator
        for sep in separators:
            if sep == "":
                # Character-level split as last resort
                return self._split_by_char(text)
            
            if sep in text:
                splits = text.split(sep)
                chunks = []
                current_chunk = ""
                
                for split in splits:
                    # Add separator back (except for the last split)
                    if split != splits[-1]:
                        split = split + sep
                    
                    if self.length_function(current_chunk + split) <= self.chunk_size:
                        current_chunk += split
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = split
                
                if current_chunk:
                    chunks.append(current_chunk)
                
                # Merge small chunks with overlap
                return self._merge_chunks(chunks)
        
        # No separator found, split by character
        return self._split_by_char(text)
    
    def _split_by_char(self, text: str) -> List[str]:
        """Split by character with chunk_size."""
        chunks = []
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunk = text[i:i + self.chunk_size]
            if chunk:
                chunks.append(chunk)
        return chunks
    
    def _merge_chunks(self, chunks: List[str]) -> List[str]:
        """Merge chunks with overlap handling."""
        if not chunks:
            return []
        
        # If only one chunk, return as is
        if len(chunks) == 1:
            return chunks if self.length_function(chunks[0]) <= self.chunk_size else self._split_by_char(chunks[0])
        
        merged = []
        current = chunks[0]
        
        for next_chunk in chunks[1:]:
            if self.length_function(current + next_chunk) <= self.chunk_size:
                current += next_chunk
            else:
                merged.append(current)
                current = next_chunk
        
        if current:
            merged.append(current)
        
        # Apply overlap between chunks
        if len(merged) > 1 and self.chunk_overlap > 0:
            overlapped = [merged[0]]
            for i in range(1, len(merged)):
                prev_end = merged[i-1][-self.chunk_overlap:] if len(merged[i-1]) > self.chunk_overlap else merged[i-1]
                overlapped.append(prev_end + merged[i])
            return overlapped
        
        return merged


# Test the splitter
if __name__ == "__main__":
    splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=50)
    text = """# 第一章 基础架构

## 1.1 MySQL架构概述

MySQL的架构分为Server层和存储引擎层。Server层负责连接处理、查询缓存、解析器、优化器、执行器等。存储引擎层负责数据的存储和提取。

### 连接器

连接器负责跟客户端建立连接、获取权限、维持和管理连接。

### 查询缓存

查询缓存是将查询语句作为key，将查询结果作为value存储在内存中。

## 1.2 存储引擎

InnoDB是MySQL默认的存储引擎，支持事务、行级锁、外键约束。

### B+树索引

InnoDB使用B+树作为索引数据结构。B+树的特点是所有数据都存储在叶子节点，非叶子节点只存储索引键值。"""

    chunks = splitter.split_text(text)
    print(f"Generated {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i+1} ({len(chunk)} chars) ---")
        print(chunk[:200] + ("..." if len(chunk) > 200 else ""))
