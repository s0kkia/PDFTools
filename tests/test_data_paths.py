from pdftools.services.data_paths import data_dir, set_storage_mode

def test_data_dir_creates_appdata_default(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    set_storage_mode("appdata")
    path = data_dir("database")
    assert path.exists()
    assert path.name == "database"

def test_invalid_storage_mode_rejected():
    try:
        set_storage_mode("invalid")
    except ValueError:
        return
    raise AssertionError("invalid storage mode must raise ValueError")
