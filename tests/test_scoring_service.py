import pandas as pd

from services.scoring_service import ScoringService


def test_scoring_service():

    df = pd.DataFrame(
        {
            "return_9m": [
                0.80,
                0.60,
                0.40,
            ],
            "return_6m": [
                0.70,
                0.50,
                0.30,
            ],
            "return_3m": [
                0.60,
                0.40,
                0.20,
            ],
            "volatility": [
                0.40,
                0.20,
                0.10,
            ],
        }
    )

    result = ScoringService().calculate(df)

    print()
    print(result)

    assert "score" in result.columns

    #
    # Higher score should rank first
    #
    ranked = result.sort_values(
        "score",
        ascending=False,
    )

    assert len(ranked) == 3

    assert ranked.iloc[0]["score"] >= ranked.iloc[1]["score"]

    assert ranked.iloc[1]["score"] >= ranked.iloc[2]["score"]