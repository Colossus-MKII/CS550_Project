"""Resource-link presentation uses only completed local package manifests."""

import json

import pytest

from learning.team_downloads import ALLOWED, DIRECTORY, content, download_link, read_resources


def fixture_packages(tmp_path):
    folder = tmp_path / DIRECTORY
    folder.mkdir(parents=True)
    files = []
    for name in sorted(ALLOWED):
        (folder / name).write_bytes(b"file-link-test-fixture")
        files.append({"name": name, "bytes": 22, "sha256": "a" * 64})
    data = {"status": "ready", "files": files}
    (folder / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    return folder, data


def test_no_packages_means_no_advertised_downloads(tmp_path):
    assert read_resources(tmp_path) is None
    assert content(tmp_path, "en") == ""
    assert download_link(tmp_path, "zh") == ""


def test_changed_or_missing_package_is_not_advertised(tmp_path):
    folder, _ = fixture_packages(tmp_path)
    (folder / "pilot-data.zip").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed size"):
        read_resources(tmp_path)


def test_bilingual_contents_and_optional_full_dataset(tmp_path):
    _, data = fixture_packages(tmp_path)
    assert read_resources(tmp_path) == data
    for language in ("zh", "en"):
        page = content(tmp_path, language)
        for name in ALLOWED:
            assert f'href="{DIRECTORY}{name}"' in page
            assert f'download="{name}"' in page
        assert "SHA256SUMS.txt" in page
        assert "26.4 GiB" in page
    assert "documents.en.html#team-assets" in download_link(tmp_path, "en")
    assert "documents.html#team-assets" in download_link(tmp_path, "zh")
