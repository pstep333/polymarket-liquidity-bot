import httpx
import pandas as pd


gamma_url = "https://gamma-api.polymarket.com"
gamma_markets_endpoint = gamma_url + "/markets?start_date_min=2024-11-10T00:00:00Z"
gamma_events_endpoint = gamma_url + "/events?start_date_min=2024-11-10T00:00:00Z"


def get_markets(querystring_params={}):
    response = httpx.get(gamma_markets_endpoint, params=querystring_params)
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print(f"Error response returned from api: HTTP {response.status_code}")
        raise Exception()
        

def get_all_current_markets(limit=100):
    offset = 0
    all_markets = []
    while True:
        params = {
            "active": True,
            "closed": False,
            "archived": False,
            "limit": limit,
            "offset": offset,
        }
        market_batch = get_markets(querystring_params=params)
        all_markets.extend(market_batch)

        if len(market_batch) < limit:
            break
        offset += limit

    return all_markets


def return_latest_markets():
    all_markets = get_all_current_markets()
    df = pd.DataFrame()
    for market in all_markets:
        df_dictionary = pd.DataFrame([market])
        df = pd.concat([df, df_dictionary], ignore_index=True)
    df['startDate'] = pd.to_datetime(df['startDate'])
    sorted_markets = df.sort_values(by='startDate', ascending=False).reset_index()
    
    for i, _ in sorted_markets.iterrows():
        sorted_markets.loc[i, 'event_id'] = sorted_markets.loc[i, 'events'][0]['id']

    return sorted_markets


def get_events(querystring_params={}):
    response = httpx.get(gamma_events_endpoint, params=querystring_params)
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        raise Exception()
        

def get_current_events(limit=100):
    offset = 0
    all_events = []
    while True:
        params = {
            "active": True,
            "closed": False,
            "archived": False,
            "limit": limit,
            "offset": offset,
        }
        event_batch = get_events(querystring_params=params)
        all_events.extend(event_batch)

        if len(event_batch) < limit:
            break
        offset += limit
    
    return get_events(querystring_params=params)


def return_latest_events():
    all_events = get_current_events()
    df_temp = pd.DataFrame()
    for event in all_events:
        df_dictionary_temp = pd.DataFrame([event])
        df_temp = pd.concat([df_temp, df_dictionary_temp], ignore_index=True)
    df_temp['startDate'] = pd.to_datetime(df_temp['startDate'])
    sorted_events = df_temp.sort_values(by='startDate', ascending=False).reset_index()
    
    return sorted_events


def return_event_condition_id(events_ids, binary_only=True):
    sorted_markets = return_latest_markets()

    condition_ids = []
    for id in events_ids:
        markets_of_event = sorted_markets[sorted_markets['event_id'] == id]['conditionId']
        if binary_only:
            if len(markets_of_event) == 1: # only keep binary markets
                for m in markets_of_event:
                    condition_ids.append(m)
        else: 
            for m in markets_of_event:
                condition_ids.append(m)
    
    return condition_ids


def main():
    sorted_events = return_latest_events()
    print(sorted_events.iloc[0]['markets'])
    last_events_ids = sorted_events['id'].head(10)
    condition_ids = return_event_condition_id(last_events_ids, binary_only=False)
    return condition_ids
    

if __name__ == '__main__':
    ids = main()
    print(ids)
