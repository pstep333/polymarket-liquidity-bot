<h1> polymarket-liquidity-bot </h1>
<h3> Farm liquidity rewards on Polymarket </h3>


Farm 'liquidity rewards' by placing orders without ever getting them filled. It works by making sure you never have the top order on the orderbook while being close enought to that level with your placed order to be eligible to obtain liquidity rewards. The bot will place and cancel orders on any active market on Ploymarket you select. Every market is handled by another CPU core assuring minimal delay in response time while trading on multiple markets.

*Results may vary*

---

To use, after cloning the repo, start by installing the required packages by running: 

`pip install -r requirements.txt`.

Then, navigate to the support/variables.py file. Fill in your private key and public address (retreive from Polymarket).

Use the get_ids.py file to get the id's of the markets you want to place orders on. Run the file (`python support/get_ids.py`) and give 1 or 2 keywords of the market you want (for example: trump, election).

Copy the id from the output and paste it in the ids list in the variables.py file. (For optimal use, don't give more id's than CPU cores though the impact should be relatively small). 

I found that rate limits kick in - depending on how active the markets are - at around 12 markets (the bot cancels all orders on a market when it is rate limited, resulting in less optimal performance)

All that's left now is running the app.py file (`python app.py`).

<h5>The bot always places orders on the side (yes or no) that has a probability less than 50%. If the probability is below 10%, no orders will be placed as rewards have to be earned by taking both sides of the order book at this point.*</h5>



