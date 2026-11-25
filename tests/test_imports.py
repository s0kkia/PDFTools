def test_core_modules_import():
    from pdftools.core import operations, repair, history
    assert callable(operations.merge_pdfs)
    assert callable(repair.repair_file)
    assert callable(history.HistoryStore)
