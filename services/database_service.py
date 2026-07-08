# services/database_service.py
import json
import logging
from typing import List, Dict, Any, Optional
import services.sqlite_service as sqlite_service
from services.embedding_service import get_embedding

logger = logging.getLogger("database_service")

LANGUAGE_MAPPING = {
    "py": "python", "js": "javascript", "ts": "typescript", 
    "tsx": "typescript", "md": "markdown", "txt": "text", 
    "json": "json", "yaml": "yaml", "html": "html", "css": "css", 
    "java": "java", "go": "go", "rs": "rust"
}

# ── COUNTS ──────────────────────────────────────────────────────────
def get_file_count() -> int:
    return sqlite_service.get_file_count()

def get_chunk_count() -> int:
    return sqlite_service.get_chunk_count()

def get_query_count() -> int:
    return sqlite_service.get_query_count()

def get_storage_bytes() -> int:
    return sqlite_service.get_storage_bytes()

def get_storage_label() -> str:
    b = get_storage_bytes()
    return f'{b/1024/1024:.1f} MB' if b > 1024*1024 else f'{b/1024:.0f} KB'

# ── FILES ───────────────────────────────────────────────────────────
def get_all_files() -> List[Dict[str, Any]]:
    return sqlite_service.get_all_files()

def get_file_type_breakdown() -> Dict[str, int]:
    files = get_all_files()
    counts = {}
    for f in files:
        ft = f['file_type']
        counts[ft] = counts.get(ft, 0) + 1
    return counts

def get_language_breakdown() -> Dict[str, int]:
    files = get_all_files()
    counts = {}
    for f in files:
        lang = f['language'] or 'Unknown'
        counts[lang] = counts.get(lang, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1])[:10])

def delete_file(file_id: int):
    sqlite_service.delete_file(file_id)

def wipe_all():
    sqlite_service.wipe_all()

# ── QUERIES ─────────────────────────────────────────────────────────
def get_query_history(limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
    return sqlite_service.get_query_history(limit, offset)

def get_recent_queries(n: int = 5) -> List[Dict[str, Any]]:
    return sqlite_service.get_recent_queries(n)

def get_queries_today() -> int:
    return sqlite_service.get_queries_today()

def insert_query_log(question: str, plan: str, retrieved_files: List[str], answer: str, trace: Optional[List[Dict[str, Any]]] = None):
    payload = {
        'question': question, 
        'plan': plan,
        'retrieved_files': json.dumps(retrieved_files),
        'answer': answer,
    }
    if trace:
        payload['agent_trace'] = json.dumps(trace)
    sqlite_service.insert_query_log(payload)

def get_avg_files_per_query() -> float:
    return sqlite_service.get_avg_files_per_query()

# ── SEMANTIC SEARCH ─────────────────────────────────────────────────
def semantic_search(embedding: List[float], top_k: int = 8, file_type: Optional[str] = None) -> List[Dict[str, Any]]:
    return sqlite_service.semantic_search(embedding, top_k, file_type)

def search_chunks_vector(query: str, limit: int = 5, file_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    query_vector = get_embedding(query)
    if not query_vector:
        return []
        
    ft_filter = None
    if file_types and len(file_types) == 1:
        ft_filter = file_types[0]
        
    raw_results = semantic_search(query_vector, top_k=limit, file_type=ft_filter)
    
    mapped = []
    for r in raw_results:
        mapped.append({
            "content": r.get("content", ""),
            "filename": r.get("filename", ""),
            "file_type": r.get("file_type", "source_code"),
            "score": r.get("similarity", 0.0)
        })
    return mapped

# ── INGESTION OPERATIONS ─────────────────────────────────────────────
def get_file_content(file_id: int) -> Dict[str, Any]:
    return sqlite_service.get_file_content(file_id)

def chunk_text_by_lines(text: str, max_lines: int = 40, overlap_lines: int = 5) -> List[str]:
    lines = text.splitlines()
    chunks = []
    if not lines:
        return chunks
    i = 0
    while i < len(lines):
        chunk_lines = lines[i:i + max_lines]
        chunks.append("\n".join(chunk_lines))
        i += max_lines - overlap_lines
        if i >= len(lines):
            break
    return chunks

def save_file(filename: str, file_type: str, content: str, language: str, size_bytes: int) -> bool:
    file_id = sqlite_service.save_file(filename, file_type, content, language, size_bytes)
    if file_id is None:
        return False
        
    sqlite_service.clear_chunks(file_id)
    chunks = chunk_text_by_lines(content)
    for idx, chunk in enumerate(chunks):
        embedding_val = get_embedding(chunk)
        embedding_json = json.dumps(embedding_val) if embedding_val else None
        sqlite_service.insert_chunk(file_id, idx, chunk, embedding_json)
            
    return True

def insert_file_with_chunks(file_info: Dict[str, Any]) -> bool:
    path = file_info.get("path", "")
    content = file_info.get("content", "")
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="ignore")
        
    ext = path.split(".")[-1].lower() if "." in path else ""
    lang = LANGUAGE_MAPPING.get(ext, "text")
    
    if ext in ["md", "txt"]:
        db_type = "design_doc" if "design" in path.lower() or "architecture" in path.lower() else "api_doc"
    else:
        db_type = "source_code"
        
    return save_file(path, db_type, content, lang, len(content))

# ── COMPATIBILITY CLASS WRAPPER ─────────────────────────────────────
class DatabaseManager:
    """Compatibility class delegate for agent_orchestrator.py."""
    def __init__(self):
        pass

    def get_all_files(self) -> List[Dict[str, Any]]:
        return get_all_files()

    def search_files(self, keyword: str, file_types: List[str] = None) -> List[Dict[str, Any]]:
        files = self.get_all_files()
        results = []
        for f in files:
            if file_types and f["file_type"] not in file_types:
                continue
            if keyword.lower() in f["filename"].lower():
                content_file = get_file_content(f["id"])
                results.append({
                    "id": f["id"],
                    "filename": f["filename"],
                    "file_type": f["file_type"],
                    "language": f["language"],
                    "size_bytes": f["size_bytes"],
                    "content": content_file.get("content", "")
                })
        return results

    def search_chunks_vector(self, query: str, limit: int = 5, file_types: List[str] = None) -> List[Dict[str, Any]]:
        return search_chunks_vector(query, limit, file_types)

    def save_query(self, question: str, plan: str, retrieved_files: List[str], answer: str, agent_trace: Optional[List[Dict[str, Any]]] = None) -> bool:
        try:
            insert_query_log(question, plan, retrieved_files, answer, agent_trace)
            return True
        except Exception:
            return False

    def delete_file(self, file_id: Any) -> bool:
        delete_file(file_id)
        return True

    def get_file_content(self, file_id: Any) -> Dict[str, Any]:
        return get_file_content(file_id)

    def save_file(self, filename: str, file_type: str, content: str, language: str, size_bytes: int) -> bool:
        return save_file(filename, file_type, content, language, size_bytes)
