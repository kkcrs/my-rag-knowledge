import { useState } from 'react'
import {
  App,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import {
  useAssignUserRolesMutation,
  useCreateUserMutation,
  useDeleteUserMutation,
  useUpdateUserMutation,
  useUsersQuery,
} from '@/api/users'
import { useAuthStore } from '@/stores/authStore'
import { useRolesQuery } from '@/api/roles'
import type { UserRead } from '@/client/types.gen'

const { Title } = Typography

export function UsersPage() {
  const [page, setPage] = useState(1)
  const { data, isLoading } = useUsersQuery(page, 20)
  const currentUserId = useAuthStore((s) => s.user?.id)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<UserRead | null>(null)

  const columns: ColumnsType<UserRead> = [
    { title: '用户名', dataIndex: 'username', width: 120 },
    { title: '昵称', dataIndex: 'display_name', width: 120 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 80,
      render: (s: string) =>
        s === 'active' ? (
          <Tag color="success">启用</Tag>
        ) : (
          <Tag color="error">禁用</Tag>
        ),
    },
    {
      title: '角色',
      dataIndex: 'roles',
      width: 200,
      render: (roles: Array<{ name: string }>) =>
        roles?.map((r) => <Tag key={r.name}>{r.name}</Tag>),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 180,
      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_, record) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              setEditingUser(record)
              setModalOpen(true)
            }}
          >
            编辑
          </Button>
          <Popconfirm
            title="确认删除用户？"
            okType="danger"
            okText="删除"
            cancelText="取消"
            disabled={record.id === currentUserId}
            onConfirm={() => deleteMutation.mutate(record.id)}
          >
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              disabled={record.id === currentUserId}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const deleteMutation = useDeleteUserMutation()
  const createMutation = useCreateUserMutation()
  const updateMutation = useUpdateUserMutation()
  const assignMutation = useAssignUserRolesMutation()

  const closeModal = () => {
    setModalOpen(false)
    setEditingUser(null)
  }

  return (
    <div style={{ padding: 24 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: 16,
        }}
      >
        <Title level={3} style={{ margin: 0 }}>
          用户管理
        </Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setModalOpen(true)}
        >
          新建用户
        </Button>
      </div>

      <Table
        rowKey="id"
        loading={isLoading}
        columns={columns}
        dataSource={data?.items ?? []}
        pagination={{
          current: page,
          pageSize: 20,
          total: data?.total ?? 0,
          onChange: setPage,
          showSizeChanger: false,
        }}
      />

      <UserFormModal
        open={modalOpen}
        editingUser={editingUser}
        onClose={closeModal}
        createMutation={createMutation}
        updateMutation={updateMutation}
        assignMutation={assignMutation}
        currentUserId={currentUserId}
      />
    </div>
  )
}

function UserFormModal({
  open,
  editingUser,
  onClose,
  createMutation,
  updateMutation,
  assignMutation,
  currentUserId,
}: {
  open: boolean
  editingUser: UserRead | null
  onClose: () => void
  createMutation: ReturnType<typeof useCreateUserMutation>
  updateMutation: ReturnType<typeof useUpdateUserMutation>
  assignMutation: ReturnType<typeof useAssignUserRolesMutation>
  currentUserId: string | undefined
}) {
  const { message } = App.useApp()
  const { data: rolesData } = useRolesQuery()
  const [form] = Form.useForm()
  const isEdit = !!editingUser
  const isSelf = editingUser?.id === currentUserId

  return (
    <Modal
      title={isEdit ? '编辑用户' : '新建用户'}
      open={open}
      onCancel={onClose}
      destroyOnClose
      onOk={async () => {
        const values = await form.validateFields()
        try {
          if (isEdit && editingUser) {
            await updateMutation.mutateAsync({
              id: editingUser.id,
              display_name: values.display_name,
              status: isSelf ? 'active' : values.status,
              password: values.password || undefined,
            } as never)
            await assignMutation.mutateAsync({
              userId: editingUser.id,
              roleIds: values.role_ids ?? [],
            })
          } else {
            const newUser = await createMutation.mutateAsync({
              username: values.username,
              password: values.password,
              display_name: values.display_name,
              role_ids: values.role_ids ?? [],
            })
            if (values.role_ids?.length) {
              await assignMutation.mutateAsync({
                userId: newUser.id,
                roleIds: values.role_ids,
              })
            }
          }
          message.success(isEdit ? '已保存' : '已创建')
          form.resetFields()
          onClose()
        } catch {
          // handled by interceptor
        }
      }}
      confirmLoading={
        createMutation.isPending ||
        updateMutation.isPending ||
        assignMutation.isPending
      }
      okText={isEdit ? '保存' : '创建'}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          username: editingUser?.username || '',
          display_name: editingUser?.display_name || '',
          status: editingUser?.status || 'active',
          password: '',
          role_ids: editingUser?.roles?.map((r) => r.id) ?? [],
        }}
      >
        {!isEdit && (
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 2, max: 64 },
            ]}
          >
            <Input placeholder="用户名" />
          </Form.Item>
        )}
        <Form.Item
          name="display_name"
          label="昵称"
          rules={[{ required: true, message: '请输入昵称' }]}
        >
          <Input placeholder="昵称" />
        </Form.Item>
        <Form.Item
          name="password"
          label={isEdit ? '新密码（留空不修改）' : '密码'}
          rules={
            isEdit
              ? undefined
              : [{ required: true, message: '请输入密码', min: 4 }]
          }
        >
          <Input.Password placeholder={isEdit ? '留空则不修改' : '密码'} />
        </Form.Item>
        {isEdit && !isSelf && (
          <Form.Item name="status" label="状态">
            <Select
              options={[
                { value: 'active', label: '启用' },
                { value: 'disabled', label: '禁用' },
              ]}
            />
          </Form.Item>
        )}
        <Form.Item name="role_ids" label="角色">
          <Select
            mode="multiple"
            placeholder="选择角色"
            options={(rolesData ?? []).map((r) => ({
              value: r.id,
              label: r.name,
            }))}
          />
        </Form.Item>
      </Form>
    </Modal>
  )
}
