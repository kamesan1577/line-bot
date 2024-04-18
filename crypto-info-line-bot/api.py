import requests
import json
import time
import datetime
import hmac
import hashlib
from abc import ABCMeta, abstractmethod
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class CryptInfoApi(metaclass=ABCMeta):

    exchange_name = ""
    base_url = ""

    def __init__(self, api_key):
        self.api_key = api_key

    @abstractmethod
    def get_balance(self) -> dict:
        pass

    @abstractmethod
    def get_transaction_log(self) -> dict:
        pass

    @abstractmethod
    def get_ticker(self) -> dict:
        pass

    @abstractmethod
    def get_rate(self) -> dict:
        pass

class CoincheckApi(CryptInfoApi):

        exchange_name = "coincheck"
        base_url = "https://coincheck.com"
        pair_list = ["btc_jpy", "eth_jpy","etc_jpy", "lsk_jpy", "mona_jpy", "plt_jpy", "fnct_jpy", "dai_jpy", "wbtc_jpy"]
        def __init__(self, api_key, api_secret):
            super().__init__(api_key)
            self.api_secret = api_secret

        def get_balance(self) -> dict:
            url = self.base_url + "/api/accounts/balance"
            response =  self.get(url)
            if response is None:
                return {"exchange_name": self.exchange_name, "balance": {}}
            if "success" in response:
                del response["success"]
            return {"exchange_name": self.exchange_name, "balance": response}

        def get_transaction_log(self) -> dict:
            url = self.base_url + "/api/exchange/orders/transactions"
            response = self.get(url)
            if response is None:
                return {"exchange_name": self.exchange_name, "transaction_log": []}
            if "success" in response:
                del response["success"]

            transaction_log = []
            for log in response["transactions"]:
                transaction_log.append({
                    "date": log["created_at"],
                    "funds": log["funds"],
                    "pair": log["pair"],
                    "fee_currency": log["fee_currency"],
                    "fee": log["fee"],
                    "order_type": log["side"],
                })

            return {"exchange_name": self.exchange_name, "transaction_log": transaction_log}

        def get_ticker(self,pair) -> dict:

            if pair not in self.pair_list:
                return {}
            url = self.base_url + f"/api/ticker?pair={pair}"
            response = self.get(url)
            if response is None:
                return {"exchange_name": self.exchange_name, "pair": pair, "ticker": {}}

            ticker = {
                "highest_deal_price": response["high"],
                "lowest_deal_price": response["low"],
                "deal_volume": response["volume"],
                "timestamp": datetime.datetime.fromtimestamp(response["timestamp"]),
            }
            return {"exchange_name": self.exchange_name, "pair": pair, "ticker": ticker}

        def get_rate(self,pair) -> dict:
            url = self.base_url + f"/api/rate/{pair}"
            response = self.get(url)
            if response is None:
                return {"exchange_name": self.exchange_name, "rate": {}, "pair": ""}
            rate = {
                "rate": response["rate"],
                "pair": pair,
            }
            return {"exchange_name": self.exchange_name, "rate": rate}

        def get(self, url):
            nonce = str(int(time.time()))
            message = nonce + url
            signature = self.get_signature(message)
            header = self.get_header(nonce, signature)
            try:
                response = requests.get(url, headers=header)
            except requests.exceptions.RequestException as e:
                logger.error(e)
                return None
            logger.info(response.json())
            return response.json()


        def get_signature(self,message,body=""):
            signature = hmac.new(
            bytes(self.api_secret.encode('ascii')),
            bytes((message + body).encode('ascii')),
            hashlib.sha256
         ).hexdigest()

            return signature

        def get_header(self,nonce,signature):
            header = {
            "ACCESS-KEY": self.api_key,
            "ACCESS-NONCE": nonce,
            "ACCESS-SIGNATURE": signature
            }
            return header
