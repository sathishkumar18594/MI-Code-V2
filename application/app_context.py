from config.config_loader import ConfigLoader
from repositories.upstox_repository import UpstoxRepository
from repositories.parquet_repository import ParquetRepository
from services.report_service import ReportService


class AppContext:

    def __init__(self):

        #
        # Configuration
        #
        self.config = ConfigLoader.load()

        #
        # Repositories
        #
        self.price_repository = UpstoxRepository()

        self.index_repository = ParquetRepository(
            root="data_v2/upstox/index"
        )
        
        self.report_service = ReportService()
