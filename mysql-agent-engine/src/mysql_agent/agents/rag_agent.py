"""
Simple RAG Agent for MySQL performance analysis.
Uses vector index + LLM for grounded Q&A.
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ..vectorstore import FAISSIndex, Embedder
from ..vectorstore.hybrid_search import HybridSearcher
from ..prompts import PromptBuilder


@dataclass
class RAGResult:
    """Result from RAG query."""
    question: str
    answer: str
    sources: List[Dict[str, Any]]
    confidence: float


class MySQLRAGAgent:
    """
    RAG Agent for MySQL performance analysis.
    Retrieves relevant documentation chunks and synthesizes answers.
    """
    
    def __init__(
        self,
        index_path: str,
        top_k: int = 5,
        min_score: float = 0.1,
        quiet: bool = False,
        use_hybrid: bool = True,
        llm_client: Optional[object] = None,
        prompt_builder: Optional[PromptBuilder] = None,
    ):
        self.index_path = Path(index_path)
        self.top_k = top_k
        self.min_score = min_score
        self.quiet = quiet
        self.use_hybrid = use_hybrid
        self.llm = llm_client
        self.prompt_builder = prompt_builder or PromptBuilder()
        
        if not quiet:
            print(f"🔄 Loading index from {index_path}")
        self.index = FAISSIndex.load(index_path)
        self.embedder = Embedder.load(index_path)
        self.hybrid = HybridSearcher(self.index, self.embedder) if use_hybrid else None
        if not quiet:
            print("✅ Agent ready")
    
    def expand_query(self, question: str) -> str:
        """Expand Chinese/English mixed queries for better recall."""
        extras: List[str] = []
        lowered = question.lower()
        if "死锁" in question:
            extras.extend(["deadlock", "innodb", "lock", "死锁检测"])
        if "buffer" in lowered or "buffer_pool" in lowered or "buffer pool" in lowered:
            extras.extend(["innodb_buffer_pool_size", "buffer pool"])
        if "1205" in question or "lock wait" in lowered:
            extras.extend(["innodb lock", "lock wait timeout"])
        if not extras:
            return question
        return f"{question} {' '.join(extras)}"

    def retrieve(self, question: str, k: Optional[int] = None) -> List[tuple]:
        """Retrieve relevant chunks for a question."""
        k = k or self.top_k
        search_query = self.expand_query(question)
        if self.hybrid is not None:
            results = self.hybrid.search(search_query, k=k)
        else:
            results = self.index.search_by_text(search_query, self.embedder, k=k)
        return [(c, s) for c, s in results if s >= self.min_score]
    
    def format_context(self, chunks: List[tuple]) -> str:
        """Format retrieved chunks into context string."""
        if not chunks:
            return "无相关文档。"
        
        lines = []
        for i, (chunk, score) in enumerate(chunks, 1):
            lines.append(f"[文档 {i}] 来源: {chunk.source_column}/{chunk.source_file}")
            lines.append(f"标题: {chunk.title}")
            lines.append(f"相关度: {score:.3f}")
            lines.append(f"内容: {chunk.content[:500]}...")
            lines.append("---")
        
        return "\n".join(lines)
    
    def build_prompt(self, question: str, context: str) -> str:
        """Build prompt for LLM synthesis."""
        return self.prompt_builder.render("rag_qa", context=context, question=question)
    
    def query(self, question: str) -> RAGResult:
        """Query the agent with a question."""
        # Retrieve relevant chunks
        chunks = self.retrieve(question)
        
        # Format context
        context = self.format_context(chunks)
        
        # Build prompt and synthesize answer
        prompt = self.build_prompt(question, context)
        
        sources = [
            {
                "chunk_id": getattr(c, "chunk_id", ""),
                "column": c.source_column,
                "file": c.source_file,
                "title": c.title,
                "score": float(s),
                "snippet": c.content[:200],
            }
            for c, s in chunks
        ]
        
        if self.llm is not None and hasattr(self.llm, "complete"):
            try:
                answer = self.llm.complete(prompt)
            except Exception:
                answer = self._heuristic_answer(chunks)
        else:
            answer = self._heuristic_answer(chunks)
        
        confidence = chunks[0][1] if chunks else 0.0
        
        return RAGResult(
            question=question,
            answer=answer,
            sources=sources,
            confidence=confidence,
        )

    def _heuristic_answer(self, chunks: List[tuple]) -> str:
        if not chunks:
            return "未找到相关文档，建议尝试其他关键词。"
        top_chunk = chunks[0][0]
        return (
            f"根据《{top_chunk.title}》（{top_chunk.source_column}），"
            f"{top_chunk.content[:300]}..."
        )
    
    def interactive(self):
        """Run interactive Q&A session."""
        print("\n" + "=" * 60)
        print("MySQL RAG Agent - 交互式问答")
        print("输入 'quit' 或 'exit' 退出")
        print("=" * 60)
        
        while True:
            try:
                question = input("\n❓ 问题: ").strip()
                if question.lower() in ('quit', 'exit', 'q', '退出'):
                    print("👋 再见！")
                    break
                
                if not question:
                    continue
                
                result = self.query(question)
                
                print(f"\n📝 回答 (置信度: {result.confidence:.2f}):")
                print(result.answer)
                
                if result.sources:
                    print("\n📚 参考来源:")
                    for i, src in enumerate(result.sources, 1):
                        print(f"  {i}. [{src['column']}] {src['title']} (相关度: {src['score']:.3f})")
                
            except KeyboardInterrupt:
                print("\n👋 再见！")
                break
            except EOFError:
                break


def main():
    import argparse
    parser = argparse.ArgumentParser(description="MySQL RAG Agent")
    parser.add_argument("index_path", help="Path to vector index directory")
    parser.add_argument("--question", "-q", help="Single question to ask")
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve")
    
    args = parser.parse_args()
    
    agent = MySQLRAGAgent(args.index_path, top_k=args.top_k)
    
    if args.question:
        result = agent.query(args.question)
        print(f"Q: {result.question}")
        print(f"A: {result.answer}")
        print(f"Confidence: {result.confidence:.2f}")
        for src in result.sources:
            print(f"  - [{src['column']}] {src['title']} ({src['score']:.3f})")
    else:
        agent.interactive()


if __name__ == "__main__":
    main()
