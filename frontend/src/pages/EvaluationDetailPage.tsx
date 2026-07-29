import { useState } from 'react'
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Drawer,
  Form,
  Input,
  Row,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { Link, useParams } from 'react-router-dom'

import {
  type BadCaseCategory,
  useEvaluationItems,
  useEvaluationRun,
  useUpdateEvaluationItem,
} from '@/api/evaluation'
import type { EvaluationItemRead } from '@/client/types.gen'
import { MetricsCard } from '@/components/MetricsCard'
import { BadCaseCategorySelect } from '@/components/BadCaseCategorySelect'
import { BAD_CASE_CATEGORY_LABELS } from '@/utils/badCaseCategory'

const { Paragraph, Text, Title } = Typography

function pct(v: number | null | undefined) {
  if (v === null || v === undefined) return '-'
  return `${(v * 100).toFixed(1)}%`
}

function boolTag(v: boolean | null | undefined) {
  if (v === null || v === undefined) return <Tag>-</Tag>
  return v ? <Tag color="success">是</Tag> : <Tag color="error">否</Tag>
}

const columns: ColumnsType<EvaluationItemRead> = [
  { title: 'Case ID', dataIndex: 'case_id', width: 100 },
  { title: 'Question', dataIndex: 'question', ellipsis: true },
  { title: '应拒答', dataIndex: 'should_refuse', width: 80, render: boolTag },
  { title: '实际拒答', dataIndex: 'actual_refused', width: 90, render: boolTag },
  { title: '拒答正确', dataIndex: 'refusal_correct', width: 90, render: boolTag },
  { title: '引用命中', dataIndex: 'citation_hit', width: 90, render: boolTag },
  { title: 'Faith.', dataIndex: 'faithfulness', width: 80, render: pct },
  { title: 'Rel.', dataIndex: 'answer_relevancy', width: 80, render: pct },
  { title: 'Ctx P.', dataIndex: 'context_precision', width: 80, render: pct },
  { title: 'Ctx R.', dataIndex: 'context_recall', width: 80, render: pct },
  {
    title: 'Bad Case',
    width: 160,
    render: (_: unknown, record: EvaluationItemRead) => {
      if (!record.is_bad_case) return <Tag>正常</Tag>
      const label = record.bad_case_category
        ? BAD_CASE_CATEGORY_LABELS[record.bad_case_category]
        : '未归因'
      return <Tag color="red">{label}</Tag>
    },
  },
]

export function EvaluationDetailPage() {
  const { id: runId } = useParams<{ id: string }>()
  const { data: run } = useEvaluationRun(runId)

  const [page, setPage] = useState(1)
  const pageSize = 20
  const [badCaseOnly, setBadCaseOnly] = useState(false)
  const [category, setCategory] = useState<BadCaseCategory | null>(null)
  const { data: items, isLoading } = useEvaluationItems(runId!, {
    page,
    pageSize,
    badCaseOnly,
    category,
  })

  const [activeItem, setActiveItem] = useState<EvaluationItemRead | null>(null)

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16 }}>
        <Link to="/evaluation">
          <Button icon={<ArrowLeftOutlined />}>返回列表</Button>
        </Link>
        <Title level={3} style={{ margin: 0 }}>
          {run?.name ?? '加载中...'}
        </Title>
      </Space>

      <Text type="secondary">
        评测集 {run?.dataset_name} ({run?.dataset_size} 条)，状态 {run?.status}
        {run?.status === 'running' && (
          <>，进度 {run.progress_completed} / {run.progress_total}</>
        )}
      </Text>

      {run?.status === 'failed' && (
        <Alert
          type="error"
          showIcon
          message="评测执行失败"
          description={run.error_message ?? '未知错误'}
          style={{ marginTop: 16 }}
        />
      )}

      <Row gutter={[12, 12]} style={{ marginTop: 16 }}>
        <Col xs={12} md={6}>
          <MetricsCard label="Faithfulness" value={run?.faithfulness} />
        </Col>
        <Col xs={12} md={6}>
          <MetricsCard label="Answer Relevancy" value={run?.answer_relevancy} />
        </Col>
        <Col xs={12} md={6}>
          <MetricsCard label="Context Precision" value={run?.context_precision} />
        </Col>
        <Col xs={12} md={6}>
          <MetricsCard label="Context Recall" value={run?.context_recall} />
        </Col>
        <Col xs={12} md={6}>
          <MetricsCard label="引用命中率" value={run?.citation_hit_rate} />
        </Col>
        <Col xs={12} md={6}>
          <MetricsCard label="拒答正确率" value={run?.refusal_accuracy} />
        </Col>
        <Col xs={12} md={6}>
          <MetricsCard
            label="平均耗时"
            value={run?.avg_latency_ms}
            passthrough
            suffix=" ms"
          />
        </Col>
        <Col xs={12} md={6}>
          <MetricsCard
            label="首 token 延迟"
            value={run?.avg_first_token_latency_ms}
            passthrough
            suffix=" ms"
          />
        </Col>
      </Row>

      <div style={{ marginTop: 16 }}>
        <Space wrap>
          <span>仅看 Bad Case</span>
          <Switch
            checked={badCaseOnly}
            onChange={(v) => {
              setBadCaseOnly(v)
              setPage(1)
            }}
          />
          <span style={{ marginLeft: 16 }}>归因类型:</span>
          <BadCaseCategorySelect
            value={category}
            onChange={(v) => {
              setCategory(v)
              setPage(1)
            }}
          />
        </Space>

        <Table
          rowKey="case_id"
          size="small"
          style={{ marginTop: 16 }}
          dataSource={items?.items ?? []}
          loading={isLoading}
          columns={columns}
          onRow={(record) => ({
            onClick: () => setActiveItem(record),
            style: { cursor: 'pointer' },
          })}
          pagination={{
            current: page,
            pageSize,
            total: items?.total ?? 0,
            onChange: (p) => setPage(p),
            showSizeChanger: false,
          }}
          scroll={{ x: 1200 }}
        />
      </div>

      <ItemDrawer
        key={activeItem?.id ?? 'none'}
        runId={runId!}
        item={activeItem}
        onClose={() => setActiveItem(null)}
      />
    </div>
  )
}

function ItemDrawer({
  runId,
  item,
  onClose,
}: {
  runId: string
  item: EvaluationItemRead | null
  onClose: () => void
}) {
  const { message } = App.useApp()
  const mutation = useUpdateEvaluationItem(runId)
  const [note, setNote] = useState(() => item?.bad_case_note ?? '')
  const [editedCategory, setEditedCategory] = useState<BadCaseCategory | null>(
    () => item?.bad_case_category ?? null,
  )
  const [editedIsBadCase, setEditedIsBadCase] = useState(
    () => item?.is_bad_case ?? false,
  )

  return (
    <Drawer
      open={!!item}
      onClose={onClose}
      title={item ? `Case ${item.case_id}` : ''}
      width={720}
      destroyOnClose
    >
      {item && (
        <div>
          <Card size="small" title="问题" style={{ marginBottom: 12 }}>
            <Paragraph style={{ marginBottom: 0 }}>{item.question}</Paragraph>
            <Space wrap>
              {(item.tags ?? []).map((t) => (
                <Tag key={t}>{t}</Tag>
              ))}
              {item.should_refuse && <Tag color="orange">应拒答</Tag>}
            </Space>
          </Card>

          <Card size="small" title="期望答案" style={{ marginTop: 12 }}>
            <Paragraph>{item.expected_answer || '-'}</Paragraph>
            <Space wrap size={4}>
              <Text type="secondary">预期文档:</Text>
              {(item.expected_document_names ?? []).length === 0 ? (
                <Text type="secondary">-</Text>
              ) : (
                (item.expected_document_names ?? []).map((n) => (
                  <Tag key={n}>{n}</Tag>
                ))
              )}
            </Space>
            <br />
            <Space wrap size={4}>
              <Text type="secondary">关键词:</Text>
              {(item.expected_keywords ?? []).length === 0 ? (
                <Text type="secondary">-</Text>
              ) : (
                (item.expected_keywords ?? []).map((k) => (
                  <Tag color="blue" key={k}>
                    {k}
                  </Tag>
                ))
              )}
            </Space>
          </Card>

          <Card size="small" title="实际答案" style={{ marginTop: 12 }}>
            {item.error_message ? (
              <Alert
                type="error"
                message="执行异常"
                description={item.error_message}
              />
            ) : (
              <>
                {item.actual_refused && <Tag color="orange">已拒答</Tag>}
                <Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                  {item.actual_answer || '-'}
                </Paragraph>
              </>
            )}
          </Card>

          <Card size="small" title="指标与归因" style={{ marginTop: 12 }}>
            <Row gutter={[8, 8]} style={{ marginBottom: 12 }}>
              <Col span={12}>
                <Text type="secondary">Faithfulness: </Text>
                <Text>{pct(item.faithfulness)}</Text>
              </Col>
              <Col span={12}>
                <Text type="secondary">Answer Relevancy: </Text>
                <Text>{pct(item.answer_relevancy)}</Text>
              </Col>
              <Col span={12}>
                <Text type="secondary">Context Precision: </Text>
                <Text>{pct(item.context_precision)}</Text>
              </Col>
              <Col span={12}>
                <Text type="secondary">Context Recall: </Text>
                <Text>{pct(item.context_recall)}</Text>
              </Col>
              <Col span={12}>
                <Text type="secondary">引用命中: </Text>
                {boolTag(item.citation_hit)}
              </Col>
              <Col span={12}>
                <Text type="secondary">拒答正确: </Text>
                {boolTag(item.refusal_correct)}
              </Col>
            </Row>

            <Form layout="vertical">
              <Form.Item label="是 Bad Case">
                <Switch
                  checked={editedIsBadCase}
                  onChange={(v) => {
                    setEditedIsBadCase(v)
                    if (!v) setEditedCategory(null)
                  }}
                />
              </Form.Item>
              <Form.Item label="归因类别">
                <BadCaseCategorySelect
                  value={editedCategory}
                  onChange={(v) => {
                    setEditedCategory(v)
                    if (v) setEditedIsBadCase(true)
                  }}
                />
              </Form.Item>
              <Form.Item label="备注">
                <Input.TextArea
                  rows={3}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="补充说明（可选）"
                />
              </Form.Item>
              <Button
                type="primary"
                loading={mutation.isPending}
                onClick={async () => {
                  await mutation.mutateAsync({
                    itemId: item.id,
                    body: {
                      is_bad_case: editedIsBadCase,
                      bad_case_category: editedIsBadCase
                        ? editedCategory ?? null
                        : null,
                      bad_case_note: note || null,
                    },
                  })
                  message.success('已更新归因')
                }}
              >
                保存归因
              </Button>
            </Form>
          </Card>
        </div>
      )}
    </Drawer>
  )
}
