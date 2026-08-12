WEIGHT_TOLERANCE = 0.0001
VALUE_TOLERANCE = 0.01

class PortfolioValidator:

    def validate(self, portfolio, expected_size):

        self._validate_structure(
            portfolio,
            expected_size,
        )

        self._validate_integrity(
            portfolio,
        )

        self._validate_strategy(
            portfolio,
        )

    def _validate_structure(
        self,
        portfolio,
        expected_size,
    ):

        self._validate_holdings_count(
            portfolio,
            expected_size,
        )

        self._validate_duplicate_symbols(
            portfolio,
        )

        self._validate_weights(
            portfolio,
        )

        self._validate_cash(
            portfolio,
        )

    def _validate_integrity(
        self,
        portfolio,
    ):

        self._validate_prices(
            portfolio,
        )

        self._validate_quantities(
            portfolio,
        )

        self._validate_market_values(
            portfolio,
        )

        self._validate_total_value(
            portfolio,
        )

        self._validate_position_values(
            portfolio,
        )

        self._validate_allocations(
            portfolio,
        )

    def _validate_strategy(
        self,
        portfolio,
    ):
        """Strategy-specific validations (liquidity, sectors, circuits, etc.)."""
        pass

    def _validate_holdings_count(
        self,
        portfolio,
        expected_size,
    ):

        actual = len(portfolio.holdings)

        if actual != expected_size:
            raise ValueError(
                f"Expected {expected_size} holdings but found {actual}."
            )

    def _validate_duplicate_symbols(
        self,
        portfolio,
    ):

        symbols = [
            holding.symbol
            for holding in portfolio.holdings
        ]

        if len(symbols) != len(set(symbols)):
            raise ValueError(
                "Duplicate symbols found in portfolio."
            )

    def _validate_weights(
        self,
        portfolio,
    ):

        total_weight = sum(
            holding.weight
            for holding in portfolio.holdings
        )

        if abs(total_weight - 1.0) > WEIGHT_TOLERANCE:
            raise ValueError(
                f"Portfolio weights sum to {total_weight:.6f}, expected 1.0."
            )

    def _validate_cash(
        self,
        portfolio,
    ):

        if portfolio.cash < -0.01:
            raise ValueError(
                f"Portfolio cash cannot be negative: {portfolio.cash:.2f}"
            )

    def _validate_prices(
        self,
        portfolio,
    ):

        for holding in portfolio.holdings:

            if holding.entry_price <= 0:
                raise ValueError(
                    f"{holding.symbol}: invalid entry price {holding.entry_price}."
                )

            if holding.current_price <= 0:
                raise ValueError(
                    f"{holding.symbol}: invalid current price {holding.current_price}."
                )

    def _validate_quantities(
        self,
        portfolio,
    ):

        for holding in portfolio.holdings:

            if holding.quantity <= 0:
                raise ValueError(
                    f"{holding.symbol}: invalid quantity {holding.quantity}."
                )

    def _validate_market_values(
        self,
        portfolio,
    ):

        for holding in portfolio.holdings:

            if holding.market_value < 0:
                raise ValueError(
                    f"{holding.symbol}: negative market value {holding.market_value}."
                )

            if holding.cost_value < 0:
                raise ValueError(
                    f"{holding.symbol}: negative cost value {holding.cost_value}."
                )

    def _validate_total_value(
        self,
        portfolio,
    ):

        holdings_value = sum(
            holding.market_value
            for holding in portfolio.holdings
        )

        calculated_total = (
            holdings_value + portfolio.cash
        )

        if abs(calculated_total - portfolio.total_value) > VALUE_TOLERANCE:
            raise ValueError(
                f"Portfolio total value mismatch. "
                f"Expected {portfolio.total_value:.2f}, "
                f"calculated {calculated_total:.2f}."
            )

    def _validate_position_values(
        self,
        portfolio,
    ):

        for holding in portfolio.holdings:

            expected_market_value = (
                holding.quantity
                * holding.current_price
            )

            if abs(expected_market_value - holding.market_value) > VALUE_TOLERANCE:
                raise ValueError(
                    f"{holding.symbol}: market value mismatch. "
                    f"Expected {expected_market_value:.2f}, "
                    f"found {holding.market_value:.2f}."
                )

    def _validate_allocations(
        self,
        portfolio,
    ):

        for holding in portfolio.holdings:

            expected_weight = (
                holding.market_value
                / portfolio.total_value
            )

            if abs(expected_weight - holding.weight) > WEIGHT_TOLERANCE:
                raise ValueError(
                    f"{holding.symbol}: weight mismatch. "
                    f"Expected {expected_weight:.6f}, "
                    f"found {holding.weight:.6f}."
                )