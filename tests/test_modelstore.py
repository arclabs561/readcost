"""The first-run model download: checksum, safe unpacking, cache use, opt-out."""

import zipfile

import pytest

from readcost import modelstore


def make_wheel(path, members):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def test_install_rejects_a_wrong_checksum(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    wheel = make_wheel(tmp_path / "m.whl", {modelstore.PREFIX + "config.cfg": "x"})
    with pytest.raises(ValueError, match="SHA-256"):
        modelstore.install(wheel)
    assert modelstore.cached_path() is None


def test_extract_takes_only_the_model_directory(tmp_path):
    wheel = make_wheel(tmp_path / "m.whl", {
        modelstore.PREFIX + "config.cfg": "cfg",
        modelstore.PREFIX + "tagger/model": "weights",
        "en_core_web_sm/__init__.py": "code",
        "en_core_web_sm-3.8.0.dist-info/METADATA": "meta",
    })
    dest = tmp_path / "out"
    dest.mkdir()
    modelstore._extract(wheel, dest)
    files = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    assert files == ["config.cfg", "tagger/model"]


def test_extract_refuses_path_traversal(tmp_path):
    wheel = make_wheel(tmp_path / "m.whl", {modelstore.PREFIX + "../../evil": "x",
                                            modelstore.PREFIX + "config.cfg": "cfg"})
    dest = tmp_path / "out"
    dest.mkdir()
    with pytest.raises(ValueError, match="unexpected path"):
        modelstore._extract(wheel, dest)
    assert not (tmp_path / "evil").exists()


def test_install_puts_a_verified_wheel_in_the_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    wheel = make_wheel(tmp_path / "m.whl", {modelstore.PREFIX + "config.cfg": "cfg"})
    import hashlib

    monkeypatch.setattr(modelstore, "SHA256", hashlib.sha256(wheel.read_bytes()).hexdigest())
    path = modelstore.install(wheel)
    assert path == modelstore.cached_path()
    assert (path / "config.cfg").read_text() == "cfg"
    assert not list(path.parent.glob(".partial-*"))  # no staging directory left behind


def test_load_falls_back_to_the_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    cached = modelstore.cache_dir() / f"{modelstore.MODEL}-{modelstore.VERSION}"
    cached.mkdir(parents=True)
    (cached / "config.cfg").write_text("cfg")
    import spacy

    def fake_load(name, **kw):
        if name == modelstore.MODEL:
            raise OSError("not installed")
        return ("loaded", name)

    monkeypatch.setattr(spacy, "load", fake_load)
    assert modelstore.load() == ("loaded", cached)


def test_no_download_opt_out(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("READCOST_NO_DOWNLOAD", "1")
    with pytest.raises(OSError, match="READCOST_NO_DOWNLOAD"):
        modelstore.fetch()


def test_other_models_are_not_fetched(monkeypatch):
    import spacy

    monkeypatch.setattr(spacy, "load", lambda name, **kw: (_ for _ in ()).throw(OSError("missing")))
    with pytest.raises(OSError):
        modelstore.load("en_core_web_trf")
