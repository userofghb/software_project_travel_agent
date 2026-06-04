import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Card, Col, Progress, Row, Space, Spin, Steps, Tag, Typography } from 'antd';
import { CheckCircle2, Clock, Home, Loader2, RefreshCw, ServerCog, Sparkles, XCircle } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';

import { getTask, getTaskLogs, type TaskLogItem } from '../api/tasks';

const { Title, Text } = Typography;

const POLL_INTERVAL_MS = 2000;
const STALE_WARNING_MS = 90_000;
const AUTO_NAVIGATE_SECONDS = 4;

const STEP_DEFS = [
  { step: 'task_created', title: '任务创建', message: '正在接收你的目的地、日期和偏好。' },
  { step: 'queued', title: '进入队列', message: '已进入生成队列，正在准备规划。' },
  { step: 'planning', title: '生成旅行方案', message: '正在综合画像、天气、景点、餐饮、住宿和预算。' },
  { step: 'persisting', title: '保存方案与版本', message: '正在保存方案内容、预算拆解和天气预警。' },
  { step: 'completed', title: '任务完成', message: '方案已生成，可以查看详情。' },
];

const WAITING_TIPS = [
  '正在把用户画像和天气约束合并进每日安排。',
  '正在为三餐、住宿和景点补齐可展示信息。',
  '生成可能需要几十秒，尤其是需要匹配地图点位和餐饮地点时。',
  '你可以停留在此页，完成后会自动跳转到方案详情。',
];

export function TaskPage() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const numericTaskId = Number(taskId);
  const validTaskId = Number.isFinite(numericTaskId) && numericTaskId > 0;
  const [now, setNow] = useState(() => Date.now());
  const [autoNavigateCountdown, setAutoNavigateCountdown] = useState(AUTO_NAVIGATE_SECONDS);

  const taskQuery = useQuery({
    queryKey: ['task', numericTaskId],
    queryFn: () => getTask(numericTaskId),
    enabled: validTaskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'success' || status === 'failed' ? false : POLL_INTERVAL_MS;
    },
    retry: 3,
  });

  const logsQuery = useQuery({
    queryKey: ['task-logs', numericTaskId],
    queryFn: () => getTaskLogs(numericTaskId),
    enabled: validTaskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'success' || status === 'failed' ? false : POLL_INTERVAL_MS;
    },
    retry: 3,
  });

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const task = taskQuery.data;
    if (task?.status !== 'success' || !task.plan_id) {
      setAutoNavigateCountdown(AUTO_NAVIGATE_SECONDS);
      return;
    }
    if (autoNavigateCountdown <= 0) {
      navigate(`/plans/${task.plan_id}`, { replace: true });
      return;
    }
    const timer = window.setTimeout(() => setAutoNavigateCountdown((value) => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [autoNavigateCountdown, navigate, taskQuery.data]);

  const refresh = () => {
    void taskQuery.refetch();
    void logsQuery.refetch();
  };

  const task = taskQuery.data;
  const rawLogs = logsQuery.data?.logs ?? [];
  const logs = useMemo(() => mergeLogs(rawLogs, task?.status ?? 'pending'), [rawLogs, task?.status]);
  const percent = task?.progress ?? logsQuery.data?.progress ?? 0;
  const isFinished = task?.status === 'success';
  const isFailed = task?.status === 'failed';
  const isWorking = !isFinished && !isFailed;
  const startedAt = task?.created_at ? parseServerTime(task.created_at) : now;
  const updatedAt = task?.updated_at ? parseServerTime(task.updated_at) : startedAt;
  const elapsedSeconds = Math.max(0, Math.floor((now - startedAt) / 1000));
  const staleSeconds = Math.max(0, Math.floor((now - updatedAt) / 1000));
  const showSlowWarning = isWorking && now - updatedAt > STALE_WARNING_MS;
  const activeLog = logs.find((item) => item.status === 'running') ?? logs.find((item) => item.status === 'waiting') ?? logs[logs.length - 1];
  const tip = WAITING_TIPS[Math.floor(elapsedSeconds / 8) % WAITING_TIPS.length];

  const stepItems = logs.map((item) => ({
    title: mapStepTitle(item.step),
    description: item.status === 'running' ? '进行中' : item.status === 'success' ? '已完成' : item.status === 'failed' ? '失败' : '等待中',
    status: mapStepStatus(item.status),
    icon: item.status === 'running' ? <Loader2 className="animate-spin" size={22} color="#1890ff" /> : undefined,
  }));

  const runningIndex = logs.findIndex((item) => item.status === 'running');
  const currentStep = runningIndex === -1 ? Math.max(0, logs.findIndex((item) => item.status === 'waiting') - 1) : runningIndex;

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

  if (taskQuery.isError && !taskQuery.data) {
    return (
      <div style={{ maxWidth: 760, margin: '0 auto', paddingTop: 48 }}>
        <Alert
          type="error"
          showIcon
          message="任务加载失败"
          description={taskQuery.error.message || '暂时无法读取任务状态。'}
          action={
            <Space>
              <Button icon={<RefreshCw size={15} />} onClick={refresh}>重新加载</Button>
              <Button icon={<Home size={15} />} onClick={() => navigate('/')}>返回首页</Button>
            </Space>
          }
        />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', paddingTop: 20 }}>
      <Row gutter={[24, 24]}>
        <Col span={24}>
          <Card
            bordered={false}
            style={{
              borderRadius: 16,
              background: '#001529',
              color: '#fff',
              boxShadow: '0 12px 24px rgba(0,0,0,0.1)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 24 }}>
              <div>
                <Title level={3} style={{ color: '#fff', margin: 0 }}>
                  <Space>
                    <ServerCog size={28} />
                    {isFinished ? '方案生成完成' : isFailed ? '方案生成失败' : '正在生成旅行方案'}
                  </Space>
                </Title>
                <Text style={{ color: 'rgba(255,255,255,0.7)', display: 'block', marginTop: 8 }}>
                  {isWorking ? '可以稍等片刻，完成后会自动进入方案详情。' : '方案状态已更新。'}
                </Text>
                <Space size={8} style={{ marginTop: 16, flexWrap: 'wrap' }}>
                  <Tag color={isFinished ? 'green' : isFailed ? 'red' : 'blue'}>{mapStatusText(task?.status ?? 'pending')}</Tag>
                  <Tag color="cyan">已用时 {formatSeconds(elapsedSeconds)}</Tag>
                  {activeLog && <Tag color="geekblue">{mapStepTitle(activeLog.step)}</Tag>}
                </Space>
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

        <Col span={24}>
          <Card bordered={false} style={{ borderRadius: 16 }}>
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <Space style={{ justifyContent: 'space-between', width: '100%', alignItems: 'flex-start' }}>
                <Space align="start">
                  {isWorking ? <Loader2 className="animate-spin" size={22} color="#1890ff" /> : isFinished ? <CheckCircle2 size={22} color="#52c41a" /> : <XCircle size={22} color="#ff4d4f" />}
                  <div>
                    <Text strong>{activeLog ? mapStepTitle(activeLog.step) : '准备生成'}</Text>
                    <div style={{ marginTop: 4 }}>
                      <Text type="secondary">{activeLog?.message || tip}</Text>
                    </div>
                  </div>
                </Space>
                <Button icon={<RefreshCw size={15} />} onClick={refresh} loading={taskQuery.isFetching || logsQuery.isFetching}>
                  刷新状态
                </Button>
              </Space>

              {isWorking && (
                <Alert
                  type="info"
                  showIcon
                  icon={<Sparkles size={18} />}
                  message={tip}
                  description="地图点位、餐饮地点或天气信息匹配较慢时，进度可能会在某个阶段停留一会儿；只要方案仍在生成，页面会持续更新。"
                />
              )}

              {showSlowWarning && (
                <Alert
                  type="warning"
                  showIcon
                  message="这个任务比平时久一些"
                  description={`生成状态已有 ${formatSeconds(staleSeconds)} 没有更新。你可以继续等待，或刷新状态确认方案是否完成。`}
                />
              )}

              {(taskQuery.isError || logsQuery.isError) && task && (
                <Alert
                  type="warning"
                  showIcon
                  message="状态刷新暂时不稳定"
                  description="当前展示的是最近一次成功获取到的任务状态，页面会继续尝试刷新。"
                />
              )}
            </Space>
          </Card>
        </Col>

        <Col xs={24} md={8}>
          <Card title="生成节点" bordered={false} style={{ borderRadius: 16, height: '100%' }} bodyStyle={{ padding: '24px 24px 0' }}>
            <Steps direction="vertical" current={currentStep} items={stepItems} />
          </Card>
        </Col>

        <Col xs={24} md={16}>
          <Card title="生成进度" bordered={false} style={{ borderRadius: 16, height: '100%', background: '#fafafa' }}>
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
              <Alert
                style={{ marginTop: 24 }}
                type="error"
                showIcon
                message="方案生成失败"
                description={task?.error_message ?? '请稍后重试。'}
                action={
                  <Space>
                    <Button onClick={() => navigate('/')}>重新填写</Button>
                    <Button icon={<RefreshCw size={15} />} onClick={refresh}>刷新状态</Button>
                  </Space>
                }
              />
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
                  方案已保存，并生成当前版本。{task?.plan_id ? `${autoNavigateCountdown} 秒后自动打开详情。` : ''}
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

function mergeLogs(logs: TaskLogItem[], taskStatus: string): TaskLogItem[] {
  const byStep = new Map(logs.map((item) => [item.step, item]));
  return STEP_DEFS.map((definition, index) => {
    const existing = byStep.get(definition.step);
    if (existing) return existing;
    const status =
      taskStatus === 'success'
        ? 'success'
        : taskStatus === 'failed' && index >= STEP_DEFS.length - 2
          ? 'failed'
          : index === 0
            ? 'running'
            : 'waiting';
    return {
      step: definition.step,
      status,
      message: status === 'waiting' ? '等待前一步完成' : definition.message,
      progress: index * 20,
      timestamp: new Date().toISOString(),
    };
  });
}

function mapStepTitle(step: string): string {
  const local = STEP_DEFS.find((item) => item.step === step);
  if (local) return local.title;
  return step;
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
  if (status === 'pending') return 'Pending';
  if (status === 'success') return 'Success';
  if (status === 'failed') return 'Failed';
  if (status === 'running') return 'Running';
  return 'Waiting';
}

function parseServerTime(value: string): number {
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  const parsed = new Date(hasTimezone ? value : `${value}Z`).getTime();
  return Number.isFinite(parsed) ? parsed : Date.now();
}

function formatSeconds(total: number): string {
  if (total < 60) return `${total}秒`;
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return seconds ? `${minutes}分${seconds}秒` : `${minutes}分`;
}
