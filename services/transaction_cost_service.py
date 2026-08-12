from application.app_context import AppContext
from models.trade_charges import TradeCharges

class TransactionCostService:
    def __init__(self, context: AppContext):
        self.context = context
        self.config = context.config["charges"]

    def calculate_buy(
        self,
        trade_value,
    ):
        brokerage_rate = self.config["brokerage"]["delivery"]
        stt_rate = self.config["stt"]["delivery_buy"]
        exchange_rate = self.config["exchange"]["nse"]
        sebi_rate = self.config["sebi"]["turnover"]
        gst_rate = self.config["gst"]["percentage"]
        stamp_duty_rate = self.config["stamp_duty"]["delivery"]

        brokerage = trade_value * brokerage_rate
        stt = trade_value * stt_rate
        exchange_charge = trade_value * exchange_rate
        sebi_charge = trade_value * sebi_rate
        gst = (brokerage + exchange_charge + sebi_charge) * gst_rate
        stamp_duty = trade_value * stamp_duty_rate
        total = brokerage + stt + exchange_charge + sebi_charge + gst + stamp_duty

        return TradeCharges(
            brokerage=brokerage,
            stt=stt,
            exchange_charge=exchange_charge,
            sebi_charge=sebi_charge,
            gst=gst,
            stamp_duty=stamp_duty,
            total=total
        )

    def calculate_sell(
        self,
        trade_value,
    ):
        brokerage_rate = self.config["brokerage"]["delivery"]
        stt_rate = self.config["stt"]["delivery_sell"]
        exchange_rate = self.config["exchange"]["nse"]
        sebi_rate = self.config["sebi"]["turnover"]
        gst_rate = self.config["gst"]["percentage"]
        # stamp duty is 0 for sell
        stamp_duty = 0.0

        brokerage = trade_value * brokerage_rate
        stt = trade_value * stt_rate
        exchange_charge = trade_value * exchange_rate
        sebi_charge = trade_value * sebi_rate
        gst = (brokerage + exchange_charge + sebi_charge) * gst_rate
        total = brokerage + stt + exchange_charge + sebi_charge + gst + stamp_duty

        return TradeCharges(
            brokerage=brokerage,
            stt=stt,
            exchange_charge=exchange_charge,
            sebi_charge=sebi_charge,
            gst=gst,
            stamp_duty=stamp_duty,
            total=total
        )