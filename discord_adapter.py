import asyncio
import discord
from discord.ext import commands
from astrbot.api.platform import (
    Platform, AstrBotMessage, MessageMember, MessageType, PlatformMetadata, register_platform_adapter
)
from astrbot.api.event import MessageChain
from astrbot.core.platform.astr_message_event import MessageSesion
from astrbot import logger
from .discord_event import DiscordEvent
from astrbot.api.message_components import Plain, Image, At, Reply


@register_platform_adapter("discord", "Discord 消息平台适配器", default_config_tmpl={
    "token": "",
    "introduction": "",
    "prefix": "!"
})
class DiscordAdapter(Platform):
    def __init__(self, platform_config: dict, platform_settings: dict, event_queue: asyncio.Queue) -> None:
        super().__init__(event_queue)
        self.config = platform_config
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        self.bot = commands.Bot(
            command_prefix=platform_config.get("prefix"), intents=intents)

        @self.bot.event
        async def on_message(message):
            # 忽略自己的消息
            if message.author == self.bot.user:
                return
            abm = await self.convert_message(message)
            await self.handle_msg(abm)

    async def convert_discord_message_to_components(self, message: discord.Message) -> list:
        """将 Discord 消息转换为 AstrBot 消息组件列表"""
        components = []

        # 处理回复
        if message.reference and isinstance(message.reference.resolved, discord.Message):
            replied_msg = message.reference.resolved
            components.append(
                Reply(
                    id=str(message.reference.message_id),
                    sender_id=str(replied_msg.author.id),
                    sender_nickname=replied_msg.author.name,
                    time=int(replied_msg.created_at.timestamp()),
                    message_str=replied_msg.content,
                    text=replied_msg.content,
                    qq=str(replied_msg.author.id),
                ))

        # 处理文本内容和提及
        if message.content:
            content = message.content
            last_idx = 0
            # 按出现顺序处理 mentions
            for m in message.mentions:
                mention_str = f"<@{m.id}>"
                idx = content.find(mention_str, last_idx)
                if idx == -1:
                    continue
                # 前面的文本
                if idx > last_idx:
                    components.append(Plain(text=content[last_idx:idx]))
                # at 组件
                components.append(At(qq=str(m.id)))
                last_idx = idx + len(mention_str)
            # 剩余文本
            if last_idx < len(content):
                components.append(Plain(text=content[last_idx:]))
            # 如果没有任何内容，添加原始文本
            if not components or (len(components) == 1 and isinstance(components[0], Reply)):
                components.append(Plain(text=content))

        # 处理附件（图片等）
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith('image/'):
                components.append(Image(file=attachment.url))

        logger.info(f"components: {components}")
        return components

    async def send_by_session(self, session: MessageSesion, message_chain: MessageChain):
        await super().send_by_session(session, message_chain)

    def meta(self) -> PlatformMetadata:
        return PlatformMetadata(
            name="discord",
            description="Discord 适配器",
            id=str(self.bot.user.id) if self.bot.user else ""
        )

    async def run(self):
        await self.bot.start(self.config.get("token"))

    async def convert_message(self, message: discord.Message) -> AstrBotMessage:
        abm = AstrBotMessage()
        # 判断是群聊还是私聊
        abm.type = MessageType.FRIEND_MESSAGE if isinstance(
            message.channel, discord.DMChannel) else MessageType.GROUP_MESSAGE
        abm.group_id = str(message.guild.id) if message.guild and hasattr(
            message.guild, 'id') else ""
        abm.message_str = message.content
        abm.sender = MessageMember(
            user_id=str(message.author.id),
            nickname=message.author.name
        )
        # 转换消息内容为组件
        abm.message = await self.convert_discord_message_to_components(message)
        abm.raw_message = message
        abm.self_id = str(self.bot.user.id) if self.bot.user else ""
        abm.session_id = str(message.channel.id)
        abm.message_id = str(message.id)
        return abm

    async def handle_msg(self, message: AstrBotMessage):
        message_event = DiscordEvent(
            message_str=message.message_str,
            message_obj=message,
            platform_meta=self.meta(),
            session_id=message.session_id,
            client=self.bot
        )
        self.commit_event(message_event)
