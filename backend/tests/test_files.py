from datetime import date

import pytest

from stillroom.files import FileError, clean_name, extract_text, next_available, relative_destination


def test_upload_name_and_text_rules(tmp_path):
    assert clean_name("../../private/notice.TXT") == ("notice.TXT", ".txt")
    assert extract_text(b"A sufficiently long UTF-8 document with useful words.", ".txt").startswith("A sufficiently")
    with pytest.raises(FileError):
        clean_name("payload.exe")
    with pytest.raises(FileError):
        extract_text(b"short", ".txt")


def test_destination_is_safe_and_collision_free(tmp_path):
    relative = relative_destination("Projects", "../../Launch: Plan?", date(2026, 10, 22), ".pdf")
    assert str(relative) == "2026/Projects/2026-10-22-launch-plan.pdf"
    first = next_available(tmp_path, relative)
    first.parent.mkdir(parents=True)
    first.write_bytes(b"first")
    second = next_available(tmp_path, relative)
    assert second.name == "2026-10-22-launch-plan-2.pdf"
