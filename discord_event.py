from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.platform import AstrBotMessage, PlatformMetadata
from astrbot.api.message_components import Plain, Image, At, Reply
from astrbot.core.utils.io import download_image_by_url
from astrbot import logger
import discord
from discord.ext import commands
import asyncio



class DiscordEvent(AstrMessageEvent):
    def __init__(self, message_str: str, message_obj: AstrBotMessage, platform_meta: PlatformMetadata, session_id: str, client: commands.Bot):
        super().__init__(message_str, message_obj, platform_meta, session_id)
        self.client = client

    async def send(self, message: MessageChain):
        channel = await self.client.fetch_channel(int(self.session_id))
        logger.info(f"Discord 发送消息: {channel}")
        # 收集所有要发送的内容
        content = ""
        files = []
        embeds = []

        for i in message.chain:
            if isinstance(i, Plain):
                # 文本消息，追加到 content
                if content:
                    content += "\n"
                content += i.text
            elif isinstance(i, Image):
                # 处理图片
                img_url = i.file
                if img_url.startswith("file:///"):
                    # 本地文件
                    img_path = img_url[8:]
                    files.append(discord.File(img_path))
                elif img_url.startswith("http"):
                    # 网络图片,先下载
                    img_path = await download_image_by_url(img_url)
                    files.append(discord.File(img_path))
                else:
                    files.append(discord.File(img_url))
            elif isinstance(i, At):
                # @用户
                content += f"<@{i.user_id}>"
            elif isinstance(i, Reply):
                # 回复消息
                try:
                    replied_msg = await channel.fetch_message(int(i.message_id))
                    content = f"> {replied_msg.author.name}: {replied_msg.content}\n{content}"
                except:
                    # 如果获取回复消息失败，忽略回复部分
                    pass
        try:
            # 分批发送消息，避免超过 Discord 的限制
            while content or files or embeds:
                current_files = files[:10]  # Discord 限制每条消息最多 10 个文件
                current_embeds = embeds[:10]  # Discord 限制每条消息最多 10 个 embed

                # 如果内容太长，分割发送
                # Discord 消息长度限制 2000
                current_content = content[:2000] if content else ""
                if len(content) > 2000:
                    # 在合适的位置分割消息
                    split_pos = current_content.rfind('\n')
                    if split_pos == -1 or split_pos < 1500:
                        split_pos = 2000
                    current_content = content[:split_pos]
                    content = content[split_pos:].lstrip()
                else:
                    content = ""

                # 发送当前批次的消息
                await channel.send(
                    content=current_content if current_content else None,
                    files=current_files if current_files else None,
                    embeds=current_embeds if current_embeds else None
                )

                # 更新剩余内容
                files = files[10:]
                embeds = embeds[10:]

                # 如果还有内容要发送，稍微等待一下避免触发 Discord 的速率限制
                if content or files or embeds:
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error sending Discord message: {str(e)}")

        await super().send(message)
