import { forwardRef, useImperativeHandle, useState } from 'react'
import { Collapse, Tag, Typography } from 'antd'
import { Link } from 'react-router-dom'
import type { CitationRead } from '@/client/types.gen'

type SourceTagMeta = { color: string; label: string }

function formatSourceTag(sources?: string[]): SourceTagMeta | null {
  if (!sources || sources.length === 0) return null
  const hasVector = sources.includes('vector')
  const hasKeyword = sources.includes('keyword')
  if (hasVector && hasKeyword) return { color: 'purple', label: '混合' }
  if (hasVector) return { color: 'blue', label: '向量' }
  if (hasKeyword) return { color: 'orange', label: '关键词' }
  return null
}

const { Paragraph } = Typography

export interface CitationListHandle {
    /** 展开第 n 条引用面板并将其滚动到视口中央，n 从 1 开始。 */
    expandAndScroll: (n: number) => void
}

interface CitationListProps {
    citations: CitationRead[]
    /** 用于生成唯一的 DOM 锚点，避免多条助手消息之间相互干扰。 */
    messageId: string
}

export const CitationList = forwardRef<CitationListHandle, CitationListProps>(
    function CitationList({ citations, messageId }, ref) {
        const [activeKey, setActiveKey] = useState<string[]>([])

        useImperativeHandle(
            ref,
            () => ({
                expandAndScroll: (n: number) => {
                    const target = citations.find((citation) => citation.ordinal === n)
                    if (!target) return

                    const key = panelKey(target)
                    setActiveKey((previous) =>
                        previous.includes(key) ? previous : [...previous, key],
                    )
                    requestAnimationFrame(() => {
                        document
                            .getElementById(anchorId(messageId, n))
                            ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
                    })
                },
            }),
            [citations, messageId],
        )

        if (citations.length === 0) return null

        const items = citations.map((citation) => {
            const sourceTag = formatSourceTag(citation.retrieval_meta?.sources)
            return {
            key: panelKey(citation),
            label: (
                <span id={anchorId(messageId, citation.ordinal)}>
                    <Tag color="blue" style={{ marginRight: 8 }}>{`[${citation.ordinal}]`}</Tag>
                    {
                        sourceTag ? (
                            <Tag color={sourceTag.color} style={{ marginInlineEnd: 8 }}>{sourceTag.label}</Tag>
                        ) : null
                    }
                    {citation.document_id ? (
                        <Link to={`/documents/${citation.document_id}`}>
                            {citation.document_name}
                        </Link>
                    ) : (
                        <span>{citation.document_name}</span>
                    )}
                    {citation.page_no != null ? (
                        <span style={{ marginLeft: 8, color: '#999' }}>
                            第 {citation.page_no} 页
                        </span>
                    ) : null}
                </span>
            ),
            children: (
                <Paragraph
                    style={{ whiteSpace: 'pre-wrap', marginBottom: 0, color: '#555' }}
                    ellipsis={{ rows: 6, expandable: true, symbol: '展开' }}
                >
                    {citation.quote}
                </Paragraph>
            ),
        }
        })



        return (
            <Collapse
                size="small"
                ghost
                items={items}
                activeKey={activeKey}
                onChange={(keys) => setActiveKey(typeof keys === 'string' ? [keys] : keys)}
                style={{ marginTop: 12, background: '#fafafa', borderRadius: 6 }}
            />
        )
    },
)

function anchorId(messageId: string, n: number): string {
    return `cite-${messageId}-${n}`
}

function panelKey(citation: CitationRead): string {
    return citation.id || `ord-${citation.ordinal}`
}
