import { useState } from 'react'
import {
  App,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

import {
  useCreateRoleMutation,
  useDeleteRoleMutation,
  useRolesQuery,
  useUpdateRoleMutation,
} from '@/api/roles'
import type { RoleRead } from '@/client/types.gen'
import { PermissionTagsField } from '@/components/PermissionTagsField'

const { Title } = Typography

export function RolesPage() {
  const { data, isLoading } = useRolesQuery()
  const [modalOpen, setModalOpen] = useState(false)
  const [editingRole, setEditingRole] = useState<RoleRead | null>(null)

  const deleteMutation = useDeleteRoleMutation()
  const createMutation = useCreateRoleMutation()
  const updateMutation = useUpdateRoleMutation()

  const columns: ColumnsType<RoleRead> = [
    { title: '角色名', dataIndex: 'name', width: 120 },
    { title: '描述', dataIndex: 'description', width: 200 },
    {
      title: '权限标签',
      dataIndex: 'permission_tags',
      width: 300,
      render: (tags: string[]) =>
        tags?.length ? (
          <Space wrap size={4}>
            {tags.map((t) => (
              <Tag key={t}>{t}</Tag>
            ))}
          </Space>
        ) : (
          <Tag>无</Tag>
        ),
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
              setEditingRole(record)
              setModalOpen(true)
            }}
          >
            编辑
          </Button>
          <Popconfirm
            title="确认删除角色？"
            okType="danger"
            okText="删除"
            cancelText="取消"
            onConfirm={() => deleteMutation.mutate(record.id)}
          >
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const closeModal = () => {
    setModalOpen(false)
    setEditingRole(null)
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
          角色管理
        </Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setModalOpen(true)}
        >
          新建角色
        </Button>
      </div>

      <Table
        rowKey="id"
        loading={isLoading}
        columns={columns}
        dataSource={data ?? []}
        pagination={false}
      />

      <RoleFormModal
        open={modalOpen}
        editingRole={editingRole}
        onClose={closeModal}
        createMutation={createMutation}
        updateMutation={updateMutation}
      />
    </div>
  )
}

function RoleFormModal({
  open,
  editingRole,
  onClose,
  createMutation,
  updateMutation,
}: {
  open: boolean
  editingRole: RoleRead | null
  onClose: () => void
  createMutation: ReturnType<typeof useCreateRoleMutation>
  updateMutation: ReturnType<typeof useUpdateRoleMutation>
}) {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const isEdit = !!editingRole

  return (
    <Modal
      title={isEdit ? '编辑角色' : '新建角色'}
      open={open}
      onCancel={onClose}
      destroyOnClose
      onOk={async () => {
        const values = await form.validateFields()
        try {
          if (isEdit && editingRole) {
            await updateMutation.mutateAsync({
              id: editingRole.id,
              description: values.description,
              permission_tags: values.permission_tags ?? [],
            })
          } else {
            await createMutation.mutateAsync({
              name: values.name,
              description: values.description,
              permission_tags: values.permission_tags ?? [],
            })
          }
          message.success(isEdit ? '已保存' : '已创建')
          form.resetFields()
          onClose()
        } catch {
          // handled by interceptor
        }
      }}
      confirmLoading={createMutation.isPending || updateMutation.isPending}
      okText={isEdit ? '保存' : '创建'}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          name: editingRole?.name || '',
          description: editingRole?.description || '',
          permission_tags: editingRole?.permission_tags ?? [],
        }}
      >
        {!isEdit && (
          <Form.Item
            name="name"
            label="角色名"
            rules={[
              { required: true, message: '请输入角色名' },
              { max: 64 },
            ]}
          >
            <Input placeholder="角色名" />
          </Form.Item>
        )}
        <Form.Item name="description" label="描述">
          <Input placeholder="描述" />
        </Form.Item>
        <Form.Item name="permission_tags" label="权限标签">
          <PermissionTagsField placeholder="输入标签后回车，留空视为公开" />
        </Form.Item>
      </Form>
    </Modal>
  )
}
