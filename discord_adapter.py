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
        self.bot = commands.Bot(command_prefix=platform_config.get("prefix"), intents=intents)

        @self.bot.event
        async def on_message(message):
            # 忽略自己的消息
            if message.author == self.bot.user:
                return
            abm = await self.convert_message(message)
            await self.handle_msg(abm)

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
        abm.type = MessageType.GROUP_MESSAGE if isinstance(message.channel, discord.TextChannel) else MessageType.FRIEND_MESSAGE
        abm.group_id = str(message.guild.id) if message.guild else ""
        abm.message_str = message.content
        abm.sender = MessageMember(
            user_id=str(message.author.id),
            nickname=message.author.name
        )
        from astrbot.api.message_components import Plain
        abm.message = [Plain(text=message.content)]
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
