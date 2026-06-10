import sys
import types


def _install_fake_st(monkeypatch, vectors):
    """Stub sentence_transformers + numpy-free path so import stays cheap."""

    class _FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def encode(self, sentences):
            return [vectors[s] for s in sentences]

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = _FakeModel
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)


def test_cosine_identical_is_one(monkeypatch):
    _install_fake_st(monkeypatch, {"a": [1.0, 0.0], "b": [1.0, 0.0]})
    import importlib

    import dubai.text as text

    importlib.reload(text)
    assert text.cosine_similarity("a", "b") == 1.0


def test_cosine_orthogonal_is_zero(monkeypatch):
    _install_fake_st(monkeypatch, {"a": [1.0, 0.0], "b": [0.0, 1.0]})
    import importlib

    import dubai.text as text

    importlib.reload(text)
    assert text.cosine_similarity("a", "b") == 0.0
