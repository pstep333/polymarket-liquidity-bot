import os
import time
from py_clob_client.constants import POLYGON
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import SELL
from web3 import Web3
from polymarket import key, funder

rpc_url = "https://polygon-rpc.com" # Polygon rpc url 
priv_key = key
pub_key = funder # Polygon account public key corresponding to private key
chain_id = 137
host = "https://clob.polymarket.com"


# Create CLOB client and get/set API credentials
client = ClobClient(host, key=key, chain_id=chain_id)
client.set_api_creds(client.create_or_derive_api_creds())


## Create and sign a limit order buying
order_args = OrderArgs(
    price=0.24,
    size=50,
    side=SELL,
    token_id="16101717229067257909185717512999902009459932010607684571159203241254383422570",
    # There is a 1 minute of security threshold for the expiration field.
    # If we need the order to expire in 30 seconds the correct expiration value is:
    # now + 1 miute + 30 seconds
    expiration= int(time.time()) + 900
)
signed_order = client.create_order(order_args)

## GTD Order
resp = client.post_order(signed_order, OrderType.GTD)
print(resp)