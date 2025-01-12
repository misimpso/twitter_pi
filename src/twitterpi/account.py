import logging
import random

from asyncio import sleep
from twitterpi.api import Api
from twitterpi.cache import Cache
from twitterpi.dto import Directive, Tweet, User
from typing import Optional


class Account:
    def __init__(self, account_name: str, api: Api, cache: Cache, search_terms: list[str], filter_terms: list[str]):
        """ Main controller for account interaction.

        Args:
            account_name (str): Account screen name (from credentials.toml).
            api (obj: Api): Api object with consumer / secret keys already setup.
            cache (obj: Cache): Cache object for storing / referencing tweets.
            search_terms (list[str]): List of search terms.
            filter_terms (list[str]): List of filter terms to append to each search term.
        """

        logger: logging.Logger = logging.getLogger(__name__)
        self.logger = logging.LoggerAdapter(logger, extra={"account_name": account_name})

        self.account_name: str = account_name
        self.api: Api = api
        self.cache: Cache = cache

        # Append filter terms to each search term
        self.search_terms = [
            f"{search_term} {' '.join([f'-filter:{filter_term}' for filter_term in filter_terms])}".strip()
            for search_term in search_terms
        ]

    async def start(self):
        """ Main loop for getting and interacting with tweets.
        """

        while True:
            tweet: Tweet = await self.get_tweet()

            if not await self.cache.check_tweet_seen(tweet):
                await self.interact(tweet)
            else:
                self.logger.info("Tweet already seen.")

            await self.cache.remove_new_tweet(tweet)
            await self.cache.insert_seen_tweet(tweet)

            await sleep(5.0)

    async def interact(self, tweet: Tweet):
        """ Interact with given `tweet` based on its text contents.

        Args:
            tweet (obj: Tweet): Tweet to interact with.
        """

        actions: list[tuple] = []
        directive = Directive()
        directive.parse_tweet(tweet.text)

        self.logger.info(f"Interacting with Tweet [https://twitter.com/{tweet.author.screen_name}/status/{tweet.id}]")
        for line in tweet.text.split("\n"):
            self.logger.info(f" │ {line}")
        self.logger.info(f" └─────── {directive}")

        if not ((directive.retweet and directive.follow) or (directive.retweet and directive.favorite)):
            self.logger.info("Not enough directives to act upon.")
            return

        if directive.retweet:
            actions.append((self.api.retweet, {"tweet_id": tweet.id}))

        if directive.favorite:
            actions.append((self.api.favorite_tweet, {"tweet_id": tweet.id}))

        if directive.follow:
            actions.append((self.api.follow_user, {"user": tweet.author}))
            for mention in tweet.mentions:
                actions.append((self.api.follow_user, {"user": mention}))

        if not actions:
            self.logger.info("Nothing to act upon.")
            return

        random.shuffle(actions)

        for action in actions:
            endpoint, kwargs = action
            await endpoint(**kwargs)

        self.logger.info("Tweet interacted!")

    async def get_tweet(self) -> Optional[Tweet]:
        """ Get a tweet to interact with. If tweets don't exist in cache,
            get tweets from API and populate the cache.

        Returns:
            (obj: Tweet | None): A tweet to interact with or None.
        """

        # Get tweet from database
        tweet: Tweet = await self.cache.get_tweet()

        if not tweet:
            # Get tweets from API and insert into database
            for search_term in self.search_terms:
                new_tweets: list[Tweet] = await self.api.get_tweets(search_term)
                if len(new_tweets) == 0:
                    raise ValueError(f"Search returned no tweets. [{search_term}]")
                await self.cache.insert_new_tweets(tweets=new_tweets)

            tweet: Tweet = await self.cache.get_tweet()
        return tweet

    async def follow_user(self, user: User):
        """ Send request to API to follow the given `user`.

        Args:
            user (obj: User) User to follow
        """

        await self.api.follow_user(user_id=user.id)
