'''Counter class.

Usage:

increment('counter1')
count = get_count('counter')

Modified from http://code.google.com/appengine/articles/sharding_counters.html

Original is Apache license,
see http://code.google.com/p/google-app-engine-samples.
'''
from google.appengine.ext import db
import random

class GeneralCounterShardConfig(db.Model):
    """Tracks the number of shards for each named counter."""
    name = db.StringProperty(required=True)
    num_shards = db.IntegerProperty(required=True, default=1)


class GeneralCounterShard(db.Model):
    """Shards for each named counter"""
    name = db.StringProperty(required=True)
    count = db.IntegerProperty(required=True, default=0)


def get_count(name):
    """Retrieve the value for a given sharded counter.

    Parameters:
      name - The name of the counter
    """
    total = 0
    for counter in GeneralCounterShard.all().filter('name = ', name):
        total += counter.count
    return total


def set_value(name, value):
    config = GeneralCounterShardConfig.get_or_insert(name, name=name)
    def txn():
        for index in range(config.num_shards):
            shard_name = name + str(index)
            counter = GeneralCounterShard.get_by_key_name(shard_name)
            if counter is None:
                counter = GeneralCounterShard(key_name=shard_name, name=name)
            if index == 0:
                counter.count = value
            else:
                counter.count = 0
            counter.put()
    db.run_in_transaction(txn)


def increment(name, delta=1):
    """Increment the value for a given sharded counter.

    Parameters:
      name - The name of the counter
      delta - The amount to increment

    If the counter doesn't exist, its value after this function is delta.
    """
    config = GeneralCounterShardConfig.get_or_insert(name, name=name)
    def txn():
        index = random.randint(0, config.num_shards - 1)
        shard_name = name + str(index)
        counter = GeneralCounterShard.get_by_key_name(shard_name)
        if counter is None:
            counter = GeneralCounterShard(key_name=shard_name, name=name)
        counter.count += delta
        counter.put()
    db.run_in_transaction(txn)


def increase_shards(name, num):
    """Increase the number of shards for a given sharded counter.
    Will never decrease the number of shards.

    Parameters:
      name - The name of the counter
      num - How many shards to use

    """
    config = GeneralCounterShardConfig.get_or_insert(name, name=name)
    def txn():
        if config.num_shards < num:
            config.num_shards = num
            config.put()
    db.run_in_transaction(txn)
