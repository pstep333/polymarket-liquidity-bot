from dotenv import load_dotenv
import os
from eth_account import Account

# Load environment variables from .env
load_dotenv()

key = os.getenv("PRIVATE_KEY")
funder = Account.from_key(key)

chain_id = 137
host = 'https://clob.polymarket.com'

ids = ['0xfc4c7a2af57acbbd42223ea7d6472aae124d73166b3b631ff9981496a2fe42d9', # Will the price of Ethereum be between $1600 and $1700 on Apr 25?
       '0xd89059ab7874993719630031e34f055ca68236eb9b82aed815fd42dc50d3638d' # Will the price of Ethereum be between $1500 and $1600 on Apr 25?
      ]
