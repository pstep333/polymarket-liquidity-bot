import sys
import pandas as pd
from datetime import datetime
from py_clob_client.order_builder.constants import BUY, SELL
from py_clob_client.client import ClobClient, OrderArgs, OpenOrderParams


def init_client():
    chain_id = 137
    host = 'https://clob.polymarket.com'
    key = '' # private key
    funder = '' # public address

    client = ClobClient(host=host, key=key, chain_id=chain_id, signature_type=1, funder=funder)
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
            print(datetime.now())
            print('Order succesfully placed!')
            print(f'{order_id[:5]}: {side}, {price}, {size}, {token_id[:5]}\n')
            return order_id

        err_msg = resp.get("errorMsg")
        print(f'Order unsuccesfull: {err_msg}')
        
    except Exception as e:
        print(f'Failed to place order for market {condition_id[:5]}:\n{e}\nprice: {price}, size: {size}, amount: {price * size}')
        a = cancel_all_orders(client=client)
        if a: print('Cancelled all orders')
        sys.exit('\nExitting.\n')
    return True


def cancel_order(client, order_id):
    if order_id is None:
        print("Invalid order_id")
        return False
    try:
        _ = client.cancel(order_id)
        print(datetime.now())
        print(f'Order {order_id[:5]} cancelled\n')
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


def main():
    return 0


if __name__ == '__main__':
    main()
