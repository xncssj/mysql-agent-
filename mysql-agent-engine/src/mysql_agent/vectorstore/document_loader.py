"""
Document loading and chunking for MySQL knowledge base.
Supports three GeekTime columns: MySQL实战45讲, MySQL运维实战课, SQL必知必会
"""
import os
import re
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional
from tqdm import tqdm

# Use custom text splitter to avoid langchain dependency issues
from .text_splitter import RecursiveCharacterTextSplitter


@dataclass
class DocumentChunk:
    """A single chunk of documentation with metadata."""
    chunk_id: str
    source_column: str
    source_file: str
    file_order: int
    title: str
    content: str
    token_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentChunk":
        return cls(**data)


class DocumentLoader:
    """Loads and chunks markdown documents from GeekTime columns."""
    
    # Default source directories (override with GEEKTIME_DOCS_ROOT)
    _DOCS_ROOT = Path(os.environ.get("GEEKTIME_DOCS_ROOT", "~/giteeInfo/geektime-docs-master")).expanduser()
    DEFAULT_SOURCES = {
        "mysql45": str(_DOCS_ROOT / "后端-架构/MySQL实战45讲/docs"),
        "mysql_ops": str(_DOCS_ROOT / "后端-架构/MySQL运维实战课/docs"),
        "sql_master": str(_DOCS_ROOT / "后端-架构/SQL必知必会/docs"),
    }
    
    def __init__(
        self,
        sources: Optional[Dict[str, str]] = None,
        chunk_size: int = 800,
        chunk_overlap: int = 150,
        min_chunk_length: int = 50,
    ):
        self.sources = sources or self.DEFAULT_SOURCES
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_length = min_chunk_length
        
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n## ", "\n### ", "\n#### ", 
                "\n\n", "\n", 
                "。", "！", "？", 
                " ", ""
            ],
            length_function=len,
        )
    
    def load_all(self) -> List[DocumentChunk]:
        """Load all documents from all configured sources."""
        all_chunks = []
        
        for column_name, source_dir in self.sources.items():
            chunks = self._load_column(column_name, source_dir)
            all_chunks.extend(chunks)
            print(f"📂 {column_name}: {len(chunks)} chunks from {source_dir}")
        
        return all_chunks
    
    def _load_column(self, column_name: str, source_dir: str) -> List[DocumentChunk]:
        """Load all markdown files from a single column directory."""
        source_path = Path(source_dir)
        if not source_path.exists():
            print(f"⚠️ Directory not found: {source_dir}")
            return []
        
        md_files = sorted(source_path.glob("*.md"))
        chunks = []
        
        for order, md_file in enumerate(md_files):
            if md_file.name in ("index.md", "README.md"):
                continue
            
            file_chunks = self._process_file(column_name, md_file, order)
            chunks.extend(file_chunks)
        
        return chunks
    
    def _process_file(self, column_name: str, md_file: Path, file_order: int) -> List[DocumentChunk]:
        """Process a single markdown file into chunks."""
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception as e:
            print(f"❌ Failed to read {md_file}: {e}")
            return []
        
        # Extract title from first # heading
        title_match = re.match(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else md_file.stem
        
        # Split into chunks
        raw_chunks = self.splitter.split_text(content)
        
        chunks = []
        for i, chunk_text in enumerate(raw_chunks):
            chunk_text = chunk_text.strip()
            if len(chunk_text) < self.min_chunk_length:
                continue
            
            # Generate deterministic chunk ID
            chunk_id = hashlib.md5(
                f"{column_name}:{md_file.name}:{i}".encode()
            ).hexdigest()[:12]
            
            chunks.append(DocumentChunk(
                chunk_id=chunk_id,
                source_column=column_name,
                source_file=md_file.name,
                file_order=file_order,
                title=title,
                content=chunk_text,
                token_count=len(chunk_text) // 2,  # Rough Chinese token estimate
                metadata={
                    "column": column_name,
                    "file": md_file.name,
                    "order": file_order,
                    "chunk_index": i,
                    "title": title,
                }
            ))
        
        return chunks
    
    def get_stats(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        """Generate statistics about loaded chunks."""
        stats = {
            "total_chunks": len(chunks),
            "total_tokens": sum(c.token_count for c in chunks),
            "by_column": {},
            "by_file": {},
        }
        
        for chunk in chunks:
            col = chunk.source_column
            if col not in stats["by_column"]:
                stats["by_column"][col] = {"chunks": 0, "tokens": 0}
            stats["by_column"][col]["chunks"] += 1
            stats["by_column"][col]["tokens"] += chunk.token_count
            
            file_key = f"{col}/{chunk.source_file}"
            if file_key not in stats["by_file"]:
                stats["by_file"][file_key] = 0
            stats["by_file"][file_key] += 1
        
        return stats
