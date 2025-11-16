"""Semantic search using sentence embeddings.

Provides meaning-based search using transformer models and FAISS.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import faiss
    from sentence_transformers import SentenceTransformer
    from sklearn.cluster import KMeans

    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False

from podx.domain.models.transcript import Transcript


class SemanticSearch:
    """Semantic search using sentence embeddings and FAISS."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        index_path: Optional[Path] = None,
    ) -> None:
        """Initialize semantic search.

        Args:
            model_name: SentenceTransformer model name
            index_path: Path to store FAISS index and metadata.
                       Defaults to ~/.podx/semantic_index/

        Raises:
            ImportError: If sentence-transformers or faiss-cpu not installed
        """
        if not SEMANTIC_AVAILABLE:
            raise ImportError(
                "Semantic search requires: pip install sentence-transformers faiss-cpu"
            )

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

        # Set up index directory
        if index_path is None:
            index_path = Path.home() / ".podx" / "semantic_index"
        index_path.mkdir(parents=True, exist_ok=True)
        self.index_path = index_path

        # Initialize or load index
        self.index: Optional[faiss.Index] = None
        self.segments: List[Dict[str, Any]] = []
        self._load_index()

    def _load_index(self) -> None:
        """Load existing FAISS index and metadata."""
        index_file = self.index_path / "faiss.index"
        metadata_file = self.index_path / "metadata.pkl"

        if index_file.exists() and metadata_file.exists():
            self.index = faiss.read_index(str(index_file))
            with open(metadata_file, "rb") as f:
                self.segments = pickle.load(f)
        else:
            # Create new index (384 dimensions for all-MiniLM-L6-v2)
            self.index = faiss.IndexFlatL2(384)
            self.segments = []

    def _save_index(self) -> None:
        """Save FAISS index and metadata."""
        index_file = self.index_path / "faiss.index"
        metadata_file = self.index_path / "metadata.pkl"

        faiss.write_index(self.index, str(index_file))
        with open(metadata_file, "wb") as f:
            pickle.dump(self.segments, f)

    def index_transcript(
        self,
        episode_id: str,
        transcript: Transcript,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Index a transcript for semantic search.

        Args:
            episode_id: Unique episode identifier
            transcript: Transcript to index
            metadata: Optional episode metadata
        """
        # Remove existing segments for this episode
        self.segments = [s for s in self.segments if s["episode_id"] != episode_id]

        # Rebuild index from scratch (simpler than incremental updates)
        texts = []
        new_segments = []

        # Add existing segments
        for seg in self.segments:
            texts.append(seg["text"])

        # Add new segments
        for segment in transcript.segments:
            text = segment.text
            texts.append(text)

            seg_data = {
                "episode_id": episode_id,
                "speaker": segment.speaker or "Unknown",
                "text": text,
                "timestamp": segment.start,
                "metadata": metadata or {},
            }
            new_segments.append(seg_data)

        # Update segments list
        self.segments.extend(new_segments)

        # Re-encode all texts
        if texts:
            embeddings = self.model.encode(texts, show_progress_bar=False)
            embeddings = np.array(embeddings).astype("float32")

            # Create new index
            self.index = faiss.IndexFlatL2(embeddings.shape[1])
            self.index.add(embeddings)

            self._save_index()

    def search(
        self,
        query: str,
        k: int = 10,
        episode_filter: Optional[str] = None,
        speaker_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic search for similar segments.

        Args:
            query: Search query
            k: Number of results to return
            episode_filter: Filter by episode ID (optional)
            speaker_filter: Filter by speaker name (optional)

        Returns:
            List of matching segments with similarity scores
        """
        if self.index is None or self.index.ntotal == 0:
            return []

        # Encode query
        query_embedding = self.model.encode([query], show_progress_bar=False)
        query_embedding = np.array(query_embedding).astype("float32")

        # Search FAISS index (get more results for filtering)
        search_k = min(k * 10, self.index.ntotal)
        distances, indices = self.index.search(query_embedding, search_k)

        # Collect results with filtering
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx >= len(self.segments):
                continue

            segment = self.segments[idx]

            # Apply filters
            if episode_filter and segment["episode_id"] != episode_filter:
                continue
            if speaker_filter and speaker_filter not in segment["speaker"]:
                continue

            # Convert L2 distance to similarity score (0-1, higher is better)
            similarity = 1.0 / (1.0 + float(dist))

            results.append(
                {
                    "episode_id": segment["episode_id"],
                    "speaker": segment["speaker"],
                    "text": segment["text"],
                    "timestamp": segment["timestamp"],
                    "similarity": similarity,
                    "metadata": segment.get("metadata", {}),
                }
            )

            if len(results) >= k:
                break

        return results

    def find_similar_segments(
        self, episode_id: str, timestamp: float, k: int = 5
    ) -> List[Dict[str, Any]]:
        """Find segments similar to a given segment.

        Args:
            episode_id: Episode ID
            timestamp: Timestamp of reference segment
            k: Number of similar segments to return

        Returns:
            List of similar segments
        """
        # Find the reference segment
        ref_segment = None
        ref_idx = None
        for i, seg in enumerate(self.segments):
            if seg["episode_id"] == episode_id and abs(seg["timestamp"] - timestamp) < 1.0:
                ref_segment = seg
                ref_idx = i
                break

        if ref_segment is None or ref_idx is None:
            return []

        # Get embedding for reference segment
        if self.index is None or ref_idx >= self.index.ntotal:
            return []

        # Create query from reference embedding
        ref_embedding = self.index.reconstruct(ref_idx).reshape(1, -1)

        # Search for similar segments
        distances, indices = self.index.search(ref_embedding, k + 1)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == ref_idx:  # Skip self
                continue
            if idx >= len(self.segments):
                continue

            segment = self.segments[idx]
            similarity = 1.0 / (1.0 + float(dist))

            results.append(
                {
                    "episode_id": segment["episode_id"],
                    "speaker": segment["speaker"],
                    "text": segment["text"],
                    "timestamp": segment["timestamp"],
                    "similarity": similarity,
                }
            )

        return results[:k]

    def cluster_topics(
        self, n_clusters: int = 10, episode_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Cluster segments into topics using K-means.

        Args:
            n_clusters: Number of topic clusters
            episode_filter: Filter by episode ID (optional)

        Returns:
            List of clusters with representative segments
        """
        if self.index is None or self.index.ntotal == 0:
            return []

        # Filter segments
        filtered_segments = self.segments
        if episode_filter:
            filtered_segments = [
                s for s in self.segments if s["episode_id"] == episode_filter
            ]

        if len(filtered_segments) < n_clusters:
            n_clusters = max(1, len(filtered_segments) // 2)

        # Get embeddings for filtered segments
        indices = [i for i, s in enumerate(self.segments) if s in filtered_segments]
        embeddings = np.array([self.index.reconstruct(i) for i in indices])

        # Cluster with K-means
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        labels = kmeans.fit_predict(embeddings)

        # Build cluster results
        clusters = []
        for cluster_id in range(n_clusters):
            cluster_indices = [i for i, label in enumerate(labels) if label == cluster_id]
            cluster_segments = [filtered_segments[i] for i in cluster_indices]

            # Find representative segment (closest to centroid)
            centroid = kmeans.cluster_centers_[cluster_id]
            cluster_embeddings = embeddings[cluster_indices]
            distances = np.linalg.norm(cluster_embeddings - centroid, axis=1)
            representative_idx = np.argmin(distances)

            clusters.append(
                {
                    "cluster_id": cluster_id,
                    "size": len(cluster_segments),
                    "representative": cluster_segments[representative_idx],
                    "segments": cluster_segments,
                }
            )

        # Sort by cluster size (largest first)
        clusters.sort(key=lambda x: x["size"], reverse=True)

        return clusters

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics.

        Returns:
            Dict with index size, model info, etc.
        """
        return {
            "model": self.model_name,
            "indexed_segments": len(self.segments),
            "index_size": self.index.ntotal if self.index else 0,
            "embedding_dim": self.index.d if self.index else 0,
        }
