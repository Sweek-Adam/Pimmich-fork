"""Photos oubliées : celles jamais ou rarement montrées reviennent plus souvent dans le diaporama."""
from utils import stats


def test_forgotten_photos_get_extra_turns():
    counts = {"a/vue.jpg": 40, "a/souvent.jpg": 35, "a/parfois.jpg": 20, "a/rare.jpg": 2, "a/encore.jpg": 30}
    paths = list(counts) + ["a/jamais.jpg"]
    extra = stats.forgotten_extra(paths, boost=2, counts=counts)
    assert extra["a/jamais.jpg"] == 2 and extra["a/rare.jpg"] == 1
    assert "a/vue.jpg" not in extra and "a/souvent.jpg" not in extra
    assert stats.forgotten_extra(paths, boost=0, counts=counts) == {}


def test_playlist_includes_extra_turns(monkeypatch, tmp_path):
    import local_slideshow as ls
    prepared = ls.PREPARED_BASE_DIR / "essai_oubli"
    media = [str(prepared / "vue.jpg"), str(prepared / "jamais.jpg")]
    monkeypatch.setattr(stats, "_load", lambda: {"photos": {"essai_oubli/vue.jpg": 10}})
    playlist = ls.build_playlist(media, {"favorite_boost_factor": 0}, [])
    assert playlist.count(media[1]) == 3 and playlist.count(media[0]) == 1
    assert ls.build_playlist(media, {"forgotten_boost_enabled": False}, []).count(media[1]) == 1
