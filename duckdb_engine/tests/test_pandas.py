#! /usr/bin/env python3
# vim:fenc=utf-8

"""
Test pandas functionality.
"""

import random
from collections import OrderedDict
from datetime import datetime
from itertools import product
from typing import Dict, List, Optional, Tuple, Union, cast

import pandas as pd
from pytest import mark, xfail
from sqlalchemy import create_engine

_possible_args = OrderedDict(
    {
        "chunksize": [None, 1, 10, 100],
        "if_exists": ["fail", "replace", "append"],
        "method": [
            None,
            "multi",
        ],  # TODO Implement a callable insert method?
    }
)

args = {
    "to_sql": ["chunksize", "if_exists", "method"],
    "read_sql": ["chunksize"],
}
params = {
    k: list(
        product(*(_v for _k, _v in _possible_args.items() if _k in args[k]))  # type: ignore
    )
    for k in args
}
params_strings = {k: (",".join([str(_k) for _k in args[k]])) for k in args}

# Generate a DataFrame of 100 rows.
sample_data: Dict[str, List[Union[datetime, str, int, float]]] = {
    "datetime": [],
    "int": [],
    "str": [],
    "float": [],
}
sample_rowcount = max(
    cs
    for cs in cast(List[Optional[int]], _possible_args["chunksize"])
    if cs is not None
)
for i in range(sample_rowcount):
    sample_data["datetime"].append(datetime.utcnow())
    sample_data["int"].append(random.randint(0, 100))
    sample_data["float"].append(round(random.random(), 5))
    sample_data["str"].append("foo")

sample_df: pd.DataFrame = pd.DataFrame(sample_data)


@mark.parametrize(params_strings["to_sql"], params["to_sql"])
def test_to_sql(
    chunksize: Optional[int],
    if_exists: str,
    method: Optional[str],
    index: bool = False,
) -> None:
    eng = create_engine("duckdb:///:memory:")
    try:
        sample_df.to_sql(
            name="foo",
            con=eng,
            if_exists=if_exists,
            chunksize=chunksize,
            index=index,
        )
    except ValueError as e:
        if if_exists != "fail":
            raise e


table_name = "test_read"


# Perform the test twice:
# Once for reading the table name (testing reflection),
@mark.xfail(reason="reflection not yet supported in duckdb")
@mark.parametrize(params_strings["read_sql"], params["read_sql"])
def test_read_sql_reflection(
    chunksize: Tuple[Optional[int]],
) -> None:
    run_query(table_name, chunksize[0])


# and once for directly executing a SQL query.
@mark.parametrize(params_strings["read_sql"], params["read_sql"])
def test_read_sql(
    chunksize: Tuple[Optional[int]],
) -> None:
    run_query(f"SELECT * FROM {table_name}", chunksize[0])


def run_query(query: str, chunksize: Optional[int]) -> None:
    eng = create_engine("duckdb:///:memory:")

    sample_df.to_sql(name=table_name, con=eng, if_exists="replace")

    result = pd.read_sql(query, eng, chunksize=chunksize)
    chunks = [result] if chunksize is None else list(result)
    if chunksize is None:
        assert len(chunks[0]) == sample_rowcount
    else:
        xfail(reason="This will fail until the next duckdb release")

        # Assert that the chunks are the size specified.
        assert len(chunks[0]) == chunksize
        # Assert that the expected number of chunks was returned.
        assert (sample_rowcount / chunksize) == len(chunks)
