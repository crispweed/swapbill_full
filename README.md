# Introduction

SwapBill is an 'embedded' cryptocurrency protocol and cryptocurrency, currently at the preview stage and hosted on the litecoin blockchain.

A reference client for SwapBill is provided, written in Python and using the litecoin reference client (litecoinQT or litecoind) as
as a backend for peer to peer network connectivity and block validation.

# Requirements

To run the SwapBill reference client you'll need:

* Python version 2.7, 3.2, 3.3 or 3.4
* The third party Python 'ecdsa' and 'requests' modules
* The litecoin reference client (litecoinQT or litecoind) set up and running as an RPC server

The code has been tested on Linux and Windows, but should work on any platform with support for the litecoin reference client and the
required Python dependencies.

# Setting up litecoinQT or litecoind as an RPC server

The SwapBill client can connect to either litecoind or litecoinQT as an RPC server (so with or without the QT graphical interface),
as long as this is configured appropriately, but from here on I'll use the term 'litecoind' generically to refer to either litecoind
or litecoinQT set up as an RPC server, and 'the client' to refer to the SwapBill reference client.

You can download installers for litecoind from <https://litecoin.org/>, or this can also be built from source (from <https://github.com/litecoin-project/litecoin>).

For the current preview version of the client, you'll need to tell litecoind to connect to the litecoin testnet (as opposed to mainnet),
and maintain a full transaction index.

The default location for the litecoind configuration file is `~/.litecoin/litecoin.conf` on Linux,
and something like `C:\Users\YourUserName\AppData\Roaming\LiteCoin\litecoin.conf` on Windows.

Create a litecoin.conf file in this default location (if not already present), and add some lines like the following:

    server=1
    testnet=1
    txindex=1
    rpcuser=litecoinrpc
    rpcpassword=somesecretpassword

(Change the password!)

To start the server you can then either launch litecoinQT (the graphical client) normally, or run litecoind from the command line.
If running litecoind, the -printtoconsole option can be used to get console output about what the server is doing.

If you already ran the reference client previously, against testnet and *without the txindex option* a reindexing operation will be required,
and you should get a message about this.
If running litecoinQT you should be able to just click OK to go ahead, or you can also call litecoind with the -reindex option to do this explicitly.

You can test the RPC server by making RPC queries from the command line, e.g.:

    ~/git/litecoin/src $ ./litecoind getbalance
    11914.15504872

(This RPC interface is very handy for interaction with the reference client generally, and for general troubleshooting.)

## A note about the txindex option

The txindex tells litecoind to include a full transaction index, which is required if you want to look up any arbitrary transaction in the blockchain history
by transaction ID.

Because of the way the SwapBill protocol works, with swapbill amounts associated directly with unspent outputs in the underlying blockchain,
the SwapBill client actually just needs to scan the transactions in each new block as it arrives,
and *doesn't* need to look up arbitrary transactions from further back in the blockchain history.

Unfortunately, the RPC interface to the litecoin reference client doesn't provide a way to query the transactions by block, and
the txindex option is then required, essentially, as a workaround to implement this specific query functionality.

It's possible, and quite straightforward, to patch the reference client source code to add an RPC method for querying the set of transactions in a given block,
without the txindex option needing to be set. The SwapBill client actually tests for the existance of a custom 'getrawtransactionsinblock' RPC method,
and uses this if available. (With this custom query no arbitrary transaction queries is required, and the txindex option can be left unset.)

# Running the client

There's no installation process for the client and you can just run this directly
from the downloaded source tree.
(You'll need to ensure that third party dependencies are met before running the client, or you'll get an error message telling you to do this.)

At the time of writing, the project is hosted on <https://github.com/crispweed/swapbill>, and you can get the client source code with:

```
~/git $ git clone https://github.com/crispweed/swapbill
Cloning into 'swapbill'...
remote: Counting objects: 52, done.
remote: Compressing objects: 100% (41/41), done.
remote: Total 52 (delta 9), reused 46 (delta 3)
Unpacking objects: 100% (52/52), done.
```

and then run the client with (e.g.):

```
~/git $ cd swapbill/
~/git/swapbill $ python Client.py get_balance
```

Or, if you don't have git, you can download the archive from <https://github.com/crispweed/swapbill/archive/master.zip>, extract to a new directory, and run from there.

If you don't have litecoind or litecoinQT running, or if you don't have the RPC interface set up correctly, you'll see something like:

```
~/git/swapbill $ python Client.py get_balance
Couldn't connect for remote procedure call, will sleep for ten seconds and then try again.
Couldn't connect for remote procedure call, will sleep for ten seconds and then try again.
(...repeated indefinitely)
```

But if you start the RPC server, the client should connect and complete the command from there.

If the RPC interface is working correctly you should see something like this:

```
~/git/swapbill $ python Client.py get_balance
Failed to load from cache, full index generation required (no cache file found)
State update starting from block 305846
Committed state updated to start of block 305886
In memory state updated to end of block 305906
Operation successful
balance : 0
```

## Testnet

For the current release the client is configured to work only with the litecoin testnet,
and only spend 'testnet litecoin' outputs.
Any swapbill balances created with the client are then all 'testnet swapbill'.

As with the bitcoin testnet (see <https://en.bitcoin.it/wiki/Testnet>), litecoin testnet coins are designed to be without value, and the same goes for testnet swapbill,
so you can try things out at this stage without spending any real litecoin.

From here on (and for the current release), wherever we talk about 'swapbill' or 'litecoin', this means 'testnet litecoin' and 'testnet swapbill'.

## Protocol subject to change

The purpose of this release is to solicit community feedback about a protocol in development.
The protocol and client interface implemented for the current release, and as described in this document, are not final,
and are subject to change.

# Basic operation

## Wallet organisation

When you run the client there are two different wallets to be aware of:
* the 'standard' litecoind wallet built in to litecoind, and
* a separate, independant wallet available and controlled only by the client.

The litecoind wallet is used mostly for 'backing' funds for dust outputs and transaction fees in the underlying blockchain,
but can also be used for special 'burn' transactions, and for litecoin payments that complete litecoin to swapbill exchanges.

The client then stores the keys for special SwapBill control outputs separately.
These are essentially outputs that control balances in the SwapBill protocol, and the client then also tracks the relevant outputs independantly of litecoind.

The client wallet can be found in the client data directory (by default a 'swapBillData' directory, created in the working directory when you start the client),
in 'wallet.txt'.
This file contains the private keys that control your swapbill balances, so don't send this file or reveal the contents to anyone,
unless you want them to be able to spend your swapbill, and make sure that the file is backed up securely!

## Creating swapbill by proof of burn

The only way to *create* swapbill is by 'proof of burn' (on the host blockchain).
Essentially, if you *destroy* some of the host currency (litecoin) in a specified way,
the swapbill protocol will credit you with a corresponding amount in swapbill.

There's some discussion of proof of burn [here](https://en.bitcoin.it/wiki/Proof_of_burn).

Although burning litecoin is not the recommended way of obtaining some initial swapbill, the proof of burn mechanism is quite important.
The key point here is that you're *always* able to create swapbill
by burning host currency, at a fixed price,
and this then provides a price cap for swapbill in terms of the host currency.

Let's take a look at how this works, then, first of all.

### Obtaining testnet litecoin

To create swapbill by proof of burn, you'll first of all need some litecoin to destroy.

For the current testnet only release you only need to get hold of testnet litecoin, of course,
and there are sites set up as 'faucets' for this purpose,
such as [here](http://testnet.litecointools.com/) or [here](http://kuttler.eu/bitcoin/ltc/faucet/).

It's also not so hard to get testnet litecoin directly by through the (CPU) mining functionality in litecoind.
(Use the ```setgenerate true``` RPC command to turn this on.)

### Burning

Once you have spendable litecoin, go ahead and use this to create some swapbill, with the client's 'burn' action.

```
~/git/swapbill $ python Client.py burn --amount 0.5
Loaded cached state data successfully
State update starting from block 305886
Committed state updated to start of block 305890
In memory state updated to end of block 305910
attempting to send Burn, destination output address=n1J6nWhxwJinMt1VtwrC38V4yzZ3qPvCbv, amount=50000000
Operation successful
transaction id : d70e2a95237c35235eb77f9d1491be64bb357a8a50f8ce88260053fabc095e02
```

Once this goes through you will have destroyed 0.5 litecoin, but in exchange you're credited with a corresponding amount of swapbill.

It's worth noting at this point that the SwapBill protocol includes a constraint on the minimum amount of swapbill associated with any
given SwapBill 'account', or output. This is a financial motivation for users to minimise the number of active swapbill outputs
to be tracked, and a discouragement for 'spam' outputs.
The constraint is currently set to exactly 10000000 satoshis, or 0.1 litecoin, and so that's the minimum amount we're allowed to burn.
(If you try to burn less, the client should refuse to submit the transaction and display a suitable error message.)

By default, queries such as get_balance only report the amount actually confirmed (with at least one confirmation) by the host blockchain,
and so if we try querying this straight away, we won't see any swapbill credited for this burn:

```
~/git/swapbill $ python Client.py get_balance
Loaded cached state data successfully
State update starting from block 305890
Committed state updated to start of block 305890
In memory state updated to end of block 305910
Operation successful
balance : 0
```

But we can use the -i option to force the query to include pending transactions (from the litecoind memory pool), and then we get:

```
~/git/swapbill $ python Client.py get_balance -i
Loaded cached state data successfully
State update starting from block 305890
Committed state updated to start of block 305890
In memory state updated to end of block 305910
in memory pool: Burn
 - 0.5 swapbill output added
Operation successful
balance : 0.5
```

And then, if we wait a bit to allow the transaction to go through, we can see this as a confirmed transaction:

```
~/git/swapbill $ python Client.py get_balance
Loaded cached state data successfully
State update starting from block 305890
Committed state updated to start of block 305891
in memory: Burn
 - 0.5 swapbill output added
In memory state updated to end of block 305911
Operation successful
balance : 0.5
```

Note that it can sometimes take a while for new blocks to be mined on the litecoin testnet,
depending on whether anyone is actually mining this blockchain, and if no one is mining (!) it can then take a while for swapbill transactions to be confirmed..

Burn transactions are necessary to create swapbill initially, but once some swapbill has been burnt and is in circulation
it's much better to exchange host currency for this swapbill,
and you'll get a better exchange rate this way. (We'll come back to look at the exchange functionality a bit later.)

## Aside: committed and in memory transactions

In the above output we can see different block counts for 'committed' and 'in memory' state, and it's worth taking a moment to explain this.

What's going on here is that the client commits state to disk to avoid spending time resynchronising on each invocation,
but with this committed state lagging a fixed number of blocks (currently 20) behind the actual current block chain end.

This mechanism enables the client to handle small blockchain reorganisations robustly, without overcomplicating the client code.
If there are blockchain reorganisations of more than 20 blocks this will trigger a full resynch,
but blockchain reorganisations of less than 20 blocks can be processed naturally starting from the committed state.

For transaction reporting during synchronisation:
* Transactions that are included in the persistent state cached to disk get prefixed by 'committed'.
* Transactions that are confirmed in the blockchain but not yet cached to disk get prefixed by 'in memory'. (When you run the client again, you'll normally see these transactions repeated, unless there was a blockchain reorganisation invalidating the transaction.)
* Transactions that are not yet confirmed in the blockchain, but present in the litecoind memory pool get get prefixed with 'in memory pool'.

## Making payments

To make a payment in swapbill, we use the 'pay' action.
As with bitcoin and litecoin,
the payment recipient first needs to generate a target address for the payment,
and we can do this with the 'get_receive_address' action:

```
~/git/swapbill $ python Client.py get_receive_address
...
Operation successful
receive_address : mtLEgRXJA2WhaSZiXpocacTbRb9HAn9Xs1
```

This is actually just a standard address for the host blockchain, but the client stores the corresponding private key in wallet.txt,
and will detect any swapbill outputs paying to this address and add the relevant amounts to your balance.

```
~/git/swapbill $ python Client.py pay --amount 0.1 --toAddress mtLEgRXJA2WhaSZiXpocacTbRb9HAn9Xs1
Loaded cached state data successfully
State update starting from block 305894
Committed state updated to start of block 305894
in memory: Burn
 - 0.5 swapbill output added
In memory state updated to end of block 305914
attempting to send Pay, change output address=mnR7MJH3aXJ6HBhkcVitersptTLioykkK4, destination output address=mtLEgRXJA2WhaSZiXpocacTbRb9HAn9Xs1, amount=10000000, maxBlock=305923
Operation successful
transaction id : 29755ec9c77b1141f7473e5e958e7ef96df7e92eccd939dbe8c702f18899ef43
```

In this case we're actually just paying ourselves.
It's also possible to manage multiple swapbill wallets independantly, by changing the client data directory,
and to use this to try out transactions between different wallet 'owners':

```
~/git/swapbill $ mkdir alice
~/git/swapbill $ python Client.py --dataDir alice get_receive_address
...
Operation successful
receive_address : mmdAwus4b6chWzvRtNVcL2YfxvWTeWUcq3
~/git/swapbill $ python Client.py -pay --amount 0.1 --toAddress mmdAwus4b6chWzvRtNVcL2YfxvWTeWUcq3
```

And then, in this case, the default wallet owner is debited the swapbill payment amount, and this is credited to 'alice'.

(Note that you need to create the new data directory before invoking the client. The client won't create this directory for you.)

## Trading swapbill for host currency

The swapbill protocol includes support for decentralised exchange between swapbill and the host currency, based on buy and sell
offer information posted on the block chain and with protocol rules for matching these buy and sell offers.

Three additional client actions (and associated transaction types) are provided for this exchange mechanism:
* post_ltc_buy
* post_ltc_sell
* complete_ltc_sell

Buying litecoin with swapbill is the most straightforward use case because this requires just one transaction to post a trade offer,
with the SwapBill protocol then taking over handling of the trade completely from there.

There are then two different kinds of litecoin sell offer.

'Backed' sell offers are the recommended method, when there are are 'backers' available.
In this case the backer has already committed a swapbill amount to cover the trade, so you just need to make one sell offer transaction,
and the backer then takes care of exchange completion payments.

When no backers are available, you can also make unbacked sell offers, but are then responsible for subsequent exchange completion payments yourself.

When trade offers go through, swapbill amounts are associated with the offers and paid out again when offers are matched, according to the SwapBill protocol rules.

In the case of buy offers this is the swapbill amount being offered in exchange for litecoin.

In the case of sell offers this is a deposit amount, in swapbill, currently set to 1/16 of the trade amount, which is held by the protocol and paid back on condition of successful completion.
If the seller completes the trade correctly then this deposit is refunded, but if the seller fails to make a completion payment after offers have been matched
then the deposit is credited to the matched buyer (in compensation for their funds being locked up during the trade).

Exchange rates are always fractional values between 0.0 and 1.0 (greater than 0.0 and less than 1.0), and specify the number of litecoins per swapbill
(so an exchange rate of 0.5 indicates that one litecoin exchanges for 2 swapbill).

A couple of other details to note with regards to trading:
* the sell offer transactions also require an amount equal to the protocol minimum balance constraint to be 'seeded' into the sell offer (but, unlike the deposit, this seed amount will be returned to the seller whether or not trades are successfully completed)
* trade offers are subject to minimum exchange amounts for both the swapbill and litecoin equivalent parts of the exchange
* trade offers may be partially matched, and litecoin sell offers can then potentially require more than completion transaction
* matches between small trade offers are only permitted where the offers can be matched without violating the minimum exchange amounts and minimum offer amounts for any remainder

The trading mechanism provided by SwapBill is necessarily fairly complex, and a specification of the *exact* operation of this mechanism is beyond the scope of this document,
but we'll show a concrete example of trading worked through in the client to show *how to use* the mechanism.

## Backed litecoin sell offer

Backed litecoin sell offers are actually the recommended way to obtain some initial swapbill, in preference to burn transactions.

As with burn transactions, no swapbill balance is required in order to make a backed litecoin sell offer,
but this does depend on some backing amount having already been committed by a third party, and some commission is payable to the backer for these transactions.

(Because commission is paid to backer, with the rate of commission subject to market forces, *if* there is swapbill available for exchange then there *should* be backers available,
otherwise this is an indication that swapbill supply is insufficient, and so creating more swapbill by burning is appropriate!)

You can use the 'get_ltc_sell_backers' action to check if there are backers available,
and to find out information about the backers such as rate of commission being charged, as follows:

```
~/git/swapbill $ python Client.py get_ltc_sell_backers
...
Operation successful
ltc sell backer index : 0
    blocks until expiry : 9952
    I am backer : False
    backing amount : 1000
    expires on block : 315881
    commission : 0.01
    maximum per transaction : 10
```

The commission value here indicates that 1% commission is payable to the backer on the amount of ltc offered for sale.

Apart from that, the important values to look at are backing amount value and maximum per transaction.

The backed trade mechanism provided by SwapBill essentially works by backers committing funds to guarantee trades for a certain number of transactions in advance.

From the numbers here, we can see that the backer has enough funds currently committed to guarantee at least 100 trade transaction.
But, if 100 other valid trade transactions to the same backer all come through between the backers query and our backed sell transaction actually
coming through on the blockchain, it's theoretically possible for us to lose our ltc payment amount.

With a larger backing amount, or a smaller maximum amount per transaction, more transactions would be guaranteed, making this scenario less probable.

Lets go ahead and exchange some litecoin for swapbill through this backer, however.





## Trading example

The client uses the term 'buy' to refer to buying litecoin with swapbill,
and 'sell' to refer to selling litecoin for swapbill, and we'll use the same convention here.

So a 'buyer' has some swapbill, and wants to exchange for litecoin:

```
~/git/swapbill $ python Client.py --dataDir buyer get_balance
...
Operation successful
active : 100000000
spendable : 100000000
total : 100000000
```

To check the list of sell offers currently active on the block chain:

```
~/git/swapbill $ python Client.py --dataDir buyer get_sell_offers
Loaded cached state data successfully
...
Operation successful
exchange rate : 0.919999999925
    swapbill desired : 13400000
    deposit paid : 837500
    mine : False
    ltc equivalent : 12327999
exchange rate : 0.899999999907
    swapbill desired : 10000000
    deposit paid : 625000
    mine : False
    ltc equivalent : 8999999
exchange rate : 0.889999999898
    swapbill desired : 1800000
    deposit paid : 112500
    mine : False
    ltc equivalent : 1601999
```

Higher exchange rates are better for our buyer.

Our buyer is ok with each swapbill being valued at 0.919 litecoin, and goes ahead and posts a buy offer.

```
 ~/git/swapbill $ python Client.py --dataDir buyer post_ltc_buy --swapBillOffered 10000000 --exchangeRate 0.919
...
In memory state updated to end of block 283672
attempting to send LTCBuyOffer, change output address=mtTgHycMu7H4k7CTsk1mPLCRSYzLdPsRLi, ltcBuy output address=mtbXpS62QTuiZMicZ5H34eCW2BWfxVRdjN, exchangeRate=3947074945, maxBlock=283681, receivingAddress=mzA3C8icRRpWH8bpiFvzMiPGYKRyq2uRM1, sourceAccount=(u'e35e9a1dd74a825b4cec7ceb267cc746f22f8a2dee316f032d01f08eb7d92486', 1), swapBillOffered=10000000
Operation successful
transaction id : b0e88c6d9e7969f3ebbd7738dfd5cc42f245e03a5ab75dbfc5f20db6764ad74e
```

We check sell offers again immediately, and these are unchanged, with our buy offer still in the memory pool:

```
~/git/swapbill $ python Client.py --dataDir buyer get_sell_offers
Loaded cached state data successfully
...
In memory state updated to end of block 283672
in memory pool: LTCBuyOffer
 - 100000000 swapbill output consumed
Operation successful
exchange rate : 0.919999999925
    swapbill desired : 13400000
    deposit paid : 837500
    mine : False
    ltc equivalent : 12327999
exchange rate : 0.899999999907
    swapbill desired : 10000000
    deposit paid : 625000
    mine : False
    ltc equivalent : 8999999
exchange rate : 0.889999999898
    swapbill desired : 1800000
    deposit paid : 112500
    mine : False
    ltc equivalent : 1601999
```

But in the next block, the transaction goes through:

```
thomas@Z77A-MINT15 ~/git/swapbill $ python Client.py --dataDir buyer get_sell_offers
Loaded cached state data successfully
State update starting from block 283653
Committed state updated to start of block 283654
in memory: Burn
 - 100000000 swapbill output added
in memory: LTCBuyOffer
 - 100000000 swapbill output consumed
 - 80000000 swapbill output added
 - created buy offer, refund output seeded with 10000000 swapbill and locked until trade completed
In memory state updated to end of block 283674
Operation successful
exchange rate : 0.919999999925
    swapbill desired : 3400000
    deposit paid : 212500
    mine : False
    ltc equivalent : 3127999
exchange rate : 0.899999999907
    swapbill desired : 10000000
    deposit paid : 625000
    mine : False
    ltc equivalent : 8999999
exchange rate : 0.889999999898
    swapbill desired : 1800000
    deposit paid : 112500
    mine : False
    ltc equivalent : 1601999
```

So we can see that no other buy offers were madein this time, and (as long as there are no subsequent blockchain reorganisations) our offer has been matched against
the top sell offer, and the amount of the top sell offer reduced accordingly.

Note the line in our transaction reports about a refund output being seeded and locked until trade complete.
And we can see this, also, when we check our balance:

```
~/git/swapbill $ python Client.py --dataDir buyer get_balance
...
In memory state updated to end of block 283675
Operation successful
active : 80000000
spendable : 80000000
total : 90000000
```

This shows that 10000000 satoshis of our total balance is not 'spendable'.
What's happened here is that an output has been created for the trade.
This output will be credited with a refund of our swapbill in trading, plus the seller's deposit, if the trade is not completed by the seller.
And the output is locked (in the SwapBill protocol) because the trade is still active, and can potentially pay more swapbill in to the output.

If we check the current list of buy offers, our offer is not listed, because this has already been matched (it was matched immediately against an existing sell offer):

```
~/git/swapbill $ python Client.py --dataDir buyer get_buy_offers
...
In memory state updated to end of block 283677
Operation successful
No entries
```

There is now a 'pending exchange' generated by our trade offer, however, and we can see this with the get_pending_exchanges query:

```
~/git/swapbill $ python Client.py --dataDir buyer get_pending_exchanges
...
In memory state updated to end of block 283677
Operation successful
pending exchange index : 2
    I am seller (and need to complete) : False
    outstanding ltc payment amount : 9194999
    swap bill paid by buyer : 10000000
    expires on block : 283724
    I am buyer (and waiting for payment) : True
    deposit paid by seller : 625000
```

We just need to wait for the seller to complete the exchange, with the exchange completion including a payment of the outstanding litecoin amount listed.
If the seller doesn't complete the exchange before block 283724 then the SwapBill protocol will refund us the amount of swapbill paid, plus the deposit of 625000.

## Selling litecoin for swapbill

The process for selling litecoin is similar, but with a second transaction required for exchange completion.

So, a 'seller' has some litecoin, and wants to exchange for swapbill.

The seller needs some swapbill to seed a receive output for the trade, and to pay a deposit.

```
~/git/swapbill $ python Client.py --dataDir seller get_balance
...
Operation successful
active : 20000000
spendable : 20000000
total : 20000000
```

A receive output will be required for the trade, and a minimum balance of 10000000 will be required to seed that output,
leaving 10000000 available for a trade deposit.

The deposit is calculated as a fixed fraction of the swapbill amount being traded, with this fraction set by the SwapBill protocol, and currently fixed at 1/16.
So this balance will enable us to exchange litecoin for a further 160000000 swapbill.

To check the list of buy offers currently active on the block chain:

```
~/git/swapbill $ python Client.py --dataDir seller get_buy_offers
...
Operation successful
exchange rate : 0.931999999797
    ltc equivalent : 112771999
    mine : False
    swapbill offered : 121000000
exchange rate : 0.949999999953
    ltc equivalent : 80337699
    mine : False
    swapbill offered : 84566000
```

Lower exchange rates are better for the seller.

The seller wants to value each swapbill at 0.925 litecoin (so below the lowest existing buy offers), and goes ahead and posts an offer.

```
~/git/swapbill $ python Client.py --dataDir seller post_ltc_sell --swapBillDesired 160000000 --exchangeRate 0.925 --blocksUntilExpiry 4
...
In memory state updated to end of block 283686
attempting to send LTCSellOffer, change output address=mtaJf1mTHsjXW97aoNQmT5ALhW6EwBZHsT, ltcSell output address=mx4hbMPDUALfF4D7YdeAAw4rUFADdbjsSQ, exchangeRate=3972844748, maxBlock=283691, sourceAccount=(u'4473ef0aca2d3750ae19c525a7ca4db66dbd96f71af0caf6a460d94eb186899b', 1), swapBillDesired=160000000
Operation successful
transaction id : ff0cf83f1523074883f5e433f05326a60548a48a2f41919eb4989411e57f145c
```

Note that we've set an additional blocksUntilExpiry option here.
This option defaults to a fairly low value, but it can be quite important to control this value when making litecoin sell transactions,
since we'll need to make sure we watch for matches and submit the corresponding completion transactions.
By making the offer expire within a small number of blocks we can limit the time during which we need to check for matches,
although this also gives buyers less time to make matching offers.

Our sell offer goes through in the next mined block, but is not matched, because it is lower than the existing buy offers, and now appears on the list of sell offers.

```
~/git/swapbill $ python Client.py --dataDir seller get_sell_offers
...
In memory state updated to end of block 283687
Operation successful
exchange rate : 0.924999999814
    swapbill desired : 160000000
    deposit paid : 10000000
    mine : True
    ltc equivalent : 147999999
exchange rate : 0.919999999925
    swapbill desired : 3400000
    deposit paid : 212500
    mine : False
    ltc equivalent : 3127999
...
```

The exchange rate value shown is slightly different to the exchange rate we specified in the offer because
exchange rates are represented internally by the client (and in the SwapBill protocol) as integer values, and there was some rounding in the post_offer_action.

In the next block, some one makes a buy offer that matches our offer, but with a smaller amount, and our offer is therefore *partially matched*.

```
~/git/swapbill $ python Client.py --dataDir seller get_sell_offers
...
In memory state updated to end of block 283689
Operation successful
exchange rate : 0.924999999814
    swapbill desired : 147700000
    deposit paid : 9231250
    mine : True
    ltc equivalent : 136622499
exchange rate : 0.919999999925
    swapbill desired : 3400000
    deposit paid : 212500
    mine : False
    ltc equivalent : 3127999
...
```

And we can see that a new pending exchange is now listed for our offer.

```
~/git/swapbill $ python Client.py --dataDir seller get_pending_exchanges
...
In memory state updated to end of block 283689
Operation successful
pending exchange index : 3
    I am seller (and need to complete) : True
    outstanding ltc payment amount : 11377499
    swap bill paid by buyer : 12300000
    expires on block : 283739
    I am buyer (and waiting for payment) : False
    deposit paid by seller : 768750
```

We now have a fixed number of blocks in which to complete the trade before this pending exchange expires.
(The SwapBill protocol currently fixes this at 50 blocks from the block in which trade offers are matched.)

To complete the exchange we use the complete_ltc_sell action.

```
~/git/swapbill $ python Client.py --dataDir seller complete_ltc_sell --pendingExchangeID 3
...
In memory state updated to end of block 283689
attempting to send LTCExchangeCompletion, destinationAddress=mg7a3nRjWnAw9EP2f11g38uMk3JAENroXR, destinationAmount=11377499, pendingExchangeIndex=3
Operation successful
transaction id : abe86fd9a17b1b27f8f302b398995d20c2f6366590484f7feee2670db580a831
```

Once the completion transaction has gone through, we can see that we have been credited with swapbill for the partial exchange:

```
~/git/swapbill $ python Client.py --dataDir seller get_balance
...
In memory state updated to end of block 283690
Operation successful
active : 0
spendable : 0
total : 23068750
```

We need to watch for further matches, and complete as necessary, until the sell offer has expires.
This happens a few blocks later, and we can then see the unmatched swapbill refunded to our balance.

```
 ~/git/swapbill $ python Client.py --dataDir seller get_balance
Loaded cached state data successfully
State update starting from block 283671
Committed state updated to start of block 283671
...
in memory: LTCSellOffer
 - 20000000 swapbill output consumed
 - created sell offer, receiving output seeded with 10000000 swapbill and locked until trade completed
in memory: LTCBuyOffer
 - sell offer updated (receiving output contains 10000000 swapbill)
in memory: LTCExchangeCompletion
 - sell offer updated (receiving output contains 23068750 swapbill)
trade offer or pending exchange expired
In memory state updated to end of block 283691
Operation successful
active : 32300000
spendable : 32300000
total : 32300000
```
