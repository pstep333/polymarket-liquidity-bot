import sys
import pandas as pd
import os
from datetime import datetime
from py_clob_client.order_builder.constants import BUY, SELL
from py_clob_client.client import ClobClient, OrderArgs, OpenOrderParams
from py_clob_client.clob_types import OrderArgs

# from variables import host, key, chain_id, funder, ids


from dotenv import load_dotenv
from eth_account import Account

# Load environment variables from .env
load_dotenv()

key = os.getenv("PRIVATE_KEY")
public_key = Account.from_key(key)
funder = public_key.address


print("Using the wallet address:", funder)

chain_id = 137
host = 'https://clob.polymarket.com'

ids = ['0xfa48a99317daef1654d5b03e30557c4222f276657275628d9475e141c64b545d', # US recession in 2025?
       '0xfc4c7a2af57acbbd42223ea7d6472aae124d73166b3b631ff9981496a2fe42d9', # Will the price of Ethereum be between $1600 and $1700 on Apr 25?
       '0xd89059ab7874993719630031e34f055ca68236eb9b82aed815fd42dc50d3638d', # Will the price of Ethereum be between $1500 and $1600 on Apr 25?
       '0x8ee2f1640386310eb5e7ffa596ba9335f2d324e303d21b0dfea6998874445791', # Russia x Ukraine ceasefire in 2025?
       '0x87822b3d4ccba1835d698354b01c050b55f20c5f34b14908bff4ea5a6d58af4c', # Will Mark Carney be the next Canadian Prime Minister?
        '0xfa48a99317daef1654d5b03e30557c4222f276657275628d9475e141c64b545d', # US recession in 2025?
        '0x322ba30e34f7ca9c6d43d00660aece6db8f3188a22795df2e3bf28c863a0c4b4', # Bitcoin Up or Down in Q2?
        '0x9d84821a6c8b45fcd9dad9f50f1b0fc6cb76de7a68d7686bfefba697c32a6375', # will-bitcoin-reach-95k-in-april
        '0x7a18e4d613d7bf6afa06aa9eb1f9287ca81e841d77ae6d5fabdab37f0c0b5d6c' # will-bitcoin-reach-100k-in-april
      ]


def init_client():
    client = ClobClient(host=host, key=key, chain_id=chain_id)
    client.set_api_creds(client.create_or_derive_api_creds())
    return client


def get_open_markets(client):
    resp = client.get_markets()

    pages = []
    pages.append(resp['data'])

    flag = True
    i = 0
    while flag:
        print(f'page: {i}')
        resp = client.get_markets(next_cursor=resp['next_cursor'])
        pages.append(resp['data'])
        i += 1
        if resp['next_cursor'] == 'LTE=':
            flag = False

    open_markets = []
    for page in pages:
        for market in page:
            if (market['active'] == True) & (market['closed'] == False):
                open_markets.append(market)

    df = pd.DataFrame()
    for market in open_markets:
        df_dictionary = pd.DataFrame([market])
        df = pd.concat([df, df_dictionary], ignore_index=True)

    print(df.head())


def get_tokens(client, condition_id):
    try:
        resp = client.get_market(condition_id=condition_id)
        tokens = resp['tokens']
        token_id_1 = tokens[0]['token_id']
        token_id_2 = tokens[1]['token_id']
    except Exception as e:
        print(e)
    return token_id_1, token_id_2


def get_order(order_dict: dict) -> dict:
    size = float(order_dict.get("original_size")) - float(
        order_dict.get("size_matched")
    )
    price = float(order_dict.get("price"))
    side = order_dict.get("side")
    order_id = order_dict.get("id")
    token_id = int(order_dict.get("asset_id"))

    return {
        "size": size,
        "price": price,
        "side": side,
        "token_id": token_id,
        "id": order_id,
    }


def get_orders(client, condition_id):
    try:
        resp = client.get_orders(OpenOrderParams(market=condition_id))
        return [get_order(order) for order in resp]
    except Exception as e:
        print(f'Failed to get orders: {e}')
    return None


def place_order(client, price, size, side, token_id, condition_id):
    side = BUY if side.lower() == 'buy' else SELL
    try:
        resp = client.create_and_post_order(
            OrderArgs(price=price, size=size, side=side, token_id=token_id)
        )
        order_id = None
        if resp and resp.get("success") and resp.get("orderID"):
            order_id = resp.get("orderID")
            print(f'{datetime.now()} ~~ Order succesfully placed! ~~ {order_id[:5]}: {side}, {price}, {size}, {token_id[:5]}\n')
            return order_id

        err_msg = resp.get("errorMsg")
        print(f'Order unsuccesfull: {err_msg}')
        
    except Exception as e:
        print(f'Failed to place order for market {condition_id[:5]}:\n{e}\nprice: {price}, size: {size}, amount: {price * size}, token: {token_id}')
        a = cancel_all_orders(client=client)
        if a: print('Cancelled all orders')
        sys.exit('\nExiting.\n')
    return True


def cancel_order(client, order_id):
    if order_id is None:
        print("Invalid order_id")
        return False
    try:
        _ = client.cancel(order_id)
        print(f'{datetime.now()} ~~ Order {order_id[:5]} cancelled\n')
        return True
    except Exception as e:
        print(f"Error cancelling order: {order_id}: {e}")
    return False


def cancel_all_orders(client) -> bool:
    print("Cancelling all open orders..")
    try:
        _ = client.cancel_all()
        return True
    except Exception as e:
        print(f"Error cancelling all orders: {e}")
    return False


def return_markets(client, ids):
    markets = []
    for id in ids:
        token_1, token_2 = get_tokens(client=client, condition_id=id)
        market = {'condition_id': id, 'token_1': token_1, 'token_2': token_2}
        markets.append(market)
    return markets


def main():
    return 0


if __name__ == '__main__':
    main()
