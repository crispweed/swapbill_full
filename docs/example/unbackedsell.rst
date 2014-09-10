Unbacked sell transactions
===========================

In addition to the backed litecoin sell offers, it's also possible to make *unbacked* sell offers.

The key differences between the two types of sell offer are that:

* some initial swapbill is required in order to make an unbacked sell offer
* in the case of an unbacked sell offer, it is up to the seller to make final completion payments for each trade offer match
* a deposit is payed in to unbacked sell offers, and will be lost if the final completion payment is not made (e.g. if your internet goes down, or something like this!)
* backed sells only require one transaction from the seller, and there is no risk to the seller after that transaction has gone through
* backed sells are based on a lump sum committed to the SwapBill protocol by the backer, however, and then only guarantee offers up to a maximum number of transactions, and there is a theoretical possibility for lots of transactions to come through an consume all of the backer amount
* some commission is payable to the backer for each backed sell offer
* unbacked sells have an expiry period, which can be set when you make the offer
* backed sells never expire

Roughly speaking, backed ltc sells are good for smaller transactions, and are the best way to obtain swapbill initially,
but for larger transactions, and if you can be confident about being able to submit completion transactions
(e.g. if you have a backup internet connection!) then unbacked sells can be preferrable.

To make an unbacked sell offer we start with a sell_offer action, as before, but in this case we *don't* specify a value for backerID
(and so don't need to check for backers and backer details).

Our seller starts with some swapbill::

    ~/git/swapbill $ python Client.py get_balance
    ...
    Operation successful
    balance : 3.00531212

Checking buy offers
--------------------

As before, we check the current set of buy offers:

```
 ~/git/swapbill $ python Client.py get_buy_offers
...
Operation successful
exchange rate : 0.95
    ltc equivalent : 0.38
    mine : False
    swapbill offered : 0.4
exchange rate : 0.96
    ltc equivalent : 0.61542028
    mine : False
    swapbill offered : 0.64106279
```

Let's try and match the top offer:

```
~/git/swapbill $ python Client.py post_ltc_sell --hostCoinOffered 0.38 --exchangeRate 0.95
...
attempting to send SellOffer, hostCoinSell output address=mrshs7hscqVPHCiFshM3cetm4JHomiEsKQ, exchangeRate=950000000, hostCoinOffered=38000000, maxBlock=306302
Operation successful
transaction id : 650a80a27c9170f9f0d0a59c7646db91e874bb84edfda24d69aaecfe76eae64b
```

This goes through successfully, and we can see that the buy offer has been matched:

```
~/git/swapbill $ python Client.py get_buy_offers
...
in memory: SellOffer
 - 0.1 swapbill output consumed
 - 4.34782609 swapbill output consumed
 - 4.42282609 swapbill output added
In memory state updated to end of block 306300
Operation successful
exchange rate : 0.96
    ltc equivalent : 0.61542028
    mine : False
    swapbill offered : 0.64106279
```

The amount of swapbill offered, plus a deposit, have been taken from our current balance, but also a
seed amount equivalent to the minimum balance protocol constraint (currently set to 0.1 swapbill):

```
~/git/swapbill $ python Client.py get_balance
...
in memory: SellOffer
 - 0.1 swapbill output consumed
 - 4.34782609 swapbill output consumed
 - 4.42282609 swapbill output added
In memory state updated to end of block 306303
Operation successful
balance : 9.43393721
```

Now it is up to us to complete.
We can see the pending exchange with get_pending_exchanges:

```
 ~/git/swapbill $ python Client.py get_pending_exchanges
...
in memory: SellOffer
 - 0.1 swapbill output consumed
 - 4.34782609 swapbill output consumed
 - 4.42282609 swapbill output added
In memory state updated to end of block 306300
Operation successful
pending exchange index : 6
    blocks until expiry : 50
    I am seller (and need to complete) : True
    outstanding ltc payment amount : 0.38
    swap bill paid by buyer : 0.4
    expires on block : 306350
    I am buyer (and waiting for payment) : False
    deposit paid by seller : 0.025
```

It's probably a good idea to wait for a few more blocks to go through before completing the exchange, in case of blockchain reorganisation.
(This is more of an issue for completion transactions than other transactions, and something that backers will normally worry about for you, in the case of backed sells!)

Note that 'blocks until expiry' starts at 50 blocks in the current protocol definition, and we can infer the number of confirmations from this.
A bit later on we can see the pending exchange with 47 blocks left to expiry, and decide to go ahead with the exchange.

```
 ~/git/swapbill $ python Client.py get_pending_exchanges
...
in memory: SellOffer
 - 0.1 swapbill output consumed
 - 4.34782609 swapbill output consumed
 - 4.42282609 swapbill output added
In memory state updated to end of block 306303
Operation successful
pending exchange index : 6
    blocks until expiry : 47
    I am seller (and need to complete) : True
    outstanding ltc payment amount : 0.38
    swap bill paid by buyer : 0.4
    expires on block : 306350
    I am buyer (and waiting for payment) : False
    deposit paid by seller : 0.025
```

The actual completion transaction is then straightforward:

```
~/git/swapbill $ python Client.py complete_ltc_sell --pendingExchangeID 6
...
In memory state updated to end of block 306303
attempting to send ExchangeCompletion, destinationAddress=mmn38D6EaMSoF5wFpg4Nns3GZMgzbXMUu9, destinationAmount=38000000, pendingExchangeIndex=6
Operation successful
transaction id : 0481db0e3d529f5d17b1709ddc8007c7ceb7fceb57b4433e98d677b13cc5e35b
```

Once this transaction has gone through we're refunded the deposit, and the seed amount,
and credited the swapbill amount corresponding to our exchange:

```
~/git/swapbill $ python Client.py get_balance
...
in memory: ExchangeCompletion
 - trade offer completed
In memory state updated to end of block 306304
Operation successful
balance : 9.85893721
```
