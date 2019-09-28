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
    bill_reminder_message: str
    cleaning_channel: int
    clean_message: str
    residents: List[int]
    todos: List[str]
    cleaning_decider: int

    def __init__(self, file: str):
        super(Client, self).__init__()

        self.file = file
        with open(Path(PATH).joinpath(file)) as f:
            for key, setting in json.load(f).items():
                setattr(self, key, setting)

        self.cleaning_areas = {index: todo for index, todo in enumerate(self.todos)}

    async def who_cleans_what(self):
        assert len(self.residents) == len(self.todos)
        cleaning = ((self.cleaning_decider + i) % len(self.todos) for i in range(len(self.todos)))
        assignments = ((self.residents[resident], self.cleaning_areas[area])
                       for resident, area in enumerate(cleaning))
        self.cleaning_decider = (self.cleaning_decider + 1) % len(self.todos)
        self.save_setting(cleaning_decider=self.cleaning_decider)

        for resident, todo in assignments:
            user: discord.User = self.get_user(resident)
            await self.asure_dm_exists(user)
            await user.send(todo)

        channel: discord.TextChannel = self.get_channel(self.cleaning_channel)
        await channel.send(self.clean_message)

    async def bill_reminder(self):
        if self.search_channel_for_bills():
            bill_manager: discord.User = self.get_user(self.bill_manager_id)
            await self.asure_dm_exists(bill_manager)
            await bill_manager.send(self.bill_reminder_message)

    async def anounce_rent(self):
        pdf_urls = await self.search_channel_for_bills()
        if pdf_urls:
            pdfs_data = await self.request_urls(pdf_urls)

            bills = [pdf.read(pdf_data) for pdf_data in pdfs_data]
            total = sum(bills)

            channel: discord.TextChannel = self.get_channel(self.bill_message_channel_id)
            message = (f"This month the total rent is ```{total} Kr```"
                       f"Each bill is: "
                       f"```"
                       f"{' Kr, '.join([str(bill) for bill in bills])} Kr"
                       f"```"
                       f"Sam and Frida pays ```3000 Kr```"
                       f"Madeleine, Ludvig and Elias pays ```{ceil((total - 6500) / 3)} Kr```"
                       f"Amanda pays ```500 Kr```")
            # message = (f"This month the total rent is ```{total} Kr``` \n"
            #            f"Each bill is: "
            #            f"```"
            #            f"{' Kr, '.join([str(bill) for bill in bills])} Kr"
            #            f"```"
            #            f"Madeleine, Ludvig, Sam and Elias each pay ```{ceil(total / 4)} Kr```")

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

    def save_setting(self, **kwargs) -> None:
        path = Path(PATH).joinpath(self.file)
        with open(path) as f:
            setting = json.load(f)
        for key, value in kwargs.items():
            setting[key] = value
        with open(path, "w") as f:
            json.dump(setting, f, indent=4, ensure_ascii=False)

    async def on_ready(self):
        print("Is booted up and ready to go!")

        scheduler = AsyncIOScheduler()

        scheduler.add_job(self.who_cleans_what, "cron", day_of_week=6, hour=10,
                          misfire_grace_time=300)
        scheduler.add_job(self.anounce_rent, "cron", day=25, hour=15,
                          misfire_grace_time=300)
        scheduler.add_job(self.bill_reminder, "cron", day="20-25", hour=13,
                          misfire_grace_time=300)
        scheduler.start()

    async def on_message(self, message: discord.Message):
        if message.author != self.user:
            if message.content.lower() == "/hus räkningar":
                await self.anounce_rent()
            if message.content.lower() == "test":
                await self.anounce_rent()

    def run(self):
        print("Booting....")
        super(Client, self).run(self.token)
