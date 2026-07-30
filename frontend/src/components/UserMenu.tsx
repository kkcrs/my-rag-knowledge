import { useQueryClient } from '@tanstack/react-query'
import { App as AntdApp, Avatar, Dropdown, Space, Tag, Typography } from 'antd'
import type { MenuProps } from 'antd'
import { LogoutOutlined, UserOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'

export function UserMenu() {
  const { message } = AntdApp.useApp()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  if (!user) return null

  const handleLogout = () => {
    logout()
    queryClient.clear()
    message.success('已退出登录')
    navigate('/login', { replace: true })
  }

  const items: MenuProps['items'] = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ]

  return (
    <Dropdown menu={{ items }} placement="bottomRight">
      <Space style={{ cursor: 'pointer' }}>
        <Avatar size="small" icon={<UserOutlined />} />
        <Typography.Text ellipsis style={{ maxWidth: 120 }}>
          {user.displayName}
        </Typography.Text>
        {user.isAdmin && (
          <Tag color="gold" style={{ marginInlineEnd: 0 }}>
            管理员
          </Tag>
        )}
      </Space>
    </Dropdown>
  )
}
