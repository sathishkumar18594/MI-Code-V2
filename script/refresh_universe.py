from services.universe_service import UniverseService

service = UniverseService()

service.refresh("nifty500")
service.refresh("midcap250")
service.refresh("niftymidcap150")
