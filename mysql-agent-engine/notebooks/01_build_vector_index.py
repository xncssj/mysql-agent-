#!/usr/bin/env python3
"""
Build vector index from three GeekTime MySQL columns.
Processes: MySQL实战45讲, MySQL运维实战课, SQL必知必会
"""
import os
import re
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
from tqdm import tqdm

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter

# ──────────────────────────────────────────────────────────────
# 配置
# ──────────────────────────────────────────────────────────────
DOCS_ROOT = Path(os.environ.get("GEEKTIME_DOCS_ROOT", "~/giteeInfo/geektime-docs-master")).expanduser()
SOURCE_DIRS = {
    "mysql45": str(DOCS_ROOT / "后端-架构/MySQL实战45讲/docs"),
    "mysql_ops": str(DOCS_ROOT / "后端-架构/MySQL运维实战课/docs"),
    "sql_master": str(DOCS_ROOT / "后端-架构/SQL必知必会/docs"),
}

OUTPUT_DIR = Path(__file__).resolve().parents[2]
VECTOR_DIR = OUTPUT_DIR / "data" / "vector_index"
KG_DIR = OUTPUT_DIR / "data" / "knowledge_graph"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # 支持中文

# ──────────────────────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────────────────────
@dataclass
class DocumentChunk:
    chunk_id: str
    source_column: str
    source_file: str
    file_order: int
    title: str
    content: str
    token_count: int
    metadata: Dict[str, Any]

# ──────────────────────────────────────────────────────────────
# 文档加载与切片
# ──────────────────────────────────────────────────────────────
def load_markdown_files() -> List[DocumentChunk]:
    """加载所有 markdown 文件并切片"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", "。", "！", "？", " ", ""],
        length_function=len,
    )
    
    all_chunks = []
    
    for column_name, source_dir in SOURCE_DIRS.items():
        source_path = Path(source_dir)
        if not source_path.exists():
            print(f"⚠️ 目录不存在: {source_dir}")
            continue
        
        md_files = sorted(source_path.glob("*.md"))
        print(f"📂 {column_name}: 发现 {len(md_files)} 个文件")
        
        for order, md_file in enumerate(md_files):
            if md_file.name in ("index.md", "README.md"):
                continue
                
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception as e:
                print(f"❌ 读取失败 {md_file}: {e}")
                continue
            
            # 提取标题（第一行 # 标题）
            title_match = re.match(r"^#\s+(.+)$", content, re.MULTILINE)
            title = title_match.group(1) if title_match else md_file.stem
            
            # 切片
            chunks = splitter.split_text(content)
            
            for i, chunk_text in enumerate(chunks):
                if len(chunk_text.strip()) < 50:  # 过滤太短的片段
                    continue
                    
                chunk_id = hashlib.md5(f"{column_name}:{md_file.name}:{i}".encode()).hexdigest()[:12]
                
                all_chunks.append(DocumentChunk(
                    chunk_id=chunk_id,
                    source_column=column_name,
                    source_file=md_file.name,
                    file_order=order,
                    title=title,
                    content=chunk_text.strip(),
                    token_count=len(chunk_text) // 2,  # 粗略估算中文 token
                    metadata={
                        "column": column_name,
                        "file": md_file.name,
                        "order": order,
                        "chunk_index": i,
                        "title": title,
                    }
                ))
    
    return all_chunks

# ──────────────────────────────────────────────────────────────
# 向量化与索引构建
# ──────────────────────────────────────────────────────────────
def build_faiss_index(chunks: List[DocumentChunk]) -> tuple:
    """构建 FAISS 向量索引"""
    print(f"🔄 加载嵌入模型: {EMBED_MODEL}")
    model = SentenceTransformer(EMBED_MODEL)
    
    texts = [c.content for c in chunks]
    print(f"🔄 向量化 {len(texts)} 个文本块...")
    
    # 分批编码避免 OOM
    batch_size = 64
    embeddings = []
    for i in tqdm(range(0, len(texts), batch_size)):
        batch = texts[i:i+batch_size]
        emb = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
        embeddings.append(emb)
    
    embeddings = np.vstack(embeddings).astype("float32")
    
    # 构建 FAISS 索引 (内积相似度，已归一化)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    
    print(f"✅ FAISS 索引构建完成: {index.ntotal} 向量, 维度 {dim}")
    return index, embeddings, model

# ──────────────────────────────────────────────────────────────
# 保存结果
# ──────────────────────────────────────────────────────────────
def save_results(chunks: List[DocumentChunk], index, embeddings, model):
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    KG_DIR.mkdir(parents=True, exist_ok=True)
    
    # 保存 FAISS 索引
    faiss.write_index(index, str(VECTOR_DIR / "faiss_index.bin"))
    
    # 保存嵌入向量（备用）
    np.save(VECTOR_DIR / "embeddings.npy", embeddings)
    
    # 保存文档元数据
    chunks_data = [asdict(c) for c in chunks]
    with open(VECTOR_DIR / "chunks.jsonl", "w", encoding="utf-8") as f:
        for c in chunks_data:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    
    # 保存配置信息
    config = {
        "embed_model": EMBED_MODEL,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "total_chunks": len(chunks),
        "dimension": embeddings.shape[1],
        "source_columns": list(SOURCE_DIRS.keys()),
        "source_stats": {k: len([c for c in chunks if c.source_column == k]) for k in SOURCE_DIRS.keys()},
    }
    with open(VECTOR_DIR / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    # 保存模型（可选，避免重复下载）
    # model.save(str(VECTOR_DIR / "embed_model"))
    
    print(f"✅ 结果已保存至: {VECTOR_DIR}")
    print(f"   - faiss_index.bin")
    print(f"   - embeddings.npy")
    print(f"   - chunks.jsonl ({len(chunks)} 条)")
    print(f"   - config.json")

# ──────────────────────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("MySQL Agent 专栏 - 文档向量化构建")
    print("=" * 60)
    
    # 1. 加载并切片文档
    print("\n📖 步骤 1/3: 加载并切片文档...")
    chunks = load_markdown_files()
    print(f"✅ 共生成 {len(chunks)} 个文本块")
    
    # 统计信息
    for col in SOURCE_DIRS.keys():
        cnt = len([c for c in chunks if c.source_column == col])
        print(f"   - {col}: {cnt} 块")
    
    # 2. 向量化并构建索引
    print("\n🔢 步骤 2/3: 向量化并构建 FAISS 索引...")
    index, embeddings, model = build_faiss_index(chunks)
    
    # 3. 保存
    print("\n💾 步骤 3/3: 保存结果...")
    save_results(chunks, index, embeddings, model)
    
    print("\n🎉 完成！")
    print(f"向量索引目录: {VECTOR_DIR}")

if __name__ == "__main__":
    main()
