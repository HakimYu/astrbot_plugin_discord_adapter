from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.platform import AstrBotMessage, PlatformMetadata
from astrbot.api.message_components import Plain, Image
from astrbot.core.utils.io import download_image_by_url
import discord

class DiscordEvent(AstrMessageEvent):
    def __init__(self, message_str: str, message_obj: AstrBotMessage, platform_meta: PlatformMetadata, session_id: str, client):
        super().__init__(message_str, message_obj, platform_meta, session_id)
        self.client = client

    async def send(self, message: MessageChain):
        channel = await self.client.fetch_channel(int(self.session_id))
        for i in message.chain:
            if isinstance(i, Plain):
                await channel.send(i.text)
            elif isinstance(i, Image):
                img_url = i.file
                if img_url.startswith("file:///"):
                    # 本地文件
                    img_path = img_url[8:]
                    await channel.send(file=discord.File(img_path))
                elif img_url.startswith("http"):
                    # 网络图片,先下载
                    img_path = await download_image_by_url(img_url)
                    await channel.send(file=discord.File(img_path))
                else:
                    await channel.send(file=discord.File(img_url))
                    
        await super().send(message) 