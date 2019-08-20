from typing import List
from . import pdf, PATH
import json
import discord
import aiohttp
import asyncio
from pathlib import Path
from datetime import datetime as dt
from datetime import timedelta as td
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from math import ceil


class Client(discord.Client):
    token: str
    bill_channel_id: int
    bill_message_channel_id: int
    bill_manager_id: int
    cleaning_channel: int
    residents: List[int]
    todos: List[str]
    clean_message: str

    def __init__(self, file: str):
        super(Client, self).__init__()

        with open(Path(PATH).joinpath(file)) as f:
            for key, setting in json.load(f).items():
                setattr(self, key, setting)

        self.cleaning_areas = {index: todo for index, todo in enumerate(self.todos)}
        self.cleaning_decider = 0

    async def who_cleans_what(self):
        cleaning = [(self.cleaning_decider + i) % len(self.todos) for i in range(len(self.todos))]
        assignments = ((self.residents[resident], self.cleaning_areas[area])
                       for resident, area in enumerate(cleaning))

        self.cleaning_decider = (self.cleaning_decider + 1) % len(self.todos)

        for resident, todo in assignments:
            user: discord.User = self.get_user(resident)
            await self.asure_dm_exists(user)
            await user.send(todo)

    async def bill_reminder(self):
        if self.search_channel_for_bills():
            message = ("It looks like you have forgotten to add the bills to the discord channel. There have not been "
                       "any new aditional attatchments in the channel.")
            bill_manager: discord.User = self.get_user(self.bill_manager_id)
            await self.asure_dm_exists(bill_manager)
            await bill_manager.send(message)

    async def anounce_rent(self):
        pdf_urls = await self.search_channel_for_bills()
        if pdf_urls:
            pdfs_data = await self.request_urls(pdf_urls)

            bills = [pdf.read(pdf_data) for pdf_data in pdfs_data]
            total = sum(bills)

            channel: discord.TextChannel = self.get_channel(self.bill_message_channel_id)
            message = (f"This month the total rent is ```{total} Kr``` \n"
                       f"Each bill is: "
                       f"```"
                       f"{' Kr, '.join([str(bill) for bill in bills])} Kr"
                       f"```"
                       f"Sam and Frida each pay ```3000 Kr```\n"
                       f"Madeleine, Ludvig and Elias each pay ```{ceil((total - 6000) / 3)} Kr```")
            await channel.send(message)

    async def search_channel_for_bills(self) -> List[str]:
        channel: discord.TextChannel = self.get_channel(self.bill_channel_id)
        now = dt.now()
        urls = [attatchemnt.url
                async for message in channel.history(after=now - td(now.day))
                for attatchemnt in message.attachments]
        return urls

    async def request_urls(self, urls: List[str]) -> List[bytes]:
        async with aiohttp.ClientSession() as session:
            tasks = []
            for url in urls:
                tasks.append(asyncio.create_task(self.request_url(url, session)))
            data = [await task for task in tasks]
        return data

    @staticmethod
    async def request_url(url: str, session: aiohttp.ClientSession) -> bytes:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.read()

    @staticmethod
    async def asure_dm_exists(user: discord.User) -> None:
        if not user.dm_channel:
            await user.create_dm()

    async def on_ready(self):
        print("Is booted up and ready to go!")

        scheduler = AsyncIOScheduler()

        scheduler.add_job(self.who_cleans_what, "cron", day_of_week=6, hour=10,
                          misfire_grace_time=300)

        scheduler.add_job(self.anounce_rent, "cron", day=25, hour=14,
                          misfire_grace_time=300)
        scheduler.add_job(self.bill_reminder, "cron", day="20-24", hour=14,
                          misfire_grace_time=300)
        scheduler.start()

    def run(self):
        print("Booting....")
        super(Client, self).run(self.token)
