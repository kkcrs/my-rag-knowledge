import {
  Button,
  List,
  Popconfirm,
  Spin,
  Tooltip,
  Typography,
  message,
} from 'antd'
import {
  DeleteOutlined,
  MessageOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { conversationsQueryKey } from '@/api/queryKeys'
import { deleteConversation, listConversations } from '@/client/sdk.gen'
import type { ConversationListItem } from '@/client/types.gen'

const { Text } = Typography

// ─── 时间格式化 ───────────────────────────────────────────

/** 把 ISO 时间格式化成"X 分钟前 / X 小时前 / YYYY-MM-DD"。 */
function formatRelativeTime(iso: string): string {
    const date = new Date(iso)
    const diffMs = Date.now() - date.getTime()
    const minute = 60 * 1000
    const hour = 60 * minute
    const day = 24 * hour
    if (diffMs < minute) return '刚刚'
    if (diffMs < hour) return `${Math.floor(diffMs / minute)} 分钟前`
    if (diffMs < day) return `${Math.floor(diffMs / hour)} 小时前`
    if (diffMs < 7 * day) return `${Math.floor(diffMs / day)} 天前`
    return date.toISOString().slice(0, 10)
}

// ─── ConversationItem ─────────────────────────────────────

interface ConversationItemProps {
    item: ConversationListItem
    isActive: boolean
    isDeleting: boolean
    onSelect: () => void
    onDelete: () => void
}

function ConversationItem({
    item,
    isActive,
    isDeleting,
    onSelect,
    onDelete,
}: ConversationItemProps) {
    return (
        <List.Item
            style={{
                cursor: 'pointer',
                background: isActive ? '#e6f4ff' : 'transparent',
                padding: '8px 12px',
                borderRadius: 4,
                margin: '2px 8px',
                border: 'none',
            }}
            onClick={onSelect}
            actions={[
                <Popconfirm
                    key="del"
                    title="删除该会话？"
                    description="将一并删除会话内的所有消息和引用，无法恢复。"
                    okText="删除"
                    okButtonProps={{ danger: true }}
                    cancelText="取消"
                    onConfirm={(e) => {
                        e?.stopPropagation()
                        onDelete()
                    }}
                    onCancel={(e) => e?.stopPropagation()}
                >
                    <Tooltip title="删除会话">
                        <Button
                            type="text"
                            size="small"
                            danger
                            icon={<DeleteOutlined />}
                            loading={isDeleting}
                            onClick={(e) => e.stopPropagation()}
                        />
                    </Tooltip>
                </Popconfirm>,
            ]}
        >
            <List.Item.Meta
                avatar={<MessageOutlined style={{ color: isActive ? '#1677ff' : '#999' }} />}
                title={
                    <Text
                        ellipsis={{ tooltip: item.title }}
                        style={{
                            fontSize: 13,
                            fontWeight: isActive ? 600 : 400,
                            color: isActive ? '#1677ff' : undefined,
                        }}
                    >
                        {item.title}
                    </Text>
                }
                description={
                    <Text type="secondary" style={{ fontSize: 11 }}>
                        {item.message_count} 条 · {formatRelativeTime(item.updated_at)}
                    </Text>
                }
            />
        </List.Item>
    )
}

// ─── 主组件 ───────────────────────────────────────────────

interface ConversationSidebarProps {
  currentId: string | null
  onSelect: (id: string) => void
  onDelete: (deletedId: string) => void
  onCreateNew: () => void
  isCreating: boolean
}

export function ConversationSidebar({
  currentId,
  onSelect,
  onDelete,
  onCreateNew,
  isCreating,
}: ConversationSidebarProps) {
  const queryClient = useQueryClient()

  const conversationQuery = useQuery({
    queryKey: conversationsQueryKey,
    queryFn: async () => {
      const res = await listConversations({ query: { page: 1, page_size: 100 } })
      return res.data!
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await deleteConversation({ path: { conversation_id: id } })
      return id
    },
    onSuccess: async (id) => {
      message.success('已删除会话')
      await queryClient.invalidateQueries({ queryKey: conversationsQueryKey })
      if (id === currentId) onDelete(id)
    },
  })

  const items = conversationQuery.data?.items ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: 12, borderBottom: '1px solid #f0f0f0' }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          block
          onClick={onCreateNew}
          loading={isCreating}
        >
          新建对话
        </Button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {conversationQuery.isLoading ? (
          <div style={{ textAlign: 'center', padding: 24 }}>
            <Spin />
          </div>
        ) : items.length === 0 ? (
          <Text
            type="secondary"
            style={{ display: 'block', textAlign: 'center', padding: 24 }}
          >
            暂无会话，点上方"新建对话"开始
          </Text>
        ) : (
          <List
            size="small"
            dataSource={items}
            renderItem={(item) => (
              <ConversationItem
                key={item.id}
                item={item}
                isActive={item.id === currentId}
                isDeleting={
                  deleteMutation.isPending &&
                  deleteMutation.variables === item.id
                }
                onSelect={() => onSelect(item.id)}
                onDelete={() => deleteMutation.mutate(item.id)}
              />
            )}
          />
        )}
      </div>
    </div>
  )
}
