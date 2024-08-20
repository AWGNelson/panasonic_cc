import pcomfortcloud
import aiohttp
import asyncio
import certifi
import ssl


async def test1():
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession() as session:
        api = pcomfortcloud.ApiClient(
            username="j.b.kay@btinternet.com",
            password="I5l30fL3w15",
            client=session,
        )
        print(api)
        await api.start_session()
        devices = api.get_devices()
        print(devices)


async def test():
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession() as session:
        async with session.get(url, ssl=ssl_context) as response:
            print(response)
            api = pcomfortcloud.ApiClient(
                username="j.b.kay@btinternet.com",
                password="I5l30fL3w15",
                client=session,
            )
            print(api)
            await api.start_session()
            devices = api.get_devices()
            print(devices)


if __name__ == "__main__":
    asyncio.run(test1())
