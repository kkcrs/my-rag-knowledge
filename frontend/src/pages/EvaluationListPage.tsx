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
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'

import {
  useCreateEvaluationRun,
  useDeleteEvaluationRun,
  useEvaluationDatasets,
  useEvaluationRuns,
} from '@/api/evaluation'
import type { EvaluationRunListItem } from '@/client/types.gen'

const { Title } = Typography

const STATUS_MAP: Record<string, { color: string; label: string }> = {
  running: { color: 'processing', label: '评测中' },
  completed: { color: 'success', label: '已完成' },
  failed: { color: 'error', label: '失败' },
}

function pct(v: number | null | undefined) {
  if (v === null || v === undefined) return '-'
  return `${(v * 100).toFixed(1)}%`
}

const columns: ColumnsType<EvaluationRunListItem> = [
  {
    title: '名称',
    dataIndex: 'name',
    ellipsis: true,
    render: (name: string, record) => (
      <Link to={`/evaluation/runs/${record.id}`}>{name}</Link>
    ),
  },
  { title: '数据集', dataIndex: 'dataset_name', width: 120 },
  {
    title: '进度',
    key: 'progress',
    width: 180,
    render: (_, r) => `${r.progress_completed} / ${r.progress_total}`,
  },
  {
    title: '拒绝准确率',
    dataIndex: 'refusal_accuracy',
    width: 110,
    render: pct,
  },
  {
    title: '引用命中率',
    dataIndex: 'citation_hit_rate',
    width: 110,
    render: pct,
  },
  {
    title: 'Faithfulness',
    dataIndex: 'faithfulness',
    width: 110,
    render: pct,
  },
  {
    title: 'Answer Relevancy',
    dataIndex: 'answer_relevancy',
    width: 130,
    render: pct,
  },
  {
    title: '延迟',
    dataIndex: 'avg_latency_ms',
    width: 100,
    render: (v: number | null) => (v != null ? `${v.toFixed(0)}ms` : '-'),
  },
  {
    title: '状态',
    dataIndex: 'status',
    width: 90,
    render: (s: string) => {
      const meta = STATUS_MAP[s]
      return meta ? <Tag color={meta.color}>{meta.label}</Tag> : s
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 60,
    render: (_, record) => (
      <DeleteRunButton runId={record.id} runName={record.name} />
    ),
  },
]

export function EvaluationListPage() {
  const [page, setPage] = useState(1)
  const pageSize = 20
  const { data, isLoading } = useEvaluationRuns(page, pageSize)
  const [modalOpen, setModalOpen] = useState(false)

  return (
    <div style={{ padding: 24 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <Title level={3} style={{ margin: 0 }}>
          评测任务
        </Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setModalOpen(true)}
        >
          新建评测
        </Button>
      </div>
      <Table
        rowKey="id"
        loading={isLoading}
        columns={columns}
        dataSource={data?.items ?? []}
        pagination={{
          current: page,
          pageSize,
          total: data?.total ?? 0,
          onChange: (p) => setPage(p),
          showSizeChanger: false,
        }}
        scroll={{ x: 1400 }}
      />
      <CreateRunModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  )
}

function CreateRunModal({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const { message } = App.useApp()
  const datasets = useEvaluationDatasets()
  const mutation = useCreateEvaluationRun()
  const [form] = Form.useForm<{ name: string; dataset_name: string }>()

  return (
    <Modal
      title="新建评测"
      open={open}
      onCancel={onClose}
      destroyOnClose
      onOk={async () => {
        const values = await form.validateFields()
        await mutation.mutateAsync(values)
        message.success('评测已创建，正在后台执行')
        form.resetFields()
        onClose()
      }}
      confirmLoading={mutation.isPending}
      okText="开始评测"
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{ name: '', dataset_name: '' }}
      >
        <Form.Item
          name="name"
          label="评测名称"
          rules={[{ required: true, message: '请输入名称' }, { max: 256 }]}
        >
          <Input placeholder="如：接入 rerank 对比测试" />
        </Form.Item>
        <Form.Item
          name="dataset_name"
          label="评测集"
          rules={[{ required: true, message: '请选择评测集' }]}
        >
          <Select
            loading={datasets.isLoading}
            options={(datasets.data?.items ?? []).map((d) => ({
              value: d.name,
              label: `${d.name} (${d.size} 条)`,
            }))}
            placeholder="选择评测集"
          />
        </Form.Item>
      </Form>
    </Modal>
  )
}

function DeleteRunButton({
  runId,
  runName,
}: {
  runId: string
  runName: string
}) {
  const { message } = App.useApp()
  const mutation = useDeleteEvaluationRun()

  return (
    <Popconfirm
      title={`删除评测 "${runName}"`}
      description="该 run 及其关联 case 都会被删除"
      okType="danger"
      okText="删除"
      cancelText="取消"
      onConfirm={async () => {
        await mutation.mutateAsync(runId)
        message.success('已删除')
      }}
    >
      <Button
        type="text"
        danger
        icon={<DeleteOutlined />}
        loading={mutation.isPending}
      />
    </Popconfirm>
  )
}
