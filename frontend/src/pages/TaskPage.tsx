import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Card, Col, Progress, Row, Space, Spin, Steps, Tag, Typography } from 'antd';
import { CheckCircle2, Clock, Loader2, ServerCog, XCircle } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';

import { getTask, getTaskLogs } from '../api/tasks';

const { Title, Text } = Typography;

export function TaskPage() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const numericTaskId = Number(taskId);
  const validTaskId = Number.isFinite(numericTaskId) && numericTaskId > 0;

  const taskQuery = useQuery({
    queryKey: ['task', numericTaskId],
    queryFn: () => getTask(numericTaskId),
    enabled: validTaskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'success' || status === 'failed' ? false : 2000;
    },
  });

  const logsQuery = useQuery({
    queryKey: ['task-logs', numericTaskId],
    queryFn: () => getTaskLogs(numericTaskId),
    enabled: validTaskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'success' || status === 'failed' ? false : 2000;
    },
  });

  if (!validTaskId) {
    return <Alert type="warning" showIcon message="任务 ID 无效" description="请从方案生成入口进入任务页。" />;
  }

  if (taskQuery.isLoading && !taskQuery.data) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
        <Spin />
      </div>
    );
  }

  if (taskQuery.isError) {
    return <Alert type="error" showIcon message="任务加载失败" description={taskQuery.error.message} />;
  }

  const task = taskQuery.data;
  const logs = logsQuery.data?.logs ?? [];
  const percent = task?.progress ?? logsQuery.data?.progress ?? 0;
  const isFinished = task?.status === 'success';
  const isFailed = task?.status === 'failed';

  const stepItems = logs.map((item) => ({
    title: mapStepTitle(item.step),
    description: item.status === 'running' ? '进行中' : item.status === 'success' ? '已完成' : item.status === 'failed' ? '失败' : '等待中',
    status: mapStepStatus(item.status),
    icon: item.status === 'running' ? <Loader2 className="animate-spin" size={22} color="#1890ff" /> : undefined,
  }));

  const currentStep = Math.max(
    0,
    logs.findIndex((item) => item.status === 'running'),
  );

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', paddingTop: 20 }}>
      <Row gutter={24}>
        <Col span={24}>
          <Card
            bordered={false}
            style={{
              borderRadius: 16,
              background: '#001529',
              color: '#fff',
              marginBottom: 24,
              boxShadow: '0 12px 24px rgba(0,0,0,0.1)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 24 }}>
              <div>
                <Title level={3} style={{ color: '#fff', margin: 0 }}>
                  <Space>
                    <ServerCog size={28} />
                    Agent 流水线生成中
                  </Space>
                </Title>
                <Text style={{ color: 'rgba(255,255,255,0.7)', display: 'block', marginTop: 8 }}>
                  任务状态、日志和结果均来自后端数据库。
                </Text>
              </div>
              <Progress
                type="circle"
                percent={percent}
                status={isFailed ? 'exception' : isFinished ? 'success' : 'active'}
                strokeColor={{ '0%': '#108ee9', '100%': '#87d068' }}
                trailColor="rgba(255,255,255,0.1)"
                format={(value) => <span style={{ color: '#fff' }}>{value}%</span>}
              />
            </div>
          </Card>
        </Col>

        <Col xs={24} md={8}>
          <Card title="生成节点" bordered={false} style={{ borderRadius: 16, height: '100%' }} bodyStyle={{ padding: '24px 24px 0' }}>
            <Steps direction="vertical" current={currentStep === -1 ? logs.length - 1 : currentStep} items={stepItems} />
          </Card>
        </Col>

        <Col xs={24} md={16}>
          <Card title="Agent 实时日志" bordered={false} style={{ borderRadius: 16, height: '100%', background: '#fafafa' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {logs.map((item) => (
                <motion.div
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3 }}
                  key={item.step}
                  style={{
                    padding: 16,
                    background: item.status === 'running' ? '#e6f7ff' : '#fff',
                    border: `1px solid ${item.status === 'running' ? '#91d5ff' : '#f0f0f0'}`,
                    borderRadius: 8,
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 12,
                  }}
                >
                  <div style={{ marginTop: 2 }}>{renderLogIcon(item.status)}</div>
                  <div>
                    <div style={{ marginBottom: 4 }}>
                      <Text strong>{mapStepTitle(item.step)}</Text>
                      <Tag color={tagColor(item.status)} style={{ marginLeft: 8, border: 0 }}>
                        {mapStatusText(item.status)}
                      </Tag>
                    </div>
                    <Text type="secondary" style={{ fontSize: 13 }}>
                      {item.message}
                    </Text>
                  </div>
                </motion.div>
              ))}
            </div>

            {isFailed && (
              <Alert style={{ marginTop: 24 }} type="error" showIcon message="方案生成失败" description={task?.error_message ?? '请稍后重试。'} />
            )}

            {isFinished && (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                style={{
                  marginTop: 32,
                  padding: 24,
                  background: '#f6ffed',
                  border: '1px solid #b7eb8f',
                  borderRadius: 12,
                  textAlign: 'center',
                }}
              >
                <CheckCircle2 size={48} color="#52c41a" style={{ marginBottom: 16 }} />
                <Title level={4}>方案已生成完成</Title>
                <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
                  已保存到数据库，并生成当前方案版本。
                </Text>
                <Button
                  type="primary"
                  size="large"
                  disabled={!task?.plan_id}
                  style={{ borderRadius: 8, background: '#13c2c2', borderColor: '#13c2c2' }}
                  onClick={() => task?.plan_id && navigate(`/plans/${task.plan_id}`)}
                >
                  查看完整方案
                </Button>
              </motion.div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

function mapStepTitle(step: string): string {
  const map: Record<string, string> = {
    task_created: '任务创建',
    queued: '进入队列',
    planning: '生成旅行方案',
    persisting: '保存方案与版本',
    completed: '任务完成',
  };
  return map[step] ?? step;
}

function mapStepStatus(status: string): 'wait' | 'process' | 'finish' | 'error' {
  if (status === 'success') return 'finish';
  if (status === 'running') return 'process';
  if (status === 'failed') return 'error';
  return 'wait';
}

function renderLogIcon(status: string) {
  if (status === 'success') return <CheckCircle2 size={18} color="#52c41a" />;
  if (status === 'failed') return <XCircle size={18} color="#ff4d4f" />;
  if (status === 'running') return <Loader2 size={18} color="#1890ff" className="animate-spin" />;
  return <Clock size={18} color="#8c8c8c" />;
}

function tagColor(status: string): string {
  if (status === 'success') return 'green';
  if (status === 'failed') return 'red';
  if (status === 'running') return 'blue';
  return 'default';
}

function mapStatusText(status: string): string {
  if (status === 'success') return 'Success';
  if (status === 'failed') return 'Failed';
  if (status === 'running') return 'Running';
  return 'Waiting';
}
