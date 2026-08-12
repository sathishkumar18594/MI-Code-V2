from pathlib import Path
import os

import yaml


class ConfigLoader:

    _config = None

    @classmethod
    def load(cls):

        if cls._config is None:

            config_file = Path(
                os.environ.get(
                    "STRATEGY_CONFIG",
                    Path(__file__).parent / "strategy.yaml",
                )
            )

            with open(
                config_file,
                "r",
                encoding="utf-8"
            ) as file:

                cls._config = yaml.safe_load(file)

        return cls._config

    @classmethod
    def get(cls, *keys):

        value = cls.load()

        for key in keys:
            value = value[key]

        return value
