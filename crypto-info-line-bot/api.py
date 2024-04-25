import requests
import json
import time
import datetime
import hmac
import hashlib
import dataclasses
from decimal import Decimal, getcontext
from abc import ABCMeta, abstractmethod
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class CryptInfoApi(metaclass=ABCMeta):

    provider_name = ""
    base_url = ""

    def __init__(self, api_key):
        self.api_key = api_key

    @abstractmethod
    def get_balance(self) -> dict:
        pass

    @abstractmethod
    def get_rate(self) -> dict:
        pass

class CoincheckApi(CryptInfoApi):

        provider_name = "coincheck"
        base_url = "https://coincheck.com"
        pair_list = ["btc_jpy", "eth_jpy","etc_jpy", "lsk_jpy", "mona_jpy", "plt_jpy", "fnct_jpy", "dai_jpy", "wbtc_jpy"]
        def __init__(self, api_key, api_secret):
            super().__init__(api_key)
            self.api_secret = api_secret

        def get_balance(self) -> dict:
            url = self.base_url + "/api/accounts/balance"
            response =  self.get(url)
            if response is None:
                return {"provider_name": self.provider_name, "balance": {}}
            if "success" in response:
                del response["success"]
            return {"provider_name": self.provider_name, "balance": response}

        def get_transaction_log(self) -> dict:
            url = self.base_url + "/api/exchange/orders/transactions"
            response = self.get(url)
            if response is None:
                return {"provider_name": self.provider_name, "transaction_log": []}
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

            return {"provider_name": self.provider_name, "transaction_log": transaction_log}

        def get_ticker(self,pair) -> dict:

            if pair not in self.pair_list:
                return {}
            url = self.base_url + f"/api/ticker?pair={pair}"
            response = self.get(url)
            if response is None:
                return {"provider_name": self.provider_name, "pair": pair, "ticker": {}}

            ticker = {
                "highest_deal_price": response["high"],
                "lowest_deal_price": response["low"],
                "deal_volume": response["volume"],
                "timestamp": datetime.datetime.fromtimestamp(response["timestamp"]),
            }
            return {"provider_name": self.provider_name, "pair": pair, "ticker": ticker}

        def get_rate(self,pair) -> dict:
            url = self.base_url + f"/api/rate/{pair}"
            response = self.get(url)
            if response is None:
                return {"provider_name": self.provider_name, "rate": {}, "pair": ""}
            return {"provider_name": self.provider_name, "rate": response["rate"], "pair": pair}

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

@dataclasses.dataclass
class OptimisticToken:
    name: str
    contract_address: str
    decimals:int = 18

    @classmethod
    def get_real_balance(cls, balance_int):
        return int(Decimal(balance_int) / Decimal(10 ** cls.decimals))

optimistic_tokens = {"WLD": OptimisticToken(name="WLD", contract_address="0xdC6fF44d5d932Cbd77B52E5612Ba0529DC6226F1"),"USDC":OptimisticToken(name="USDC", contract_address="0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",decimals=6)}

class OptimisticEtherscanApi(CryptInfoApi):

    provider_name = "optimism_mainnet"
    base_url = "https://api-optimistic.etherscan.io/api"


    def __init__(self, etherscan_api_key, coinmarketcap_api_key,wallet_address):
        self.etherscan_api_key=etherscan_api_key
        self.coinmarketcap_api_key = coinmarketcap_api_key
        self.wallet_address = wallet_address

    def get_balance(self,token_name) -> dict:
        token = optimistic_tokens[token_name]
        url = self.base_url + f"?module=account&action=tokenbalance&contractaddress={token.contract_address}&address={self.wallet_address}&tag=latest&apikey={self.etherscan_api_key}"
        response = self.get(url)
        if response is None:
            return {"provider_name": self.provider_name, "balance": {}}
        balance = {}
        for token_name, token in optimistic_tokens.items():
            balance[token_name] = OptimisticToken.get_real_balance(int(response["result"]))
        return {"provider_name": self.provider_name, "balance": balance}

    def get_rate(self,token_name) -> dict:
        coinMarketCapApi = CoinMarketCapApi(self.coinmarketcap_api_key)
        rate = coinMarketCapApi.get_rate(token_name)
        return {"provider_name": self.provider_name, "rate": rate, "token_name": token_name}

    def get(self, url):
        try:
            response = requests.get(url)
            logger.info({"request":url,"response":response.json()})
        except requests.exceptions.RequestException as e:
            logger.info({"request":url,"response":e})
            return None
        return response.json()


class CoinMarketCapApi():
    base_url = "https://pro-api.coinmarketcap.com/"
    def __init__(self, api_key):
        self.api_key = api_key

    def get_rate(self, symbol) -> dict:
        url = self.base_url + f"v2/cryptocurrency/quotes/latest"
        query = "?symbol=" + symbol + "&CMC_PRO_API_KEY=" + self.api_key + "&convert=JPY"
        url += query
        response = self.get(url)
        if response is None:
            return None
        rate = float(response["data"][symbol][0]["quote"]["JPY"]["price"])
        return rate
    def get(self, url):
        headers = {
            "Accept": "application/json"
        }
        try:
            response = requests.get(url, headers=headers)
            logger.info({"request":url,"response":response.json()})
        except requests.exceptions.RequestException as e:
            logger.info({"request":url,"response":e})
            return None
        return response.json()

