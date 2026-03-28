"""Bridges pydantic-ai streaming events to Slack chat_stream."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING

from pydantic_ai import (
    AgentRunResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    TextPartDelta,
)
from pydantic_ai.messages import ModelMessage
from slack_sdk.models.messages.chunk import TaskUpdateChunk

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from slack_sdk.web.async_client import AsyncWebClient

    from sw_reviewer.history import ConversationStore, ThreadKey

logger = logging.getLogger(__name__)

FLUSH_INTERVAL = 0.4  # seconds between Slack flushes


async def run_agent_streaming(
    *,
    agent: Agent,
    user_content: str | list,
    message_history: list[ModelMessage],
    client: AsyncWebClient,
    channel_id: str,
    thread_ts: str,
    team_id: str,
    user_id: str,
    store: ConversationStore,
    thread_key: ThreadKey,
) -> None:
    """Run the agent with event streaming, piping output to Slack chat_stream."""
    streamer = await client.chat_stream(
        channel=channel_id,
        thread_ts=thread_ts,
        recipient_team_id=team_id,
        recipient_user_id=user_id,
        task_display_mode='timeline',
        buffer_size=512,
    )

    text_buffer = ''
    last_flush = asyncio.get_event_loop().time()
    tool_id_counter = 0

    try:
        async def flush_text() -> None:
            nonlocal text_buffer, last_flush
            if text_buffer:
                await streamer.append(markdown_text=text_buffer, chunks=[])
                text_buffer = ''
                last_flush = asyncio.get_event_loop().time()

        async def maybe_flush() -> None:
            now = asyncio.get_event_loop().time()
            if now - last_flush >= FLUSH_INTERVAL and text_buffer:
                await flush_text()

        result_event = None

        async for event in agent.run_stream_events(
            user_content,
            message_history=message_history,
        ):
            if isinstance(event, AgentRunResultEvent):
                result_event = event
                continue

            if isinstance(event, PartDeltaEvent):
                if isinstance(event.delta, TextPartDelta):
                    text_buffer += event.delta.content_delta
                    await maybe_flush()

            elif isinstance(event, FunctionToolCallEvent):
                await flush_text()
                tool_id_counter += 1
                call_id = event.part.tool_call_id or f'tool_{tool_id_counter}'
                await streamer.append(
                    chunks=[
                        TaskUpdateChunk(
                            id=call_id,
                            title=f'Calling {event.part.tool_name}...',
                            status='in_progress',
                        ),
                    ],
                )

            elif isinstance(event, FunctionToolResultEvent):
                await flush_text()
                result_part = event.result
                tool_name = getattr(result_part, 'tool_name', None) or 'tool'
                call_id = result_part.tool_call_id or f'tool_{tool_id_counter}'
                outcome = getattr(result_part, 'outcome', 'success')
                status = 'error' if outcome == 'failed' else 'complete'
                await streamer.append(
                    chunks=[
                        TaskUpdateChunk(
                            id=call_id,
                            title=tool_name,
                            status=status,
                        ),
                    ],
                )

                # Upload screenshot files to the Slack thread
                if tool_name.startswith('browser_screenshot'):
                    try:
                        content = getattr(result_part, 'content', '')
                        parsed = json.loads(content) if isinstance(content, str) else {}
                        file_path = parsed.get('path', '')
                        if file_path and os.path.isfile(file_path):
                            await client.files_upload_v2(
                                channel=channel_id,
                                thread_ts=thread_ts,
                                file=file_path,
                                filename='screenshot.png',
                                initial_comment='',
                            )
                    except Exception:
                        logger.exception('Failed to upload screenshot to Slack')

        # Flush remaining text
        await flush_text()

        # Save conversation history
        if result_event is not None:
            await store.save(thread_key, result_event.result.all_messages())

    except Exception:
        logger.exception('Agent streaming error')
        if text_buffer:
            try:
                await streamer.append(markdown_text=text_buffer)
            except Exception:
                pass
        try:
            await streamer.append(markdown_text='\n\n:warning: An error occurred while processing.')
        except Exception:
            pass
    finally:
        try:
            await streamer.stop()
        except Exception:
            logger.exception('Failed to stop Slack stream')
