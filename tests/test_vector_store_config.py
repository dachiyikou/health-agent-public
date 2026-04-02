from health_agent import config
from health_agent.tools.vector_store import VectorStoreClient


def test_embedding_dim_matches_qwen_default():
    assert config.EMBEDDING_DIM == 1024


def test_existing_collection_dimension_is_valid():
    client = VectorStoreClient(base_url="http://example.com", api_key="test-key")

    assert client._collection_dimension_matches(
        {"result": {"config": {"params": {"vectors": {"size": 1024}}}}}
    )
    assert not client._collection_dimension_matches(
        {"result": {"config": {"params": {"vectors": {"size": 1536}}}}}
    )
