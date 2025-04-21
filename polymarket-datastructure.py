import json, time, math
import asyncio
import websockets
import pandas as pd
from py_clob_client.clob_types import TradeParams


from multiprocessing import Process, Event
# from support.variables import ids
from support.polymarket import init_client, get_orders, place_order, cancel_order, cancel_all_orders, return_markets

ids = ['0x7a18e4d613d7bf6afa06aa9eb1f9287ca81e841d77ae6d5fabdab37f0c0b5d6c' # will-bitcoin-reach-100k-in-april
       ]


URL = 'wss://ws-subscriptions-clob.polymarket.com/ws/market'
processes = []
stop_event = Event()


# Adjust order amounts as wanted. Comparing the number of bids above the lowest bids (eg. 75 - 700)
def logic(bids, lowest_bid):
    if bids[round(bids['price'], 3) > lowest_bid]['amount'].sum() <= 75:
        amount = 0
        lowest_bid = 0
    elif bids[round(bids['price'], 3) > lowest_bid]['amount'].sum() <= 100:
        amount = 30
    elif bids[round(bids['price'], 3) > lowest_bid]['amount'].sum() <= 150:
        amount = 60
    elif bids[round(bids['price'], 3) > lowest_bid]['amount'].sum() <= 225:
        amount = 75
    elif bids[round(bids['price'], 3) > lowest_bid]['amount'].sum() <= 450:
        amount = 105
    elif bids[round(bids['price'], 3) > lowest_bid]['amount'].sum() <= 700:
        amount = 150
    else:
        amount = 175
    return amount, lowest_bid


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
    
    if bid_lvls > 18: lowest_bid = round(relevant_bids.loc[18, 'price'], 4)
    elif bid_lvls > 15: lowest_bid = round(relevant_bids.loc[15, 'price'], 4)
    elif bid_lvls > 12: lowest_bid = round(relevant_bids.loc[12, 'price'], 4)
    elif bid_lvls > 9: lowest_bid = round(relevant_bids.loc[9, 'price'], 4)
    elif bid_lvls > 6: lowest_bid = round(relevant_bids.loc[6, 'price'], 4)
    elif bid_lvls > 4: lowest_bid = round(relevant_bids.loc[4, 'price'], 4)
    elif bid_lvls > 2: lowest_bid = round(relevant_bids.loc[len(relevant_bids) - 1, 'price'], 4)

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
    if midpoint <= 0.05: lowest_bid = 0

    bids_above_size = 1000000
    if lowest_bid != 0:
        bids_above_size = bids_df[round(bids_df['price'], 3) > lowest_bid]['size'].sum()

    amount, lowest_bid = logic(bids_df, lowest_bid)
    
    print(f'min_tick_size: {min_tick_size}, lowest_bid: {lowest_bid}, midpoint: {midpoint}, amount: {amount}, bid_lvls: {bid_lvls}, actual: {round(relevant_bids.loc[1, "price"], 3)}, \nrelevant_bids: {relevant_bids}')
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
            print(f'Closing connection (could not get orders for market {condition_id[:5]}).')
            break
        
        for order in open_orders:
            if order['side'].lower() == 'buy':
                buy_flag += 1 # Flag to check if we have an open buy order

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
                        
                        
                        print(f'Daily_rate: {daily_rate}, Lowest_bid: {lowest_bid}, Midpoint: {midpoint}, Amount: {amount}, Bids_above_size: {bids_above_size}')
                        
                        temp_midpoint = midpoint
                        temp_token = token_to_use
                        if daily_rate != 0:
                            if lowest_bid > 0:
                                diff = amount - (min_size * lowest_bid)
                                size = min_size + round(math.floor(diff / lowest_bid), 1) if diff >= 0 else 0 # Calculating the number of tokens to buy
                                if (1.5*size > bids_above_size) | (diff < 0): # Don't place order / cancel if volume above order too low
                                    lowest_bid = 0

                            if buy_flag == 0: # No open buy order, place an order if lowest_bid > 0
                                if lowest_bid != 0:
                                    await asyncio.to_thread(place_order, 
                                                            client=client, 
                                                            price=lowest_bid, 
                                                            side='buy', 
                                                            size=size, 
                                                            token_id=token_to_use,
                                                            condition_id=condition_id)
                            elif buy_flag == 1:
                                print (f'Re-evaluting Token: {open_orders[0].token_id[:5]}')
                                order_size = open_orders[0]['size']
                                order_amount = order_size * open_orders[0]['price']
                                if open_orders[0]['side'].lower() == 'buy':
                                    if (open_orders[0]['price'] != lowest_bid) | ((order_amount < 0.9*amount) | (order_amount > 1.05*amount)): # Cancel order if price or size changed
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
    markets = return_markets(client, ids)
    

    
    
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
