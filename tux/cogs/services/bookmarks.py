from typing import cast

import discord
from discord.ext import commands
from loguru import logger

from tux.bot import Tux
from tux.ui.embeds import EmbedCreator
from tux.utils.constants import CONST


class Bookmarks(commands.Cog):
    def __init__(self, bot: Tux) -> None:
        self.bot = bot

        self.valid_add_emojis = CONST.ADD_BOOKMARK
        self.valid_remove_emojis = CONST.REMOVE_BOOKMARK
        self.valid_emojis = CONST.ADD_BOOKMARK + CONST.REMOVE_BOOKMARK

    # The linter wants to change this but it breaks when it does that
    def _is_valid_emoji(self, emoji: discord.PartialEmoji, valid_list: str) -> bool:
        if emoji.name in valid_list:  # noqa: SIM103
            return True
        return False

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """
        Handle the addition of a reaction to a message.

        Parameters
        ----------
        payload : discord.RawReactionActionEvent
            The payload of the reaction event.

        Returns
        -------
        None
        """
        if not self._is_valid_emoji(payload.emoji, self.valid_emojis):
            return

        # Get the user who reacted to the message
        user = self.bot.get_user(payload.user_id)
        if user is None:
            try:
                user = await self.bot.fetch_user(payload.user_id)
            except discord.NotFound:
                logger.error(f"User not found for ID: {payload.user_id}")
            except (discord.Forbidden, discord.HTTPException) as fetch_error:
                logger.error(f"Failed to fetch user: {fetch_error}")
            return
        # Fetch the channel where the reaction was added
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(payload.channel_id)
            except discord.NotFound:
                logger.error(f"Channel not found for ID: {payload.channel_id}")
            except (discord.Forbidden, discord.HTTPException) as fetch_error:
                logger.error(f"Failed to fetch channel: {fetch_error}")
            return

        channel = cast(discord.TextChannel | discord.Thread, channel)

        # Fetch the message that was reacted to
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            logger.error(f"Message not found for ID: {payload.message_id}")
            return
        except (discord.Forbidden, discord.HTTPException) as fetch_error:
            logger.error(f"Failed to fetch message: {fetch_error}")
            return

        # check for what to do
        if self._is_valid_emoji(payload.emoji, self.valid_add_emojis):
            # Create an embed for the bookmarked message
            embed = await self._create_bookmark_embed(message)

            # Send the bookmarked message to the user
            await self._send_bookmark(user, message, embed, payload.emoji)

        elif self._is_valid_emoji(payload.emoji, self.valid_remove_emojis) and user is not self.bot.user:
            await self._delete_bookmark(message, user)
        else:
            return

    async def _create_bookmark_embed(
        self,
        message: discord.Message,
    ) -> discord.Embed:
        if len(message.content) > CONST.EMBED_MAX_DESC_LENGTH:
            message.content = f"{message.content[: CONST.EMBED_MAX_DESC_LENGTH - 3]}..."

        embed = EmbedCreator.create_embed(
            bot=self.bot,
            embed_type=EmbedCreator.INFO,
            title="Message Bookmarked",
            description=f"> {message.content}",
        )

        embed.add_field(name="Author", value=message.author.name, inline=False)

        embed.add_field(name="Jump to Message", value=f"[Click Here]({message.jump_url})", inline=False)
        if message.attachments:
            attachments_info = "\n".join([attachment.url for attachment in message.attachments])
            embed.add_field(name="Attachments", value=attachments_info, inline=False)
        return embed

    async def _delete_bookmark(self, message: discord.Message, user: discord.User) -> None:
        if message.author is not self.bot.user:
            return
        await message.delete()

    @staticmethod
    async def _send_bookmark(
        user: discord.User,
        message: discord.Message,
        embed: discord.Embed,
        emoji: discord.PartialEmoji,
    ) -> None:
        """
        Send a bookmarked message to the user.

        Parameters
        ----------
        user : discord.User
            The user to send the bookmarked message to.
        message : discord.Message
            The message that was bookmarked.
        embed : discord.Embed
            The embed to send to the user.
        emoji : str
            The emoji that was reacted to the message.
        """

        try:
            dm_message = await user.send(embed=embed)
            await dm_message.add_reaction(CONST.REMOVE_BOOKMARK)

        except (discord.Forbidden, discord.HTTPException) as dm_error:
            logger.error(f"Cannot send a DM to {user.name}: {dm_error}")

            notify_message = await message.channel.send(
                f"{user.mention}, I couldn't send you a DM. Please make sure your DMs are open for bookmarks to work.",
            )

            await notify_message.delete(delay=30)


async def setup(bot: Tux) -> None:
    await bot.add_cog(Bookmarks(bot))
