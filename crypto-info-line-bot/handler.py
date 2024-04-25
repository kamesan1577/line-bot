import logging
import json
import os
import sys
import textwrap

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

from api import CoincheckApi, OptimisticEtherscanApi

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


CHANNEL_ACCESS_TOKEN = os.getenv('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.getenv('CHANNEL_SECRET')

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
web_hook_handler = WebhookHandler(CHANNEL_SECRET)

COINCHECK_API_KEY = os.getenv('COINCHECK_API_KEY')
COINCHECK_SECRET_KEY = os.getenv('COINCHECK_SECRET_KEY')

coincheckApi = CoincheckApi(COINCHECK_API_KEY, COINCHECK_SECRET_KEY)

TARGET_GROUP_ID = os.getenv('TARGET_GROUP_ID')

ETHERSCAN_API_KEY = os.getenv('ETHERSCAN_API_KEY')
COINMARKETCAP_API_KEY = os.getenv('COINMARKETCAP_API_KEY')
OPTIMISM_WALLET = os.getenv('OPTIMISM_WALLET')
etherscanApi = OptimisticEtherscanApi(ETHERSCAN_API_KEY, COINMARKETCAP_API_KEY, OPTIMISM_WALLET)



@web_hook_handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    message = event.message.text
    if message == '残高':
        response = Summary.balance()
    if message == '取引履歴':
        response = Summary.transaction()
    if message == 'レート':
        response = Summary.rate()

    if message == 'test':
        response = 'テストメッセージです。'
    if message == ("help" or "ヘルプ"):
        response = textwrap.dedent(f"""
        以下のコマンドを入力してください。
        残高: 現在の残高を表示します。
        取引履歴: 直近の取引履歴を表示します。
        レート: 現在のレートを表示します。
        """).strip()

    logger.info(response)
    try:
        line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response)
    )
    except LineBotApiError as e:
        logger.error('Got exception from LINE Messaging API: %s\n' % e.message)
        for m in e.error.details:
            logger.error('  %s: %s' % (m.property, m.message))
        line_bot_api.reply_message(
            event.reply_token,TextSendMessage(text='エラーが発生しました。')
        )

def lambda_handler(event, context):
    # ヘッダーにx-line-signatureがあることを確認
    if 'x-line-signature' in event['headers']:
        signature = event['headers']['x-line-signature']

    body = event['body']
    # 受け取ったWebhookのJSON
    logger.info(body)

    try:
        web_hook_handler.handle(body, signature)
    except InvalidSignatureError:
        # 署名を検証した結果がLINEプラットフォームからのWebhookでなければ400を返す
        return {
            'statusCode': 400,
            'body': json.dumps('Webhooks are accepted exclusively from the LINE Platform.')
        }
    except LineBotApiError as e:
        # 応答メッセージを送る際LINEプラットフォームからエラーが返ってきた場合
        logger.error('Got exception from LINE Messaging API: %s\n' % e.message)
        for m in e.error.details:
            logger.error('  %s: %s' % (m.property, m.message))

    return {
        'statusCode': 200,
        'body': json.dumps('Success!')
    }

def lambda_handler_cron(event,context):
    try:
        balance_message = f"""
        定期メッセージです。\n
        """.strip()
        balance_summary_message = Summary.balance()

        balance_message += balance_summary_message

        rate_message = f"""
        定期メッセージです。
        """.strip()
        rate_summary_message = Summary.rate()

        rate_message += rate_summary_message

        if TARGET_GROUP_ID is not None:
            line_bot_api.push_message(TARGET_GROUP_ID, TextSendMessage(text=balance_message))
            line_bot_api.push_message(TARGET_GROUP_ID, TextSendMessage(text=rate_message))
        line_bot_api.broadcast(TextSendMessage(text=balance_message))
        line_bot_api.broadcast(TextSendMessage(text=rate_message))

    except LineBotApiError as e:
        # 応答メッセージを送る際LINEプラットフォームからエラーが返ってきた場合
        logger.error('Got exception from LINE Messaging API: %s\n' % e.message)
        for m in e.error.details:
            logger.error('  %s: %s' % (m.property, m.message))
    return {
        'statusCode': 200,
        'body': json.dumps('Success!')
    }


class CoincheckUtils:
    @staticmethod
    def convert_x_to_jpy(pair: str, lh_amount: float) -> float:
        rate = coincheckApi.get_rate(pair)['rate']
        return float(lh_amount) * float(rate)

class EtherscanUtils:
    @staticmethod
    def convert_x_to_jpy(token, amount: float) -> float:
        rate = etherscanApi.get_rate(token)["rate"]
        return float(amount) * float(rate)

class Summary:
    def balance():
        data = coincheckApi.get_balance()
        balance = data['balance']
        provider_name = data['provider_name']
        jpy_balance = int(float(balance['jpy']))
        btc_balance_jpy = int(CoincheckUtils.convert_x_to_jpy("btc_jpy",float(balance['btc'])))
        eth_balance = int(CoincheckUtils.convert_x_to_jpy("eth_jpy",float(balance['eth'])))

        coincheck_total_balance_jpy = jpy_balance + btc_balance_jpy + eth_balance
        logger.info(balance)
        message = f"""
        現在の{provider_name}の残高は以下の通りです。
        日本円: {jpy_balance:,} 円
        ビットコイン: {balance['btc']} BTC
        (円換算: {btc_balance_jpy:,}円)
        イーサリアム: {balance['eth']} ETH
        (円換算: {eth_balance:,}円)

        合計残高(円 + BTC + ETH): {coincheck_total_balance_jpy:,} 円
        """

        wld_data = etherscanApi.get_balance("WLD")
        usdc_data = etherscanApi.get_balance("USDC")

        wld_balance = wld_data['balance']["WLD"]
        usdc_balance = usdc_data['balance']["USDC"]
        provider_name = wld_data['provider_name']

        wld_balance_jpy = int(EtherscanUtils.convert_x_to_jpy("WLD", wld_balance))
        usdc_balance_jpy = int(EtherscanUtils.convert_x_to_jpy("USDC", usdc_balance))
        logger.info(wld_balance)
        logger.info(usdc_balance)

        optimism_total_balance = wld_balance_jpy + usdc_balance_jpy
        message += f"""
        {provider_name}の残高は以下の通りです。
        WLD: {wld_balance:,} WLD
        (円換算: {wld_balance_jpy:,}円)
        USD Coin: {usdc_balance:,} USDC
        (円換算: {usdc_balance_jpy:,}円)

        合計残高(WLD + USDC): {optimism_total_balance:,} 円
        """

        total_balance = coincheck_total_balance_jpy + optimism_total_balance
        message += f"""
        --------------------------------
        全財産の合計残高: {total_balance:,} 円
        """
        return textwrap.dedent(message).strip()


    def transaction():
        data = coincheckApi.get_transaction_log()
        transaction_log = data['transaction_log']
        provider_name = data['provider_name']

        logger.info(transaction_log)

        message = f"""
        {provider_name}の取引履歴は以下の通りです。
        """

        for log in transaction_log:
            message += f"""
            --------------------------------
            テスト中です
            日時: {log['date']}
            取引ペア: {log['pair']}
            注文タイプ: {"売り" if log['order_type'] == "sell" else "買い"}
            増減(JPY): {"+ " + log["funds"]["jpy"] if float(log["funds"]["jpy"]) >= 0 else "- " + log["funds"]["jpy"] :,} 円

            手数料: {log['fee']:,} {log['fee_currency']}
            """

        return textwrap.dedent(message).strip()

    def rate():
        btc_rate = coincheckApi.get_rate("btc_jpy")
        eth_rate = coincheckApi.get_rate("eth_jpy")
        provider_name = btc_rate['provider_name']

        logger.info(btc_rate)
        logger.info(eth_rate)

        message = f"""
        {provider_name}のレートは以下の通りです。
        ビットコイン: {int(float(btc_rate['rate'])):,} 円
        イーサリアム: {int(float(eth_rate['rate'])):,} 円
        """

        wld_rate = etherscanApi.get_rate("WLD")
        usdc_rate = etherscanApi.get_rate("USDC")
        provider_name = wld_rate['provider_name']

        logger.info(wld_rate)
        logger.info(usdc_rate)

        message += f"""
        {provider_name}のレートは以下の通りです。
        WLD: {int(float(wld_rate['rate'])):,} 円
        USD Coin: {int(float(usdc_rate['rate'])):,} 円
        """

        return textwrap.dedent(message).strip()

