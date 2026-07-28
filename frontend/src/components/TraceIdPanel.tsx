import { Space, Tag, Tooltip, Typography } from 'antd'

const { Text } = Typography

interface TraceIdPanelProps {
  traceId: string | null | undefined
  traceUrl?: string | null
}

export function TraceIdPanel({ traceId, traceUrl }: TraceIdPanelProps) {
  if (!traceId) return null
  const short = traceId.length > 8 ? `${traceId.slice(0, 8)}…` : traceId

  return (
    <div
      style={{
        marginTop: 12,
        padding: '6px 10px',
        background: '#fafafa',
        borderRadius: 6,
        fontSize: 12,
      }}
    >
      <Space size={8} wrap>
        <Tag color="default" style={{ marginInlineEnd: 0 }}>
          Trace
        </Tag>
        <Tooltip title={traceId}>
          <Text
            type="secondary"
            copyable={{ text: traceId, tooltips: ['复制 trace_id', '已复制'] }}
            style={{ fontFamily: 'monospace' }}
          >
            {short}
          </Text>
        </Tooltip>
        {traceUrl ? (
          <a href={traceUrl} target="_blank" rel="noreferrer">
            在 LangSmith 中查看 ↗
          </a>
        ) : null}
      </Space>
    </div>
  )
}
