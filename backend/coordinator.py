from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel
from typing import TypedDict, Optional, List
from datetime import datetime
import logging
import hashlib
import time
import os

logger = logging.getLogger(__name__)


class AlertSignal(BaseModel):
    type: str  # revenue_drop, churn, investor_contact, team_conflict, competitor_move
    confidence: float  # 0-1
    timestamp: datetime
    data: dict


class CoordinatorState(TypedDict):
    founder_id: str
    signals: List[AlertSignal]
    identified_decision: Optional[str]
    confidence_score: float
    what_happened: str
    why_it_matters: str
    what_to_do_next: str
    next_decision: str
    similar_past_decision: Optional[str]
    should_surface_alert: bool


class CoordinatorAgent:
    """Multi-agent coordinator for decision intelligence."""

    def __init__(self, memory_db=None):
        self.memory_db = memory_db
        # The model chain is built from env so a self-hosted founder can run on
        # their own cloud keys (default) OR a fully-local OpenAI-compatible
        # endpoint (vLLM / Ollama / LM Studio) where data never leaves the box.
        # See docs/llm-inference.md for the decision record.
        self.models = self._build_model_chain()
        self.embeddings = self._build_embeddings()

    def _build_model_chain(self):
        """Build the ordered (name, model) fallback chain from environment.

        LLM_MODE=cloud  (default): BYO Anthropic + OpenAI keys.
        LLM_MODE=local           : single OpenAI-compatible endpoint
                                   (LLM_LOCAL_BASE_URL) — nothing leaves the host.
        """
        mode = os.getenv("LLM_MODE", "cloud").lower()

        if mode == "local":
            base_url = os.getenv("LLM_LOCAL_BASE_URL", "http://localhost:11434/v1")
            model = os.getenv("LLM_LOCAL_MODEL", "llama3.1:70b")
            key = os.getenv("LLM_LOCAL_API_KEY", "local")
            local = ChatOpenAI(model=model, base_url=base_url, api_key=key, timeout=60)
            logger.info(f"LLM mode=local model={model} base_url={base_url}")
            return [("local", local)]

        # Cloud (BYO keys). Model ids overridable via env.
        primary = ChatAnthropic(model=os.getenv("LLM_PRIMARY_MODEL", "claude-3-5-sonnet-20241022"))
        secondary = ChatOpenAI(model=os.getenv("LLM_FALLBACK_MODEL", "gpt-4-turbo"))
        tertiary = ChatAnthropic(model=os.getenv("LLM_LAST_RESORT_MODEL", "claude-3-haiku-20240307"))
        logger.info("LLM mode=cloud (anthropic primary -> openai -> anthropic-haiku)")
        return [("primary", primary), ("fallback", secondary), ("last_resort", tertiary)]

    def _build_embeddings(self):
        """Embeddings provider — cloud OpenAI by default, or a local
        OpenAI-compatible embeddings endpoint when LLM_MODE=local."""
        if os.getenv("LLM_MODE", "cloud").lower() == "local":
            return OpenAIEmbeddings(
                model=os.getenv("LLM_LOCAL_EMBED_MODEL", "nomic-embed-text"),
                base_url=os.getenv("LLM_LOCAL_BASE_URL", "http://localhost:11434/v1"),
                api_key=os.getenv("LLM_LOCAL_API_KEY", "local"),
            )
        return OpenAIEmbeddings(model=os.getenv("LLM_EMBED_MODEL", "text-embedding-3-small"))

    def analyze_signals(self, state: CoordinatorState) -> CoordinatorState:
        """
        Analyze incoming signals and determine if alert should surface.
        Requires >= 2 INDEPENDENT signals for high confidence (doctrine edge
        case #2: revenue alone is not enough; needs corroboration).
        """
        signals = state["signals"]

        # Doctrine: require >= 2 signals from distinct sources/types to surface.
        unique_types = len({s.type for s in signals})
        if len(signals) < 2 or unique_types < 2:
            state["should_surface_alert"] = False
            logger.info(
                f"{len(signals)} signal(s) / {unique_types} type(s); need >=2 "
                f"distinct signals — suppressing (doctrine anti-noise rule)"
            )
            return state

        confidence = min(0.95, sum(s.confidence for s in signals) / len(signals))

        if confidence < 0.8:
            state["should_surface_alert"] = False
            logger.info(f"Confidence {confidence:.2f} < 0.8, suppressing alert")
            return state

        state["confidence_score"] = confidence
        state["should_surface_alert"] = True

        # Synthesize signal data into structured alert
        try:
            prompt = self._build_analysis_prompt(signals)
            llm_response = self._call_with_fallback(prompt)

            parsed = self._parse_llm_response(llm_response)
            state.update(parsed)

        except Exception as e:
            logger.error(f"Error analyzing signals: {e}")
            state["should_surface_alert"] = False

        return state

    def retrieve_historical_context(self, state: CoordinatorState) -> CoordinatorState:
        """Retrieve the most similar past decision from semantic memory (pgvector)."""
        if not state["should_surface_alert"] or not self.memory_db:
            return state

        try:
            from schema import SemanticMemory

            # Embed the alert context and rank stored decisions by cosine distance.
            embedding = self._embed_decision_context(state["what_happened"])

            similar = (
                self.memory_db.query(SemanticMemory)
                .filter(
                    SemanticMemory.founder_id == state["founder_id"],
                    SemanticMemory.content_type == "decision",
                )
                .order_by(SemanticMemory.embedding.cosine_distance(embedding))
                .limit(1)
                .all()
            )

            if similar:
                state["similar_past_decision"] = similar[0].content

        except Exception as e:
            logger.warning(f"Failed to retrieve historical context: {e}")

        return state

    def _build_analysis_prompt(self, signals: List[AlertSignal]) -> str:
        """Build prompt for LLM to synthesize signals."""
        signal_summary = "\n".join([
            f"- {s.type} (confidence: {s.confidence:.2f})\n  Data: {s.data}"
            for s in signals
        ])

        return f"""You are analyzing multiple signals to determine if a founder needs an urgent decision alert.

Signals received:
{signal_summary}

Synthesize these signals into a structured alert with:
1. WHAT_HAPPENED: Concise summary of what the data shows
2. WHY_IT_MATTERS: Business impact (loss, risk, opportunity)
3. WHAT_TO_DO_NEXT: Numbered action steps
4. NEXT_DECISION: The key decision the founder needs to make

Format your response as:
WHAT_HAPPENED: [text]
WHY_IT_MATTERS: [text]
WHAT_TO_DO_NEXT: [numbered list]
NEXT_DECISION: [decision]
"""

    def _call_with_fallback(self, prompt: str, max_retries: int = 3) -> str:
        """Call LLM with exponential backoff and circular fallback.

        Tries each model in turn; for each, retries up to `max_retries` with
        exponential backoff before failing over to the next model. Backoff is
        bounded so total latency stays predictable (doctrine: graceful
        degradation under model failure). The chain comes from self.models,
        built per-deployment from env (cloud BYO keys or local endpoint).
        """
        for model_name, model in self.models:
            for attempt in range(max_retries):
                try:
                    response = model.invoke(prompt)
                    logger.info(f"LLM response from {model_name} (attempt {attempt + 1})")
                    return response.content
                except Exception as e:
                    backoff = min(2 ** attempt, 8)  # 1s, 2s, 4s ... capped at 8s
                    logger.warning(
                        f"{model_name} failed ({e}); attempt {attempt + 1}/{max_retries}, "
                        f"backoff {backoff}s"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(backoff)
            logger.warning(f"{model_name} exhausted retries, failing over")

        logger.error("All LLM models failed")
        raise Exception("All LLM models exhausted")

    def _parse_llm_response(self, response_text: str) -> dict:
        """Parse structured LLM response."""
        lines = response_text.split("\n")
        parsed = {
            "what_happened": "",
            "why_it_matters": "",
            "what_to_do_next": "",
            "next_decision": ""
        }

        current_section = None
        for line in lines:
            if line.startswith("WHAT_HAPPENED:"):
                current_section = "what_happened"
                parsed[current_section] = line.replace("WHAT_HAPPENED:", "").strip()
            elif line.startswith("WHY_IT_MATTERS:"):
                current_section = "why_it_matters"
                parsed[current_section] = line.replace("WHY_IT_MATTERS:", "").strip()
            elif line.startswith("WHAT_TO_DO_NEXT:"):
                current_section = "what_to_do_next"
                parsed[current_section] = line.replace("WHAT_TO_DO_NEXT:", "").strip()
            elif line.startswith("NEXT_DECISION:"):
                current_section = "next_decision"
                parsed[current_section] = line.replace("NEXT_DECISION:", "").strip()
            elif current_section and line.strip():
                parsed[current_section] += "\n" + line

        return parsed

    def _embed_decision_context(self, text: str) -> list:
        """Generate embedding for semantic memory search using OpenAI."""
        try:
            return self.embeddings.embed_query(text)
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            # Deterministic fallback so semantic search still returns *something*
            # rather than crashing the alert pipeline.
            digest = hashlib.sha256(text.encode()).digest()
            base = [float(b) / 255.0 for b in digest]  # 32 values
            return (base * 48)[:1536]  # tile up to the 1536-dim vector size

    def build_graph(self):
        """Build LangGraph workflow."""
        graph = StateGraph(CoordinatorState)

        graph.add_node("analyze_signals", self.analyze_signals)
        graph.add_node("retrieve_context", self.retrieve_historical_context)
        graph.add_node("finalize_alert", lambda s: s)  # Noop, alert is ready

        graph.set_entry_point("analyze_signals")
        graph.add_edge("analyze_signals", "retrieve_context")
        graph.add_edge("retrieve_context", "finalize_alert")
        graph.add_edge("finalize_alert", END)

        return graph.compile()
