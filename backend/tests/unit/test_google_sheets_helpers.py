from app.connectors.google_sheets import column_hash, unique_headers


def test_duplicate_headers_are_disambiguated() -> None:
    assert unique_headers(["Name", "Name", "Name"]) == ["Name", "Name_2", "Name_3"]


def test_blank_headers_get_positional_names() -> None:
    assert unique_headers(["Name", "", None]) == ["Name", "column_2", "column_3"]


def test_headers_are_trimmed() -> None:
    assert unique_headers(["  Amount  "]) == ["Amount"]


def test_column_hash_is_order_sensitive() -> None:
    assert column_hash(["a", "b"]) != column_hash(["b", "a"])


def test_column_hash_is_stable() -> None:
    assert column_hash(["a", "b"]) == column_hash(["a", "b"])
