"""Row-major grouping: column-emitted words (FNB-class PDFs) must
reassemble into visual rows before any parser runs. No PII: words are
synthetic, shaped like the public sample's geometry."""

from apps.worker.parsers.extractor import _group_words_rows


def _w(x0, y0, text, block=0, line=0):
    return (x0, y0, x0 + 30, y0 + 10, text, block, line, 0)


def test_column_emission_rebuilds_rows():
    # Two visual rows; each column arrives as its own native line,
    # exactly how FNB's writer emits them.
    words = [
        _w(36, 100, "04", 0, 0), _w(52, 100, "Jul", 0, 0),
        _w(36, 114, "05", 0, 1), _w(52, 114, "Jul", 0, 1),
        _w(120, 100, "SPAR", 1, 0),
        _w(120, 114, "UBER", 1, 1),
        _w(400, 100, "206.69", 2, 0),
        _w(400, 114, "150.00", 2, 1),
        _w(470, 100, "3,193.31Cr", 3, 0),
        _w(470, 114, "3,043.31Cr", 3, 1),
    ]
    rows = _group_words_rows(words)
    assert len(rows) == 2
    assert rows[0]["text"] == "04 Jul SPAR 206.69 3,193.31Cr"
    assert rows[1]["text"] == "05 Jul UBER 150.00 3,043.31Cr"
    assert rows[0]["bbox"][0] == 36
    assert rows[0]["bbox"][2] == 500


def test_slight_y_jitter_stays_one_row():
    words = [
        _w(36, 100, "04", 0, 0), _w(52, 101, "Jul", 0, 0),
        _w(120, 99, "SPAR", 1, 0), _w(400, 102, "206.69", 2, 0),
    ]
    rows = _group_words_rows(words)
    assert len(rows) == 1
    assert rows[0]["text"] == "04 Jul SPAR 206.69"


def test_empty_words_empty_rows():
    assert _group_words_rows([]) == []
