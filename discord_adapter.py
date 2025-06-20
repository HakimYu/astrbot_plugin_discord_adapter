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
        logger.info(f"messagecontent: {message.content}")
        components = []

        # 处理回复
        if message.reference and isinstance(message.reference.resolved, discord.Message):
            components.append(
                Reply(message_id=str(message.reference.message_id)))

        # 处理文本内容和提及
        if message.content:
            current_text = ""
            for index, char in enumerate(message.content):
                # 检查这个位置是否在任何提及的范围内
                is_mention = False
                for mention in message.mentions:
                    mention_str = f"<@{mention.id}>"
                    pos = message.content.find(
                        mention_str, max(0, index - len(mention_str)))
                    if pos <= index < pos + len(mention_str):
                        if current_text:
                            components.append(Plain(text=current_text))
                            current_text = ""
                        if not any(isinstance(x, At) and x.user_id == str(mention.id) for x in components):
                            components.append(At(user_id=str(mention.id)))
                        is_mention = True
                        break

                if not is_mention:
                    current_text += char
            if current_text:
                components.append(Plain(text=current_text))

        # 处理附件（图片等）
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith('image/'):
                components.append(Image(file=attachment.url))

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
        logger.info(f"收到消息: {message}")
        self.commit_event(message_event)
