import datetime
import random
import time
import uuid

import polars as pl
import pytest

import polars_uuid


def test_version():
    assert isinstance(polars_uuid.__version__, str)


def test_uuid4_produces_valid_v4_uuids():
    df = pl.DataFrame({"a": [1, 2, 3]})
    result = df.with_columns(polars_uuid.uuid4("a").alias("id"))
    ids = [uuid.UUID(v) for v in result["id"]]
    assert all(u.version == 4 for u in ids)


def test_uuid4_is_random_per_row():
    df = pl.DataFrame({"a": [1, 2, 3]})
    result = df.with_columns(polars_uuid.uuid4("a").alias("id"))
    assert result["id"].n_unique() == 3


def test_uuid7_produces_valid_v7_uuids():
    df = pl.DataFrame({"a": [1, 2, 3]})
    result = df.with_columns(polars_uuid.uuid7("a").alias("id"))
    ids = [uuid.UUID(v) for v in result["id"]]
    assert all(u.version == 7 for u in ids)


def test_uuid7_is_random_per_row():
    df = pl.DataFrame({"a": [1, 2, 3]})
    result = df.with_columns(polars_uuid.uuid7("a").alias("id"))
    assert result["id"].n_unique() == 3


def test_uuid7_is_time_ordered_across_batches():
    df = pl.DataFrame({"a": [1]})
    first = df.with_columns(polars_uuid.uuid7("a").alias("id"))["id"][0]
    time.sleep(0.01)
    second = df.with_columns(polars_uuid.uuid7("a").alias("id"))["id"][0]
    assert first < second


def test_uuid7_on_empty_input():
    df = pl.DataFrame({"name": []}, schema={"name": pl.String})
    result = df.with_columns(polars_uuid.uuid7("name").alias("id"))
    assert result["id"].to_list() == []


def test_uuid5_matches_published_reference_value():
    # Worked example from the Python standard library docs:
    # https://docs.python.org/3/library/uuid.html#uuid.uuid5
    df = pl.DataFrame({"name": ["python.org"]})
    result = df.with_columns(
        polars_uuid.uuid5("name", namespace=uuid.NAMESPACE_DNS).alias("id")
    )
    assert result["id"][0] == "886313e1-3b8a-5372-9b90-0c9aee199e5d"


def test_uuid5_matches_stdlib_sweep():
    """`uuid5` must be byte-identical to `uuid.uuid5` for the same input.

    This is the property that makes `uuid5` usable for ids that need to match
    ones built elsewhere with Python's stdlib. Covers a seeded random sweep
    (including multi-byte UTF-8, to catch an implementation that hashes
    something other than the raw UTF-8 bytes) plus explicit edge cases.
    """
    rng = random.Random(0)
    alphabet = "0123456789abcdef|-_ é日🎲"
    names = ["".join(rng.choices(alphabet, k=rng.randint(0, 40))) for _ in range(2000)]
    names += [
        "",
        "|",
        "|||",
        " ",
        "0",
        "00",
        "x" * 4096,
        "nan",
        "None",
        "NaT",
        "null",
    ]

    expected = [str(uuid.uuid5(uuid.NAMESPACE_DNS, name)) for name in names]
    actual = (
        pl.DataFrame({"name": names})
        .select(polars_uuid.uuid5("name", namespace=uuid.NAMESPACE_DNS).alias("u"))
        .to_series()
        .to_list()
    )
    assert actual == expected


def test_uuid5_is_deterministic():
    df = pl.DataFrame({"name": ["example.com", "example.org"]})
    result = df.with_columns(
        polars_uuid.uuid5("name", namespace=uuid.NAMESPACE_DNS).alias("id")
    )
    expected = [
        str(uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")),
        str(uuid.uuid5(uuid.NAMESPACE_DNS, "example.org")),
    ]
    assert result["id"].to_list() == expected


def test_uuid5_accepts_string_namespace():
    df = pl.DataFrame({"name": ["example.com"]})
    result = df.with_columns(
        polars_uuid.uuid5("name", namespace=str(uuid.NAMESPACE_DNS)).alias("id")
    )
    assert result["id"][0] == str(uuid.uuid5(uuid.NAMESPACE_DNS, "example.com"))


def test_uuid5_rejects_invalid_namespace():
    df = pl.DataFrame({"name": ["example.com"]})
    with pytest.raises(pl.exceptions.ComputeError):
        df.with_columns(polars_uuid.uuid5("name", namespace="not-a-uuid").alias("id"))


def test_uuid5_propagates_nulls():
    df = pl.DataFrame({"name": ["example.com", None, "example.org"]})
    result = df.with_columns(
        polars_uuid.uuid5("name", namespace=uuid.NAMESPACE_DNS).alias("id")
    )
    assert result["id"].to_list() == [
        str(uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")),
        None,
        str(uuid.uuid5(uuid.NAMESPACE_DNS, "example.org")),
    ]


def test_uuid4_on_empty_input():
    df = pl.DataFrame({"name": []}, schema={"name": pl.String})
    result = df.with_columns(polars_uuid.uuid4("name").alias("id"))
    assert result["id"].to_list() == []


def test_uuid5_on_empty_input():
    df = pl.DataFrame({"name": []}, schema={"name": pl.String})
    result = df.with_columns(
        polars_uuid.uuid5("name", namespace=uuid.NAMESPACE_DNS).alias("id")
    )
    assert result["id"].to_list() == []


def test_uuid5_works_in_lazy_context():
    lf = pl.LazyFrame({"name": ["example.com", "example.org"]})
    result = lf.with_columns(
        polars_uuid.uuid5("name", namespace=uuid.NAMESPACE_DNS).alias("id")
    ).collect()
    assert result["id"].to_list() == [
        str(uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")),
        str(uuid.uuid5(uuid.NAMESPACE_DNS, "example.org")),
    ]


def test_is_valid_uuid():
    df = pl.DataFrame(
        {"id": [str(uuid.uuid4()), "not-a-uuid", None]},
    )
    result = df.with_columns(polars_uuid.is_valid_uuid("id").alias("valid"))
    assert result["valid"].to_list() == [True, False, None]


def test_uuid_version():
    df = pl.DataFrame(
        {
            "id": [
                str(uuid.uuid4()),
                str(uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")),
                "not-a-uuid",
                None,
            ]
        }
    )
    result = df.with_columns(polars_uuid.uuid_version("id").alias("version"))
    assert result["version"].to_list() == [4, 5, None, None]


def test_extract_timestamp_from_known_v7_uuid():
    # Hand-built v7 UUID whose first 48 bits are the millisecond timestamp for
    # 2023-11-14T22:13:20 UTC (1_700_000_000_000 ms since epoch).
    df = pl.DataFrame({"id": ["018bcfe5-6800-7abc-9f09-0a0b0c0d0e0f"]})
    result = df.with_columns(polars_uuid.extract_timestamp("id").alias("ts"))
    assert result["ts"].dtype == pl.Datetime("ms")
    assert result["ts"][0] == datetime.datetime(
        2023, 11, 14, 22, 13, 20, tzinfo=datetime.timezone.utc
    ).replace(tzinfo=None)


def test_extract_timestamp_null_for_non_time_based_uuid():
    df = pl.DataFrame({"id": [str(uuid.uuid4())]})
    result = df.with_columns(polars_uuid.extract_timestamp("id").alias("ts"))
    assert result["ts"][0] is None


def test_extract_timestamp_null_for_invalid_uuid():
    df = pl.DataFrame({"id": ["not-a-uuid", None]})
    result = df.with_columns(polars_uuid.extract_timestamp("id").alias("ts"))
    assert result["ts"].to_list() == [None, None]
