channels_valkey
===============

.. image:: https://img.shields.io/pypi/v/channels_valkey.svg
    :target: https://pypi.python.org/pypi/channels_valkey

Provides Django Channels channel layers that use Valkey as a backing store.

this is a fork of the wonderful ``channels-redis`` project.

There are two available implementations:

* ``ValkeyChannelLayer`` is the original layer, and implements channel and group
  handling itself.
* ``ValkeyPubSubChannelLayer`` is newer and leverages Valkey Pub/Sub for message
  dispatch. This layer is currently at *Beta* status, meaning it may be subject
  to breaking changes whilst it matures.

Both layers support a single-server and sharded configurations.

`channels_valkey` is tested against Python 3.9 to 3.13, `valkey-py` versions 6.x,
and the development branch, and Channels versions 3, 4 and the development
branch there.

Installation
------------

.. code-block::

    pip install channels-valkey

Usage
-----

Set up the channel layer in your Django settings file like so:

.. code-block:: python

    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_valkey.core.ValkeyChannelLayer",
            "CONFIG": {
                "hosts": [("localhost", 6379)],
            },
        },
    }

Or, you can use the alternate implementation which uses Valkey Pub/Sub:

.. code-block:: python

    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_valkey.pubsub.ValkeyPubSubChannelLayer",
            "CONFIG": {
                "hosts": [("localhost", 6379)],
            },
        },
    }

Possible options for ``CONFIG`` are listed below.

``hosts``
~~~~~~~~~

The server(s) to connect to, as either URIs, ``(host, port)`` tuples, or dicts conforming to `valkey Connection <https://valkey-py.readthedocs.io/en/stable/connections.html#async-client>`_.
Defaults to ``valkey://localhost:6379``. Pass multiple hosts to enable sharding,
but note that changing the host list will lose some sharded data.

SSL connections that are self-signed (ex: Heroku):

.. code-block:: python

    "default": {
        "BACKEND": "channels_valkey.pubsub.ValkeyPubSubChannelLayer",
        "CONFIG": {
            "hosts":[{
                "address": "valkeys://user@host:port",  # "VALKEY_TLS_URL"
                "ssl_cert_reqs": None,
            }]
        }
    }

Sentinel connections require dicts conforming to:

.. code-block:: python

    {
        "sentinels": [
            ("localhost", 26379),
        ],
        "master_name": SENTINEL_MASTER_SET,
        **kwargs
    }

note the additional ``master_name`` key specifying the Sentinel master set and any additional connection kwargs can also be passed. Plain Valkey and Sentinel connections can be mixed and matched if
sharding.

If your server is listening on a UNIX domain socket, you can also use that to connect: ``["unix:///path/to/valkey.sock"]``.
This should be slightly faster than a loopback TCP connection.

``prefix``
~~~~~~~~~~

Prefix to add to all Valkey keys. Defaults to ``asgi``. If you're running
two or more entirely separate channel layers through the same Valkey instance,
make sure they have different prefixes. All servers talking to the same layer
should have the same prefix, though.

``expiry``
~~~~~~~~~~

Message expiry in seconds. Defaults to ``60``. You generally shouldn't need
to change this, but you may want to turn it down if you have peaky traffic you
wish to drop, or up if you have peaky traffic you want to backlog until you
get to it.

``group_expiry``
~~~~~~~~~~~~~~~~

Group expiry in seconds. Defaults to ``86400``. Channels will be removed
from the group after this amount of time; it's recommended you reduce it
for a healthier system that encourages disconnections. This value should
not be lower than the relevant timeouts in the interface server (e.g.
the ``--websocket_timeout`` to `daphne
<https://github.com/django/daphne>`_).

``capacity``
~~~~~~~~~~~~

Default channel capacity. Defaults to ``100``. Once a channel is at capacity,
it will refuse more messages. How this affects different parts of the system
varies; a HTTP server will refuse connections, for example, while Django
sending a response will just wait until there's space.

``channel_capacity``
~~~~~~~~~~~~~~~~~~~~

Per-channel capacity configuration. This lets you tweak the channel capacity
based on the channel name, and supports both globbing and regular expressions.

It should be a dict mapping channel name pattern to desired capacity; if the
dict key is a string, it's interpreted as a glob, while if it's a compiled
``re`` object, it's treated as a regular expression.

This example sets ``http.request`` to 200, all ``http.response!`` channels
to 10, and all ``websocket.send!`` channels to 20:

.. code-block:: python

    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_valkey.core.ValkeyChannelLayer",
            "CONFIG": {
                "hosts": [("localhost", 6379)],
                "channel_capacity": {
                    "http.request": 200,
                    "http.response!*": 10,
                    re.compile(r"^websocket.send\!.+"): 20,
                },
            },
        },
    }

If you want to enforce a matching order, use an ``OrderedDict`` as the
argument; channels will then be matched in the order the dict provides them.

``symmetric_encryption_keys``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pass this to enable the optional symmetric encryption mode of the backend. To
use it, make sure you have the ``cryptography`` package installed, or specify
the ``cryptography`` extra when you install ``channels-valkey``::

    pip install channels-valkey[cryptography]

``symmetric_encryption_keys`` should be a list of strings, with each string
being an encryption key. The first key is always used for encryption; all are
considered for decryption, so you can rotate keys without downtime - just add
a new key at the start and move the old one down, then remove the old one
after the message expiry time has passed.

Data is encrypted both on the wire and at rest in Valkey, though we advise
you also route your Valkey connections over TLS for higher security; the Valkey
protocol is still unencrypted, and the channel and group key names could
potentially contain metadata patterns of use to attackers.

Keys **should have at least 32 bytes of entropy** - they are passed through
the SHA256 hash function before being used as an encryption key. Any string
will work, but the shorter the string, the easier the encryption is to break.

If you're using Django, you may also wish to set this to your site's
``SECRET_KEY`` setting via the ``CHANNEL_LAYERS`` setting:

.. code-block:: python

    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_valkey.core.ValkeyChannelLayer",
            "CONFIG": {
                "hosts": ["valkey://:password@127.0.0.1:6379/0"],
                "symmetric_encryption_keys": [SECRET_KEY],
            },
        },
    }

``on_disconnect`` / ``on_reconnect``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The PubSub layer, which maintains long-running connections to Valkey, can drop messages in the event of a network partition.
To handle such situations the PubSub layer accepts optional arguments which will notify consumers of Valkey disconnect/reconnect events.
A common use-case is for consumers to ensure that they perform a full state re-sync to ensure that no messages have been missed.

.. code-block:: python

    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_valkey.pubsub.ValkeyPubSubChannelLayer",
            "CONFIG": {
                "hosts": [...],
                "on_disconnect": "valkey.disconnect",
            },
        },
    }


And then in your channels consumer, you can implement the handler:

.. code-block:: python

    async def valkey_disconnect(self, *args):
        # Handle disconnect

Dependencies
------------

Valkey server >= 7.2.7 is required for `channels-valkey`. Python 3.9 or higher is required.

``serializer_format``
~~~~~~~~~~~~~~~~~~~~~

bt default every message sent to valkey is encoded using `msgpack <https://msgpack.org/>`_ (msgpack is a mandatory dependency of this package).
It is also possible to switch to `JSON <https://www.json.org/>`_:

.. code-block:: python

    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_valkey.core.ValkeyChannelLayer",
            "CONFIG": {
                "hosts": ["valkey://:password@127.0.0.1:6379/0"],
                "serializer_format": "json",
            },
        },
    }

also Custom serializers can be defined by:
- extending ``channels_valkey.serializers.BaseMessageSerializer``, implementing ``as_bytes `` and ``from_bytes`` methods.
- using any class which accepts generic keyword arguments and provides ``serialize``/``deserialize`` methods

Then it may be registered (or can be overriden) by using ``channels_valkey.serializers.registry``:

.. code-block:: python

    from channels_valkey.serializers import registry

    class MyFormatSerializer:
        def serialize(self, message):
            ...

        def deserializer(self, message):
            ...


    registry.register_serializer("myformat", MyFormatSerializer)


**NOTE**: the registry allows you to override the serializer class used for a specific format without any check nor constraint.
Thus it is recommended that to pay particular attention to the order-of-imports when using third-party serializers which may override a built-in format.

Serializers are also responsible for encryption using *symmetric_encryption_keys*.
When extending ``channels_valkey.serializers.BaseMessageSerializer`` encryption is already configured in the base class,
unless you override the ``serialize``/``deserialize`` methods: in this case you should call ``self.crypter.encrypt`` in serialization and ``self.crypter.decrypt`` in deserialization process.
When using a fully custom serializer, expect an optional sequence of keys to be passed via ``symmetric_encryption_keys``.

Used commands
~~~~~~~~~~~~~

Your Valkey server must support the following commands:

* ``ValkeyChannelLayer`` uses ``BZPOPMIN``, ``DEL``, ``EVAL``, ``EXPIRE``,
  ``KEYS``, ``PIPELINE``, ``ZADD``, ``ZCOUNT``, ``ZPOPMIN``, ``ZRANGE``,
  ``ZREM``, ``ZREMRANGEBYSCORE``

* ``ValkeyPubSubChannelLayer`` uses ``PUBLISH``, ``SUBSCRIBE``, ``UNSUBSCRIBE``

Local Development
-----------------

You can run the necessary Valkey instances in Docker with the following commands:

.. code-block:: shell

    docker network create valkey-network
    docker run --rm \
        --network=valkey-network \
        --name=valkey-server \
        -p 6379:6379 \
        valkey/valkey
    docker run --rm \
        --network valkey-network \
        --name valkey-sentinel \
        -e VALKEY_MASTER_HOST=valkey-server \
        -e VALKEY_SENTINEL_QUORUM=1 \
        -p 26379:26379 \
        bitnami/valkey-sentinel

Contributing
------------

this project is a fork of ``channels_redis`` project, it's mostly the same setup, only replace ``redis`` with ``valkey``.

**Note**: this package is meant to be an exact mimic of ``channels_redis``, if you need a new feature, please ask them, if accepted, it'll be added here as well.

Please refer to the
`main Channels contributing docs <https://github.com/django/channels/blob/master/CONTRIBUTING.rst>`_.
That also contains advice on how to set up the development environment and run the tests.

Maintenance
-----------

To report bugs or request new features, please open a new GitHub issue.
