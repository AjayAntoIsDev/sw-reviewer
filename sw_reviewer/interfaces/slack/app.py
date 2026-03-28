"""Slack Bolt async app with Assistant framework for the SW Reviewer agent."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from slack_bolt.app.async_app import AsyncApp
from slack_bolt.context.async_context import AsyncBoltContext
from slack_bolt.context.say.async_say import AsyncSay
from slack_bolt.middleware.assistant.async_assistant import AsyncAssistant

from sw_reviewer.history import ConversationStore
from sw_reviewer.interfaces.slack.files import build_user_content
from sw_reviewer.interfaces.slack.stream import run_agent_streaming

if TYPE_CHECKING:
    from pydantic_ai import Agent

    from sw_reviewer.config import AppConfig

logger = logging.getLogger(__name__)

_MENTION_RE = re.compile(r'<@[A-Z0-9]+>\s*')


def create_slack_app(config: AppConfig, agent: Agent) -> AsyncApp:
    if not config.slack_bot_token:
        raise RuntimeError('Missing SLACK_BOT_TOKEN in .env')

    app = AsyncApp(token=config.slack_bot_token)
    store = ConversationStore()
    assistant = AsyncAssistant()

    @assistant.thread_started
    async def handle_thread_started(
        say: AsyncSay,
        set_suggested_prompts,
        **kwargs,
    ):
        await say('How can I help you? I can browse the web, review applications, and more.')
        await set_suggested_prompts(
            prompts=[
                {
                    'title': 'Navigate to a URL',
                    'message': 'Please navigate to https://example.com and tell me what you see.',
                },
                {
                    'title': 'Take a screenshot',
                    'message': 'Navigate to https://example.com and take a screenshot.',
                },
                {
                    'title': 'Review a web page',
                    'message': 'Please review the UI/UX of https://example.com and give me feedback.',
                },
            ],
        )

    @assistant.user_message
    async def handle_user_message(
        client,
        context: AsyncBoltContext,
        payload: dict,
        say: AsyncSay,
        set_status,
        **kwargs,
    ):
        channel_id = payload['channel']
        thread_ts = payload['thread_ts']
        user_message = payload.get('text', '')
        files = payload.get('files')
        team_id = context.team_id or ''
        user_id = context.user_id or ''

        await set_status(status='Thinking...')

        thread_key = (team_id, channel_id, thread_ts)
        message_history = await store.get(thread_key)

        try:
            user_content = await build_user_content(
                text=user_message,
                files=files,
                bot_token=config.slack_bot_token,
            )
        except Exception:
            logger.exception('Failed to process user content')
            user_content = user_message

        try:
            await run_agent_streaming(
                agent=agent,
                user_content=user_content,
                message_history=message_history,
                client=client,
                channel_id=channel_id,
                thread_ts=thread_ts,
                team_id=team_id,
                user_id=user_id,
                store=store,
                thread_key=thread_key,
            )
        except Exception:
            logger.exception('Failed to run agent')
            await say(':warning: Something went wrong. Please try again.')

    app.assistant(assistant)

    @app.event('app_mention')
    async def handle_app_mention(event: dict, client, context: AsyncBoltContext):
        channel_id = event['channel']
        thread_ts = event.get('thread_ts') or event['ts']
        raw_text = event.get('text', '')
        user_message = _MENTION_RE.sub('', raw_text).strip()
        files = event.get('files')
        team_id = context.team_id or ''
        user_id = event.get('user', '')

        if not user_message and not files:
            return

        thread_key = (team_id, channel_id, thread_ts)
        message_history = await store.get(thread_key)

        try:
            user_content = await build_user_content(
                text=user_message,
                files=files,
                bot_token=config.slack_bot_token,
            )
        except Exception:
            logger.exception('Failed to process user content')
            user_content = user_message

        try:
            await run_agent_streaming(
                agent=agent,
                user_content=user_content,
                message_history=message_history,
                client=client,
                channel_id=channel_id,
                thread_ts=thread_ts,
                team_id=team_id,
                user_id=user_id,
                store=store,
                thread_key=thread_key,
            )
        except Exception:
            logger.exception('Failed to run agent for @mention')
            await client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=':warning: Something went wrong. Please try again.',
            )

    return app
