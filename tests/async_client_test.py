import unittest

from sequoia.async_client import AsyncClient


class TestAsyncClient(unittest.TestCase):

    def test(self):
        import asyncio
        client = AsyncClient('https://registry.sandbox.eu-west-1.palettedev.aws.pikselpalette.com/', 'ref-demo-blue')

        asyncio.run(client.get_all('http://google.es', 'http://ebay.es'))