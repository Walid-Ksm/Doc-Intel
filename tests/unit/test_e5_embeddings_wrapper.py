from unittest.mock import MagicMock
from app.infrastructure.langchain.e5_embeddings import E5EmbeddingsWrapper


def _make_wrapper():
    """Build an E5EmbeddingsWrapper with a mock model, return both."""
    mock_model = MagicMock()
    # embed_documents returns a list of vectors (one per input text)
    mock_model.embed_documents.return_value = [[0.1] * 384]
    # embed_query returns a single vector
    mock_model.embed_query.return_value = [0.2] * 384
    wrapper = E5EmbeddingsWrapper(model=mock_model)
    return wrapper, mock_model


def test_e5_wrapper_prefixes_passages_correctly():
    wrapper, mock_model = _make_wrapper()

    wrapper.embed_passages(["some document text"])

    # Assert the string that actually reached the underlying model
    received_texts = mock_model.embed_documents.call_args[0][0]
    assert len(received_texts) == 1
    assert received_texts[0].startswith("passage: "), (
        f"Expected prefix 'passage: ' but got: {received_texts[0]!r}"
    )
    assert received_texts[0] == "passage: some document text"


def test_e5_wrapper_prefixes_query_correctly():
    wrapper, mock_model = _make_wrapper()

    wrapper.embed_query("what is the revenue?")

    received_text = mock_model.embed_query.call_args[0][0]
    assert received_text.startswith("query: "), (
        f"Expected prefix 'query: ' but got: {received_text!r}"
    )
    assert received_text == "query: what is the revenue?"


def test_e5_wrapper_does_not_store_prefix_in_output():
    wrapper, mock_model = _make_wrapper()

    result = wrapper.embed_passages(["some text"])

    # Return value must be a list of float vectors, not prefixed strings
    assert isinstance(result, list)
    assert isinstance(result[0], list)
    assert isinstance(result[0][0], float)


def test_e5_wrapper_batches_all_passages_in_one_call():
    wrapper, mock_model = _make_wrapper()
    mock_model.embed_documents.return_value = [[0.1] * 384, [0.2] * 384, [0.3] * 384]

    wrapper.embed_passages(["text one", "text two", "text three"])

    # embed_documents must be called once with all three texts, not three times
    mock_model.embed_documents.assert_called_once()
    received_texts = mock_model.embed_documents.call_args[0][0]
    assert len(received_texts) == 3
    assert all(t.startswith("passage: ") for t in received_texts)
