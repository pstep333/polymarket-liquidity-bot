import json, time, math
import asyncio
import websockets
import pandas as pd

from multiprocessing import Process, Event
from polymarket import init_client, get_orders, place_order, cancel_order, cancel_all_orders, get_tokens


URL = 'wss://ws-subscriptions-clob.polymarket.com/ws/market'
processes = []
stop_event = Event()


def return_markets(client):
    ids = ['0x4e0f29885709d63bfcff29e80f4a8df1da9e97906ba9e21577b46a70858d8e06', # no change fed
           '0xf48f79d8e60ab1efa76e53bec8c005611bfdc097cc0e51dc2f612709c04f5acf', # 25 bps
           '0x83cbe2163655a7b55283f92cc0d1f70538408e27dca50657744362b802eb57e5', # super heavy explodes
           '0xef5604329fee713a68f4faa9d3014614c7486525864a11f2ebb054179a0c362e', # no change fed
           '0xeed6da09683149b433aeb802bd8d3f78a6b6d8799fa75bd0d73c3f87c6b2b592', # 25 bps
           '0x6e9fda006161184b29a2df3754b5b9c3757f8a2adc1f44291fe9907f8fc6ae97', # jurassic world 
           '0x8b983af0d3bb4339f809efb01439cf825331c02522c2c70c1b53f13ea4a5432d', # nickel boys
           '0x2e87bcd620d1c9f16f82e19f626f39047cbf152018461cb7146df27d981cbf1f', # brat
           '0xc53769f49bdd1e16177f64d42967b0ab2344ecc2945da88d1a67bc8771c31a1a', # tortured poet
           '0x4b4d70030f24d4eae335226191ac7fbfd93f1a45f0b1b57b639015b14625b54d'  # cowboy carter
          ]
    
    markets = []
    for id in ids:
        token_1, token_2 = get_tokens(client=client, condition_id=id)
        market = {'condition_id': id, 'token_1': token_1, 'token_2': token_2}
        markets.append(market)
    return markets


def check_book(max_spread, spread, bids_df, order_size, min_tick_size):
    max_spread = round(max_spread - 0.005, 3)
    best_bid = round(bids_df.loc[0, 'price'], 4)

    midpoint = round(best_bid + (spread / 2), 4)
    lower_bound = round(midpoint - max_spread, 4)
    spread_str = str(spread)
    last_d = int(spread_str.rsplit('.')[-1][-1])
    if last_d % 2 == 0:
        if min_tick_size == 0.01:
            lower_bound = round(midpoint - max_spread - 0.01, 3)
        else: lower_bound = round(midpoint - max_spread - 0.001, 4)
    relevant_bids = bids_df[round(bids_df['price'], 3) > lower_bound]
    bid_lvls = len(relevant_bids)
    
    if bid_lvls > 9: lowest_bid = round(relevant_bids.loc[8, 'price'], 4)
    elif bid_lvls > 6: lowest_bid = round(relevant_bids.loc[6, 'price'], 4)
    elif bid_lvls > 4: lowest_bid = round(relevant_bids.loc[4, 'price'], 4)
    elif bid_lvls > 2: lowest_bid = round(relevant_bids.loc[len(relevant_bids) - 1, 'price'], 4)
    else: lowest_bid = 0

    if min_tick_size == 0.001:
        if bid_lvls <= 4: lowest_bid = 0

    if min_tick_size == 0.01:
        if bid_lvls == 2:
            if last_d % 2 == 0: 
                target = round(midpoint - max_spread, 3)
            else: 
                target = round(midpoint - max_spread + 0.005, 3)
            if round(relevant_bids.loc[1, 'price'], 3) != target:
                lowest_bid = target
            if relevant_bids.loc[1, 'size'] == order_size: # if second order cancels, our order becomes second order -> cancel
                lowest_bid = 0
    if midpoint <= 0.1: lowest_bid = 0

    bids_above_size = 1000000
    if lowest_bid != 0:
        bids_above_size = bids_df[round(bids_df['price'], 3) > lowest_bid]['size'].sum()

    # adjust amounts as wanted
    if bids_df[round(bids_df['price'], 3) > lowest_bid]['amount'].sum() <= 75:
        amount = 0
        lowest_bid = 0
    elif bids_df[round(bids_df['price'], 3) > lowest_bid]['amount'].sum() <= 100:
        amount = 10
    elif bids_df[round(bids_df['price'], 3) > lowest_bid]['amount'].sum() <= 150:
        amount = 20
    elif bids_df[round(bids_df['price'], 3) > lowest_bid]['amount'].sum() <= 225:
        amount = 25
    elif bids_df[round(bids_df['price'], 3) > lowest_bid]['amount'].sum() <= 450:
        amount = 35
    elif bids_df[round(bids_df['price'], 3) > lowest_bid]['amount'].sum() <= 700:
        amount = 50
    else:
        amount = 58
    '''elif bids_df[round(bids_df['price'], 3) > lowest_bid]['amount'].sum() <= 1000:
        amount = 70'''
    
    # print(f'lowest_bid: {lowest_bid}, midpoint: {midpoint}, amount: {amount}, bid_lvls: {bid_lvls}, actual: {round(relevant_bids.loc[1, "price"], 3)}, \nrelevant_bids: {relevant_bids}')
    return lowest_bid, bids_above_size, amount, midpoint


def get_market_data(client, condition_id):
    resp = client.get_market(condition_id=condition_id)
    min_tick_size = resp['minimum_tick_size']
    reward_data = resp['rewards']
    min_size = reward_data['min_size']
    max_spread = round(reward_data['max_spread'] / 100, 4)
    rates = reward_data['rates']

    daily_rate = rates[0]['rewards_daily_rate'] if rates is not None else 0

    return min_size, daily_rate, max_spread, min_tick_size


def parse_orderbook(data, token_1, token_2):
    token_to_use = token_1
    spread = 0
    bids = data['bids']
    asks = data['asks']

    bids_df = pd.DataFrame(bids)
    asks_df = pd.DataFrame(asks)
    bids_df = bids_df.reindex(index=bids_df.index[::-1]).reset_index(drop=True)
    asks_df = asks_df.reindex(index=asks_df.index[::-1]).reset_index(drop=True)

    if all(x in bids_df.columns for x in ['size', 'price']):
        bids_df['price'] = bids_df['price'].apply(lambda x: float(x))
        bids_df['size'] = bids_df['size'].apply(lambda x: float(x))
        asks_df['price'] = asks_df['price'].apply(lambda x: float(x))
        asks_df['size'] = asks_df['size'].apply(lambda x: float(x))
        bids_df['amount'] = round(bids_df['price'] * bids_df['size'], 2)
        asks_df['amount'] = round(asks_df['price'] * asks_df['size'], 2)
        best_bid = bids_df.loc[0, 'price']
        best_ask = asks_df.loc[0, 'price']
        spread = round(best_ask - best_bid, 4)

        bids = bids_df
        asks = asks_df
        if best_bid > 0.5:
            bids_df['price'] = bids_df['price'].apply(lambda x: 1 - x)
            bids_df['amount'] = round(bids_df['price'] * bids_df['size'], 2)
            asks_df['price'] = asks_df['price'].apply(lambda x: 1 - x)
            asks_df['amount'] = round(asks_df['price'] * asks_df['size'], 2)
            bids = asks_df
            asks = bids_df
            token_to_use = token_2

    return bids, spread, token_to_use


async def handle_market(client, market, min_size, daily_rate, max_spread, min_tick_size):
    condition_id = market['condition_id']
    token_1 = market['token_1']
    token_2 = market['token_2']

    def return_data(data):
        i = 0
        for j in range(len(data)):
            if data[j]['asset_id'] == token_1: i = j
        data = data[i]
        return data

    while not stop_event.is_set():
        temp_midpoint = 0
        temp_token = token_1
        buy_flag = 0
        order_size = 0
        open_orders = get_orders(client=client, condition_id=condition_id)
        if open_orders is None:
            print(f'closing connection (could not get orders for market {condition_id[:5]}).')
            break
        
        for order in open_orders:
            if order['side'].lower() == 'buy':
                buy_flag += 1

        try:
            async with websockets.connect(URL) as websocket:
                await websocket.send(json.dumps({"assets_ids": [token_1, token_2],"type": "market"}))

                async for msg in websocket:
                    data = json.loads(msg)
                    data = return_data(data)
                    if data['event_type'] == 'book':
                        bids, spread, token_to_use = parse_orderbook(data=data, 
                                                            token_1=token_1, 
                                                            token_2=token_2)
                        lowest_bid, bids_above_size, amount, midpoint = check_book(max_spread=max_spread, 
                                                                                spread=spread,
                                                                                bids_df=bids, 
                                                                                order_size=order_size,
                                                                                min_tick_size=min_tick_size)
                        temp_midpoint = midpoint
                        temp_token = token_to_use
                        if daily_rate != 0:
                            if lowest_bid > 0:
                                diff = amount - (min_size * lowest_bid)
                                size = min_size + round(math.floor(diff / lowest_bid), 1) if diff >= 0 else 0
                                if (1.5*size > bids_above_size) | (diff < 0): # dont place order / cancel if volume above order too low
                                    lowest_bid = 0

                            if buy_flag == 0:
                                if lowest_bid != 0:
                                    await asyncio.to_thread(place_order, 
                                                            client=client, 
                                                            price=lowest_bid, 
                                                            side='buy', 
                                                            size=size, 
                                                            token_id=token_to_use,
                                                            condition_id=condition_id)
                            elif buy_flag == 1:
                                order_size = open_orders[0]['size']
                                order_amount = order_size * open_orders[0]['price']
                                if open_orders[0]['side'].lower() == 'buy':
                                    if (open_orders[0]['price'] != lowest_bid) | ((order_amount < 0.9*amount) | (order_amount > 1.05*amount)):
                                        await asyncio.to_thread(cancel_order,
                                                                client=client,
                                                                order_id=open_orders[0]['id'])
                                        if lowest_bid != 0:
                                            await asyncio.to_thread(place_order, 
                                                                    client=client, 
                                                                    price=lowest_bid, 
                                                                    side='buy', 
                                                                    size=size, 
                                                                    token_id=token_to_use,
                                                                    condition_id=condition_id)
                    if data['event_type'] == 'price_change':
                        prices = []
                        flag = False
                        if temp_token == token_1:
                            min_price = (temp_midpoint - max_spread - 0.01) 
                            max_price = (temp_midpoint + max_spread + 0.01) 
                        else: 
                            min_price = ((1 - temp_midpoint) - max_spread - 0.01)
                            max_price = ((1 - temp_midpoint) + max_spread + 0.01) 
                        for order in data['changes']:
                            prices.append(float(order['price']))
                        for price in prices:
                            if (price > min_price) & (price < max_price):
                                flag = True
                        if flag:
                            break

        except websockets.exceptions.ConnectionClosedError as e:
            print(f"WebSocket connection closed: {e}")
            if buy_flag == 1:
                await asyncio.to_thread(cancel_order, client=client, order_id=open_orders[0]['id'])
            await asyncio.sleep(5)
        except asyncio.TimeoutError as e:
            print(f"WebSocket timeout: {e}")
            if buy_flag == 1:
                await asyncio.to_thread(cancel_order, client=client, order_id=open_orders[0]['id'])
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Unexpected error: {e}")
            if buy_flag == 1:
                await asyncio.to_thread(cancel_order, client=client, order_id=open_orders[0]['id'])
            await asyncio.sleep(5)


def process(client, market, min_size, daily_rate, max_spread, min_tick_size):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(handle_market(client=client,
                                              market=market,  
                                              min_size=min_size, 
                                              daily_rate=daily_rate, 
                                              max_spread=max_spread, 
                                              min_tick_size=min_tick_size))
    except KeyboardInterrupt:
        stop_event.set()
        resp = cancel_all_orders(client=client)
        if resp: print('Cancelled all orders due to keyboard interrupt in process')
    except asyncio.exceptions.CancelledError:
        print(f"Cancelled market processing for {market['condition_id'][:5]}.")
    except Exception as e:
        print(f'\nException in process: {e}\n')
    

def main():
    client = init_client()
    markets = return_markets(client=client)

    for i, market in enumerate(markets):
        condition_id = market['condition_id']
        token_1 = market['token_1']
        token_2 = market['token_2']
        min_size, daily_rate, max_spread, min_tick_size = get_market_data(client, market['condition_id'])
        print(f'Market {i + 1} ({condition_id[:5]}) with tokens {token_1[:5]} and {token_2[:5]} loaded.\n')
        
        p = Process(name=str(i), target=process, args=(client, market, min_size, daily_rate, max_spread, min_tick_size, ))
        p.start()
        processes.append(p)
        time.sleep(2)


if __name__ == '__main__':
    main()
