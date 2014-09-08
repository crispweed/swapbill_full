Running the client
===================

Obtaining the source code
----------------------------

The project is hosted on <https://github.com/crispweed/swapbill>, and so you can get the client source code with git, as follows::

    ~/git $ git clone https://github.com/crispweed/swapbill
    Cloning into 'swapbill'...
    remote: Counting objects: 52, done.
    remote: Compressing objects: 100% (41/41), done.
    remote: Total 52 (delta 9), reused 46 (delta 3)
    Unpacking objects: 100% (52/52), done.

In case you don't have git, you can also download the source code directly as an archive from <https://github.com/crispweed/swapbill/archive/master.zip>, extract to a new directory.

No installer
----------------------------

There's no installation process for the client and you can just run it directly
from the downloaded source tree.

You'll need to ensure that the :doc:`python library dependencies</requirements>` are met before running the client, or you'll get an error message telling you to do this.

And then you run the client with (e.g.)::

    ~/git $ cd swapbill/
    ~/git/swapbill $ python Client.py get_balance

Selecting host blockchain
---------------------------

You can use the '--host' command line option to choose the desired host blockchain to run against.
This defaults to 'bitcoin', but if you want to run against litecoind (for example if you only have litecoind installed, and not bitcoind)
then you need to change client invocation as follows:

    ~/git/swapbill $ python Client.py --host litecoin get_balance

You can change this selection per client invocation, and work with multiple host blockchains without any problems.
(This is required for the cross chain exchange functionality!)

The client maintains independent subdirectories within its data directory for each host, with separate wallet files and state cache data.

RPC errors
-----------

If you don't have bitcoind running, or if you don't have the RPC interface set up correctly, you'll see something like:

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

