from application.app_context import AppContext
from services.factor_normalizer import (
    FactorNormalizer,
)


class ScoringService:

    def __init__(
        self,
        context: AppContext,
    ):
        self.context = context
        self.scoring = (
            context.config["scoring"]
        )
        self.normalizer = (
            FactorNormalizer()
        )

    def calculate(
        self,
        df,
    ):

        result = df.copy()

        result["score"] = 0.0

        factors = self.get_enabled_factors()

        total_weight = 0

        for factor_name, factor in factors.items():

            if not factor["enabled"]:
                continue

            if factor_name not in result.columns:

                raise ValueError(
                    f"Missing factor: {factor_name}"
                )

            normalized = self.normalizer.normalize(
                result[factor_name],
                higher_is_better=factor[
                    "higher_is_better"
                ],
            )

            result["score"] += (
                normalized
                * factor["weight"]
            )

            total_weight += (
                factor["weight"]
            )

        #
        # Optional:
        # Normalize score back to 0-1
        #
        if total_weight > 0:

            result["score"] /= total_weight

        return result

    def get_factors(self):

        return self.scoring[
            "factors"
        ]

    def get_enabled_factors(self):

        return {
            factor_name: factor
            for factor_name, factor in self.get_factors().items()
            if factor.get("enabled", False)
        }

    def get_factor_values(
        self,
        row,
    ):

        return {
            factor_name: row[factor_name]
            for factor_name in self.get_enabled_factors()
            if factor_name in row.index
        }
