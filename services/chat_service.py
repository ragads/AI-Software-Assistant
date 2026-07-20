# services/chat_service.py
import logging
from typing import List, Dict, Any
import services.database_service as database_service
import services.sqlite_service as sqlite_service
import services.llm_service as llm_service

logger = logging.getLogger("chat_service")

SYSTEM_PROMPT = """You are RepoLens AI Assistant, a powerful software architect assistant.
You are helping the user understand and navigate their codebase.
Analyze the provided code chunks retrieved from the database to answer the user's question.
If the retrieved code chunks do not contain enough information to answer, state that clearly.
Always be concise, precise, and professional. Use markdown code snippets for code blocks."""

def ask_question(question: str) -> str:
    """Retrieves relevant code chunks and generates a response using the configured LLM."""
    try:
        # Retrieve context
        if llm_service.embeddings_available():
            chunks = database_service.search_chunks_vector(question, limit=6)
        else:
            chunks = sqlite_service.keyword_search_chunks(question, limit=6)

        if not chunks:
            # Try to get overall file list to see if database has any files
            files = database_service.get_all_files()
            if not files:
                return "The workspace is empty. Please ingest a GitHub repository first."
            return "I couldn't find any relevant code segments in the index for your question. Try using different keywords."

        # Format context
        context_parts = []
        retrieved_files = set()
        for idx, chunk in enumerate(chunks):
            filename = chunk.get("filename", "unknown")
            content = chunk.get("content", "")
            retrieved_files.add(filename)
            context_parts.append(f"--- Chunk {idx+1} from {filename} ---\n{content}\n")

        context = "\n".join(context_parts)

        prompt = f"""Use the following codebase chunks as context to answer the question:

{context}

Question: {question}
Answer:"""

        # Log query to database
        answer = llm_service.generate(SYSTEM_PROMPT, prompt)
        
        try:
            database_service.insert_query_log(
                question=question,
                plan="RAG retrieval",
                retrieved_files=list(retrieved_files),
                answer=answer
            )
        except Exception as log_ex:
            logger.warning(f"Failed to insert query log: {log_ex}")

        return answer

    except Exception as e:
        logger.error(f"Chat service error: {e}")
        return f"An error occurred while generating the answer: {e}"
