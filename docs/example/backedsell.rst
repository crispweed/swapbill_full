Backed sell transactions
=========================

A backed sell transaction enables you to sell host currency for swapbill (to obtain some initial swapbill, for example), with just one single sell offer transaction.

Backed sell transactions are actually the recommended way to obtain some initial swapbill, in preference to burn transactions.

As with burn transactions, no swapbill balance is required in order to make a backed sell offer,
but this does depend on some backing amount having already been committed by a third party, and some commission is payable to the backer for these transactions.

(Because commission is paid to backer, with the rate of commission subject to market forces, *if* there is swapbill available for exchange then there *should* be backers available,
otherwise this is an indication that swapbill supply is insufficient, and so creating more swapbill by burning is appropriate!)

Checking backers
-----------------

You can use the 'get_sell_backers' action to check if there are backers available,
and to find out information about the backers such as rate of commission being charged, as follows::


    ~/git/swapbill $ python Client.py get_sell_backers
    ...
    Operation successful
    host coin sell backer index : 0
        backing amount : 190
        blocks until expiry : 29872
        maximum exchange swapbill : 0.17788235
        I am backer : False
        backing amount per transaction : 0.19
        expires on block : 309437
        commission : 0.005


The commission value here indicates that 0.5% commission is payable to the backer on the amount of host coin offered for sale.

Apart from that, the important values to look at are backing amount value and maximum per transaction.

The backed trade mechanism provided by SwapBill works by backers committing funds to guarantee trades for a certain number of transactions in advance.

From the numbers here, we can see that the backer has enough funds currently committed to guarantee at least 1000 trade transaction.
(This is worked out as 'backing amount' divided by 'maximum per transaction'.)

What this means is that if 1000 other valid trade transactions to the same backer all come through on the blockchain
in between this backer query and our backed sell transaction,
it's theoretically possible for us to lose our host currency payment amount.
But, as long as our sell transaction comes through to the blockchain with *less than* 1000 other transactions
to the same backer getting in first, SwapBill uses the funds committed by the backer to guarantee our exchange.

Lets go ahead and exchange some host coin for swapbill through this backer.

Listing buy offers
-------------------

The next step is to check the buy offers currently posted to the blockchain, to get an idea of the current excange rate:


    ~/git/swapbill $ python Client.py get_buy_offers
    ...
    Operation successful
    exchange rate : 0.92
        mine : True
        swapbill offered : 1.1
        host coin equivalent : 1.012
    exchange rate : 0.95
        mine : True
        swapbill offered : 2
        host coin equivalent : 1.9


The best offer comes first, with 1.1 swapbill offered at an exchange rate of 0.92 host coin per swapbill.
So let's assume we're ok with making an exchange at this rate, but we actually want to exchange a bit more than 1.1 host coin.

```
~/git/swapbill $ python Client.py post_ltc_sell --hostCoinOffered 4 --exchangeRate 0.92 --backerID 0
Loaded cached state data successfully
State update starting from block 306244
Committed state updated to start of block 306247
In memory state updated to end of block 306267
attempting to send BackedSellOffer, sellerReceive output address=msUkYfCkH8vdQGp1TmsnEm8Pm5vgEARBHb, backerIndex=0, backerHostCoinReceiveAddress=mo4DLT1a7ZhBRZTrXYXs9BRu6efyzrXmM1, exchangeRate=920000000, hostCoinOfferedPlusCommission=404000000
Operation successful
transaction id : 81e8bd072c386fa3b0744779083e98626de6f57719a025b8ae1115230c902fed
```

Note that, by default, backers commission will be added to the amount specified here for hostCoinOffered.
So, in this case, we'll actually pay 4.04 litecoin in to this transaction.
If we want to specify an amount to be paid *including backer commission* then we can do this by setting the --includesCommission flag.

After a short delay, this transaction goes through:

```
~/git/swapbill $ python Client.py get_balance
Loaded cached state data successfully
State update starting from block 306248
Committed state updated to start of block 306249
in memory: BackedSellOffer
 - 1.2 swapbill output added
In memory state updated to end of block 306269
Operation successful
balance : 1.2
```

So we can see that our offer has been matched directly against the highest buy offer, and we've been credited the corresponding swapbill amount immediately.
(This was credited to us by the SwapBill protocol directly from the backer funds.)

We can see that the top buy offer has been removed:

```
~/git/swapbill $ python Client.py get_buy_offers
...
In memory state updated to end of block 306269
Operation successful
exchange rate : 0.95
    ltc equivalent : 0.38
    mine : False
    swapbill offered : 0.4
```

The top buy offer didn't fully match our offer, however, and so some of our sell offer remains outstanding:

```
~/git/swapbill $ python Client.py get_sell_offers
...
Operation successful
exchange rate : 0.92
    mine : False
    ltc offered : 2.896
    deposit : 0.19673914
    backer id : 0
    swapbill equivalent : 3.14782609
```

Note that this is not reported as being 'our' offer, because the offer is actually now the responsibility of the backer.
The deposit amount quoted here was actually paid by the backer, because the backer is responsible for completing the exchange
with each matched buyer.
And we don't need to worry about whether or not exchanges are completed successfully by the backer, because we're credited directly from backer funds
(by the SwapBill protocol) as soon as offers are matched.

We do need to wait until a buy offer comes along to match the remaining part of our sell offer, however.
This offer will never expire and there is no way for us to cancel the offer,
short of posting a matching buy offer ourself, so it's generally a good idea to only make offers that are likely to be matched directly when using the backed exchange mechanism,
if you're in a hurry to receive the swapbill!

Fortunately someone comes along and makes a matching buy offer:

```
~/git/swapbill $ python Client.py get_balance
Loaded cached state data successfully
State update starting from block 306252
Committed state updated to start of block 306253
in memory: BackedSellOffer
 - 1.2 swapbill output added
in memory: BuyOffer
 - trade offer completed
In memory state updated to end of block 306273
Operation successful
balance : 4.34782609
```
