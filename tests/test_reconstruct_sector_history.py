import pandas as pd

from script.reconstruct_sector_history import reconstruct


def test_reconstruct_reverses_additions_and_removals():
    changes = pd.DataFrame(
        {
            "effective_date": pd.to_datetime(["2021-01-01", "2022-01-01"]),
            "action": ["ADD", "REMOVE"],
            "symbol": ["B", "D"],
        }
    )

    members, reversed_additions, reversed_removals = reconstruct(
        {"A", "B", "C"}, changes, pd.Timestamp("2020-12-31")
    )

    assert members == ["A", "C", "D"]
    assert reversed_additions == 1
    assert reversed_removals == 1
