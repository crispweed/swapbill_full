# Requirements

The SwapBill client is written in Python and supports Python versions 2.7, 3.2, 3.3 and 3.4.

The third party Python 'ecdsa' and 'requests' modules are required and must be installed.

The client uses the litecoin reference client (litecoinQT or litecoind) as a backend, and so this reference client must also be installed.

The client has been tested on Linux and Windows, but should work on any platform which supports the litecoin reference client and the
required Python dependencies.

# Setting up litecoinQT or litecoind as an RPC server

You can get the reference client from <https://litecoin.org/>.

The SwapBill client connects to the reference client with RPC calls, and so we need to ensure that this set up as an RPC server.

The reference client should then also connect to the litecoin testnet (as opposed to mainnet), and maintain a full transaction index.

To set this up, create a litecoin.conf file in the default location (if you don't already have one), and add some lines like the following:

    server=1
    testnet=1
    txindex=1
    rpcuser=litecoinrpc
    rpcpassword=somesecretpassword

(Change the password!)

The default location for this file on Linux is `~/.litecoin/litecoin.conf`,
while on Windows it looks like this is located at the path corresponding to `C:\Users\YourUserName\AppData\Roaming\LiteCoin\litecoin.conf`,
depending on your system setup.

To start the server you can then either launch litecoinQT (the graphical client) normally, or run litecoind from the command line.
If running litecoind, the -printtoconsole option can be used to get console output about what the server is doing.

If you already ran the reference client previously, against testnet, *without the txindex option* a reindexing operation will be required,
you should get a message about this.
If running litecoinQT you should be able to just click OK to go ahead, or you can call litecoind with the -reindex option to do this explicitly.

You can test the RPC server by making RPC queries from the command line, e.g.:

    ~/git/litecoin/src $ ./litecoind getbalance
    11914.15504872

(This RPC interface is very handy for interaction with the reference client generally, and for general troubleshooting.)

# Running the client

There's no installation process for the client, currently, and instead this just runs directly
from the downloaded source tree.
(You'll need to ensure that third party dependencies are met, before running the client, or you'll get an error message telling you to do this.)

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
State update starting from block 280696
Committed state updated to start of block 283286
In memory state updated to end of block 283306
Operation successful
active : 0
spendable : 0
total : 0
```

# Basic operation

## Testnet

For the current release the client is configured to work only with the litecoin testnet,
and only spend 'testnet litecoin' outputs, and any swapbill balances created with the client are then all 'testnet swapbill'.

As with the bitcoin testnet, litecoin testnet coins are designed to be without value, and the same then goes for testnet swapbill,
so you can try things out at this stage without spending any real litecoin.

From here on, wherever we talk about 'swapbill' or 'litecoin', for the current release this means 'testnet litecoin' and 'testnet swapbill'.

## Wallet organisation

From here on, also, we'll refer to the litecoin reference client simply as litecoind, and the SwapBill client as just 'the client'.
(The client doesn't care whether RPC requests are served by litecoind or litecoinQT, and you can use these interchangeably.)

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

(There's some discussion of proof of burn [here](https://en.bitcoin.it/wiki/Proof_of_burn).)

To create some swapbill in this way, first of all you'll need some litecoin.

For the current testnet only release, you can get some litecoin from a faucet,
such as [here](http://testnet.litecointools.com/) or [here](http://kuttler.eu/bitcoin/ltc/faucet/),
but it also seems fairly easy at the moment to get testnet litecoin directly by mining.
For this you can simply use the ```setgenerate true``` RPC command to turn on mining in litecoind.

Once you have spendable litecoin you can go ahead and use this to create some swapbill with the client's 'burn' action.

```
~/git/swapbill $ python Client.py burn --amount 10000000
Loaded cached state data successfully
State update starting from block 283276
Committed state updated to start of block 283346
In memory state updated to end of block 283366
attempting to send Burn, destination output address=myLej8rPxBF2ZE5ST2YVDpnA7Dwjh8fbRA, amount=10000000
Operation successful
transaction id : 01e436f2d26827dd9bd35b01e08a7aa4676b118284113b23ce3f0e5eac645cb6
```

The amount here is in satoshis, so this just destroyed 0.1 litecoin.
But in exchange we're credited with a corresponding amount of swapbill.

It's worth noting at this point that the SwapBill protocol includes a constraint on the minimum amount of swapbill associated with any
given SwapBill 'account', or output.
This constraint is currently set to exactly 10000000 satoshis, and so that is the minimum amount we're allowed to burn.
(If you try to burn less, the client should refuse to submit the transaction and display a suitable error message.)

By default, queries such as get_balance only report the amount actually confirmed (with at least one confirmation) by the host blockchain,
and so if we try querying this straight away, we won't see any swapbill credited for this burn:

```
~/git/swapbill $ python Client.py get_balance
Loaded cached state data successfully
State update starting from block 283346
Committed state updated to start of block 283346
In memory state updated to end of block 283366
Operation successful
active : 0
spendable : 0
total : 0
```

But we can use the -i option to force the query to include pending transactions (from the litecoind memory pool), and then we get:

```
~/git/swapbill $ python Client.py get_balance -i
Loaded cached state data successfully
State update starting from block 283346
Committed state updated to start of block 283346
In memory state updated to end of block 283366
in memory pool: Burn
 - 10000000 swapbill output added
Operation successful
active : 10000000
spendable : 10000000
total : 10000000
```

And then, if we wait a bit to allow the transaction to go through, we can see this as a confirmed transaction:

```
~/git/swapbill $ python Client.py get_balance
Loaded cached state data successfully
State update starting from block 283346
Committed state updated to start of block 283349
in memory: Burn
 - 10000000 swapbill output added
In memory state updated to end of block 283369
Operation successful
active : 10000000
spendable : 10000000
total : 10000000
```

## Aside: committed and in memory transactions

In the above output we can see different block counts for 'committed' and 'in memory' state, and it's worth taking a moment to explain this.

What's going on here is that the client commits state to disk in order to avoid spending time resynchronising on each invocation,
but with this committed state actually lagging a fixed number of blocks (currently 20) behind the actual current block chain end.

This mechanism enables the client to handle small blockchain reorganisations robustly, without overcomplicating the client code.
If there are blockchain reorganisations of more than 20 blocks this will trigger a full resynch,
but blockchain reorganisations of less than 20 blocks can be processed naturally starting from the committed state.

For transaction reporting during synchronisation:
* Transactions that are included in the persistent state cached to disk get prefixed by 'committed'.
* Transactions that are confirmed in the blockchain but not yet cached to disk get prefixed by 'in memory'. (When you run the client again, you'll normally see these transactions repeated, unless there was a blockchain reorganisation invalidating the transaction.)
* Transactions that are not yet confirmed in the blockchain, but present in the litecoind memory pool get get prefixed with 'in memory pool'.

## Multiple outputs, and 'Collect'

