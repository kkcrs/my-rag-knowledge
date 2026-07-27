import { fetchEventSource } from '@microsoft/fetch-event-source'
import type { CitationRead, QueryRouteRead } from '@/client/types.gen'

export interface ChatStartEvent {
    type: 'start'
    userMessageId: string
}

export interface ChatQueryRouteEvent {
    type: 'query_route'
    queryRoute: QueryRouteRead
}

export interface ChatCitationsEvent {
    type: 'citations'
    citations: CitationRead[]
}

export interface ChatTokenEvent {
    type: 'token'
    delta: string
}

export interface ChatEndEvent {
    type: 'end'
    message_id: string
    refused: boolean
}

export interface ChatErrorEvent {
    type: 'error'
    code: string
    message: string
}

export type ChatStreamEvent =
    | ChatStartEvent
    | ChatQueryRouteEvent
    | ChatCitationsEvent
    | ChatTokenEvent
    | ChatEndEvent
    | ChatErrorEvent

interface StreamChatParams {
    conversationId: string
    question: string
    signal?: AbortSignal
    onEvent: (event: ChatStreamEvent) => void
}

class FatalSseError extends Error {}

export async function streamChat({
    conversationId,
    question,
    signal,
    onEvent,
}: StreamChatParams): Promise<void> {
    let completed = false

    await fetchEventSource(`/api/conversations/${conversationId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
        signal,
        // 切换浏览器标签页时保持问答流连接。
        openWhenHidden: true,
        async onopen(response) {
            if (!response.ok) {
                const responseText = await response.text().catch(() => '')
                throw new FatalSseError(responseText || `HTTP ${response.status}`)
            }
            if (!response.headers.get('content-type')?.includes('text/event-stream')) {
                throw new FatalSseError('服务端未返回 SSE 事件流')
            }
        },
        onmessage(message) {
            if (!message.event) return
            const data = message.data ? JSON.parse(message.data) : {}
            switch (message.event) {
                case 'message_start':
                    onEvent({
                        type: 'start',
                        userMessageId: data.user_message_id,
                    })
                    break
                case 'query_route':
                    onEvent({ type: 'query_route', queryRoute: data as QueryRouteRead })
                    break
                case 'citations':
                    onEvent({ type: 'citations', citations: data.citations ?? [] })
                    break
                case 'token':
                    onEvent({ type: 'token', delta: data.delta ?? '' })
                    break
                case 'message_end':
                    completed = true
                    onEvent({
                        type: 'end',
                        message_id: data.message_id,
                        refused: Boolean(data.refused),
                    })
                    break
                case 'error': {
                    const errorMessage = data.message ?? '请求失败'
                    onEvent({
                        type: 'error',
                        code: data.code ?? 'error',
                        message: errorMessage,
                    })
                    throw new FatalSseError(errorMessage)
                }
            }
        },
        onclose() {
            if (!completed) {
                throw new FatalSseError('问答连接意外中断，请重试')
            }
        },
        onerror(error) {
            throw error
        },
    })
}
