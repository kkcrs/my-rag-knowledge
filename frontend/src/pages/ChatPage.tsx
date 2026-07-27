import { useEffect, useMemo, useRef, useState } from 'react'
import type { ComponentProps, KeyboardEvent } from 'react'
import {
    Alert,
    Avatar,
    Button,
    Empty,
    Input,
    Space,
    Spin,
    Typography,
    message as antdMessage,
} from 'antd'
import { PlusOutlined, RobotOutlined, SendOutlined, UserOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { createConversation, getConversation } from '@/client/sdk.gen'
import type { CitationRead, MessageRead, QueryRouteRead } from '@/client/types.gen'
import { streamChat, type ChatStreamEvent } from '@/api/chatStream'
import { gfmComponents } from '@/components/markdownComponents'
import { CitationList, type CitationListHandle } from '@/components/CitationList'
import { QueryRoutePanel } from '@/components/QueryRoutePanel'
import { formatApiError } from '@/utils/errors'

const { Title, Paragraph, Text } = Typography
const { TextArea } = Input

const STORAGE_KEY = 'rag.chat.conversation_id'

type AssistantStatus = 'streaming' | 'done' | 'error'

interface UiMessage {
    id: string
    role: 'user' | 'assistant'
    content: string
    citations: CitationRead[]
    queryRoute?: QueryRouteRead | null
    status?: AssistantStatus
    error?: string | null
}

function fromServerMessage(message: MessageRead): UiMessage {
    return {
        id: message.id,
        role: message.role === 'assistant' ? 'assistant' : 'user',
        content: message.content,
        citations: message.citations ?? [],
        queryRoute: message.query_route ?? null,
        status: 'done',
    }
}

export function ChatPage() {
    const queryClient = useQueryClient()
    const [conversationId, setConversationId] = useState<string | null>(() =>
        localStorage.getItem(STORAGE_KEY),
    )
    const [draft, setDraft] = useState('')
    // 流式过程中的临时消息只保存在前端，结束后由历史接口返回正式消息。
    const [pendingMessages, setPendingMessages] = useState<UiMessage[]>([])
    const [isStreaming, setIsStreaming] = useState(false)
    const abortRef = useRef<AbortController | null>(null)
    const scrollRef = useRef<HTMLDivElement>(null)

    const createMutation = useMutation({
        mutationFn: async () => {
            const response = await createConversation({ body: { title: '新对话' } })
            return response.data!
        },
        onSuccess: (conversation) => {
            localStorage.setItem(STORAGE_KEY, conversation.id)
            setConversationId(conversation.id)
            setPendingMessages([])
            queryClient.removeQueries({ queryKey: ['conversation'] })
        },
        onError: (error) => {
            antdMessage.error(error instanceof Error ? error.message : '创建对话失败')
        },
    })

    // 首次进入页面且没有本地会话时，自动创建一个会话。
    useEffect(() => {
        if (!conversationId && !createMutation.isPending) {
            createMutation.mutate()
        }
        // createMutation is intentionally omitted to avoid re-running after mutation state changes.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [conversationId])

    const historyQuery = useQuery({
        queryKey: ['conversation', conversationId],
        queryFn: async () => {
            const response = await getConversation({ path: { conversation_id: conversationId! } })
            return response.data!
        },
        enabled: Boolean(conversationId),
    })

    // 历史消息更新后，过滤掉已经被服务端正式消息覆盖的临时消息。
    const allMessages = useMemo<UiMessage[]>(() => {
        const history = (historyQuery.data?.messages ?? []).map(fromServerMessage)
        const historyIds = new Set(history.map((message) => message.id))
        const filteredPending = pendingMessages.filter((message) => !historyIds.has(message.id))
        return [...history, ...filteredPending]
    }, [historyQuery.data, pendingMessages])

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
    }, [allMessages])

    useEffect(() => {
        return () => {
            abortRef.current?.abort()
        }
    }, [])

    const handleNewConversation = () => {
        abortRef.current?.abort()
        createMutation.mutate()
    }

    const updateAssistant = (updater: (previous: UiMessage) => UiMessage) => {
        setPendingMessages((previous) => {
            if (previous.length === 0) return previous
            const lastIndex = previous.length - 1
            const lastMessage = previous[lastIndex]
            if (!lastMessage) return previous
            const next = previous.slice()
            next[lastIndex] = updater(lastMessage)
            return next
        })
    }

    const updatePendingUserId = (userMessageId: string) => {
        if (!userMessageId) return
        setPendingMessages((previous) => {
            const userIndex = previous.length - 2
            const userMessage = previous[userIndex]
            if (!userMessage || userMessage.role !== 'user') return previous
            const next = previous.slice()
            next[userIndex] = { ...userMessage, id: userMessageId }
            return next
        })
    }

    const handleSend = async () => {
        const question = draft.trim()
        if (!question || !conversationId || isStreaming) return

        setDraft('')
        const timestamp = Date.now()
        const userMessage: UiMessage = {
            id: `local-user-${timestamp}`,
            role: 'user',
            content: question,
            citations: [],
            status: 'done',
        }
        const assistantMessage: UiMessage = {
            id: `local-assistant-${timestamp}`,
            role: 'assistant',
            content: '',
            citations: [],
            status: 'streaming',
        }
        setPendingMessages((previous) => [...previous, userMessage, assistantMessage])
        setIsStreaming(true)

        const controller = new AbortController()
        abortRef.current = controller

        try {
            await streamChat({
                conversationId,
                question,
                signal: controller.signal,
                onEvent: (event: ChatStreamEvent) => {
                    switch (event.type) {
                        case 'start':
                            updatePendingUserId(event.userMessageId)
                            break
                        case 'query_route':
                            updateAssistant((previous) => ({
                                ...previous,
                                queryRoute: event.queryRoute,
                            }))
                            break
                        case 'citations':
                            updateAssistant((previous) => ({ ...previous, citations: event.citations }))
                            break
                        case 'token':
                            updateAssistant((previous) => ({
                                ...previous,
                                content: previous.content + event.delta,
                            }))
                            break
                        case 'end':
                            updateAssistant((previous) => ({ ...previous, status: 'done' }))
                            break
                        case 'error':
                            updateAssistant((previous) => ({
                                ...previous,
                                status: 'error',
                                error: event.message,
                            }))
                            break
                    }
                },
            })
            await queryClient.invalidateQueries({ queryKey: ['conversation', conversationId] })
            setPendingMessages([])
        } catch (error) {
            const fallback =
                error instanceof Response
                    ? await formatApiError(error)
                    : error instanceof Error
                      ? error.message
                      : '请求失败'
            updateAssistant((previous) => ({
                ...previous,
                status: 'error',
                error: fallback,
            }))
            antdMessage.error(fallback)
            await queryClient
                .invalidateQueries({ queryKey: ['conversation', conversationId] })
                .catch(() => undefined)
        } finally {
            setIsStreaming(false)
            abortRef.current = null
        }
    }

    const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
        // Shift+Enter 换行，Enter 发送。
        if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault()
            void handleSend()
        }
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)' }}>
            <Space style={{ marginBottom: 12, justifyContent: 'space-between', display: 'flex' }}>
                <div>
                    <Title level={3} style={{ marginBottom: 0 }}>
                        知识库问答
                    </Title>
                    <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                        基于已上传文档进行检索增强问答，引用来源可点击跳转到原文档。
                    </Paragraph>
                </div>
                <Button
                    icon={<PlusOutlined />}
                    onClick={handleNewConversation}
                    loading={createMutation.isPending}
                    disabled={isStreaming}
                >
                    新建对话
                </Button>
            </Space>
            <div
                ref={scrollRef}
                style={{
                    flex: 1,
                    overflowY: 'auto',
                    background: '#fff',
                    padding: 24,
                    borderRadius: 8,
                    border: '1px solid #f0f0f0',
                }}
            >
                {historyQuery.isLoading ? (
                    <Spin />
                ) : historyQuery.isError ? (
                    <Alert type="error" message="会话记录加载失败" showIcon />
                ) : allMessages.length === 0 ? (
                    <Empty description="还没有问题，在下方输入开始提问" />
                ) : (
                    allMessages.map((message) => (
                        <MessageBubble key={message.id} message={message} />
                    ))
                )}
            </div>
            <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
                <TextArea
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="输入你的问题，按 Enter 发送，Shift+Enter 换行"
                    autoSize={{ minRows: 2, maxRows: 6 }}
                    disabled={!conversationId || isStreaming}
                />
                <Button
                    type="primary"
                    icon={<SendOutlined />}
                    onClick={() => void handleSend()}
                    loading={isStreaming}
                    disabled={!conversationId || !draft.trim()}
                >
                    发送
                </Button>
            </div>
        </div>
    )
}

const CITATION_HASH_PREFIX = '#cite-'

/** 将答案中的引用编号 `[N]` 转为由 CitationList 处理的 Markdown 锚点链接。 */
function linkifyCitations(content: string, maxIndex: number, messageId: string): string {
    if (maxIndex <= 0) return content
    return content.replace(/\[(\d+)\]/g, (raw, number: string) => {
        const citationNumber = Number(number)
        if (citationNumber < 1 || citationNumber > maxIndex) return raw
        return `[[${citationNumber}]](${CITATION_HASH_PREFIX}${messageId}-${citationNumber})`
    })
}

interface MessageBubbleProps {
    message: UiMessage
}

function MessageBubble({ message }: MessageBubbleProps) {
    const isUser = message.role === 'user'
    const citationRef = useRef<CitationListHandle>(null)
    const components = {
        ...gfmComponents,
        a: (props: ComponentProps<'a'>) => {
            const href = props.href ?? ''
            if (href.startsWith(CITATION_HASH_PREFIX)) {
                const citationNumber = Number(href.split('-').pop())
                return (
                    <a
                        {...props}
                        href={href}
                        onClick={(event) => {
                            event.preventDefault()
                            if (Number.isFinite(citationNumber)) {
                                citationRef.current?.expandAndScroll(citationNumber)
                            }
                        }}
                    />
                )
            }
            return <a {...props} target="_blank" rel="noreferrer" />
        },
    }

    const renderedContent = useMemo(
        () => linkifyCitations(message.content, message.citations.length, message.id),
        [message.content, message.citations.length, message.id],
    )

    return (
        <div
            style={{
                display: 'flex',
                gap: 12,
                marginBottom: 24,
                flexDirection: isUser ? 'row-reverse' : 'row',
            }}
        >
            <Avatar
                icon={isUser ? <UserOutlined /> : <RobotOutlined />}
                style={{ background: isUser ? '#1677ff' : '#52c41a', flexShrink: 0 }}
            />
            <div
                style={{
                    maxWidth: '78%',
                    background: isUser ? '#e6f4ff' : '#f6f6f6',
                    padding: '12px 16px',
                    borderRadius: 8,
                }}
            >
                {message.error ? (
                    <Alert type="error" message={message.error} style={{ marginBottom: 8 }} />
                ) : null}
                {message.content ? (
                    isUser ? (
                        <Text style={{ whiteSpace: 'pre-wrap' }}>{message.content}</Text>
                    ) : (
                        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                            {renderedContent}
                        </ReactMarkdown>
                    )
                ) : message.status === 'streaming' ? (
                    <Text type="secondary">
                        <Spin size="small" /> 正在思考...
                    </Text>
                ) : null}
                {!isUser && message.queryRoute ? (
                    <QueryRoutePanel queryRoute={message.queryRoute} />
                ) : null}
                {!isUser && message.citations.length > 0 ? (
                    <CitationList
                        ref={citationRef}
                        citations={message.citations}
                        messageId={message.id}
                    />
                ) : null}
            </div>
        </div>
    )
}
