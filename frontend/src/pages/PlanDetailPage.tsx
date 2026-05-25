import React, { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  Col,
  Divider,
  Drawer,
  Empty,
  Input,
  Row,
  Select,
  Space,
  Spin,
  Tabs,
  Tag,
  Timeline,
  Typography,
  message,
} from 'antd';
import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import dayjs from 'dayjs';
import {
  editPlanVersion,
  getPlan,
  getPlanSummary,
  listPlanVersions,
  regeneratePlan,
  restorePlanVersion,
} from '../api/plans';
import { getPlanWarnings } from '../api/warnings';
import type { TripPlanCreateRequest, TripPlanResponse, TripPlanVersionResponse } from '../api/types';
import { mockPlanDetail } from '../utils/mockData';
import {
  Map as MapIcon,
  SunSnow,
  Wallet,
  Activity,
  Clock,
  MapPin,
  Coffee,
  Camera,
  Bus,
  FileText,
  Wand2,
  History,
  RotateCcw,
} from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

const { Title, Text, Paragraph } = Typography;

const COLORS = ['#13c2c2', '#1890ff', '#faad14', '#eb2f96'];

type UiItineraryItem = {
  time: string;
  type: 'attraction' | 'food' | 'transport';
  title: string;
  reason: string;
  duration: string;
  budget: number;
  tags: string[];
};

type UiDay = {
  day: number;
  items: UiItineraryItem[];
};

type UiWeather = {
  day: string;
  temp: string;
  condition: string;
  risk: string;
  suggestion?: string;
};

type UiBudgetItem = {
  name: string;
  value: number;
};

type UiPlanDetail = {
  city: string;
  days: number;
  date: string;
  version: string;
  totalBudget: number;
  riskLevel: string;
  pace: string;
  budgetBreakdown: UiBudgetItem[];
  weather: UiWeather[];
  itinerary: UiDay[];
};

export function PlanDetailPage() {
  const { planId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const planIdNumber = Number(planId);
  const validPlanId = Number.isFinite(planIdNumber) && planIdNumber > 0;

  const [activeDay, setActiveDay] = useState('1');
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [editSummary, setEditSummary] = useState('详情页微调');
  const [regenBudgetRange, setRegenBudgetRange] = useState<string>('medium');
  const [regenNotes, setRegenNotes] = useState('');

  const planQuery = useQuery({
    queryKey: ['plan', planIdNumber],
    queryFn: () => getPlan(planIdNumber),
    enabled: validPlanId,
  });

  const summaryQuery = useQuery({
    queryKey: ['plan-summary', planIdNumber],
    queryFn: () => getPlanSummary(planIdNumber),
    enabled: validPlanId,
  });

  const warningsQuery = useQuery({
    queryKey: ['plan-warnings', planIdNumber],
    queryFn: () => getPlanWarnings(planIdNumber),
    enabled: validPlanId,
  });

  const versionsQuery = useQuery({
    queryKey: ['plan-versions', planIdNumber],
    queryFn: () => listPlanVersions(planIdNumber),
    enabled: validPlanId,
  });

  const versions = versionsQuery.data ?? [];
  const plan = planQuery.data;

  useEffect(() => {
    if (versions.length === 0) {
      setSelectedVersionId(null);
      return;
    }

    const exists = selectedVersionId != null && versions.some((item) => item.id === selectedVersionId);
    if (exists) {
      return;
    }

    const preferred = plan?.current_version_id;
    const preferredVersion = preferred == null ? null : versions.find((item) => item.id === preferred);
    if (preferredVersion) {
      setSelectedVersionId(preferredVersion.id);
      return;
    }

    setSelectedVersionId(versions[versions.length - 1].id);
  }, [versions, selectedVersionId, plan?.current_version_id]);

  const selectedVersion = useMemo(() => {
    if (selectedVersionId != null) {
      const matched = versions.find((item) => item.id === selectedVersionId);
      if (matched) return matched;
    }
    return plan?.current_version ?? null;
  }, [versions, selectedVersionId, plan?.current_version]);

  const uiPlan = useMemo(
    () =>
      buildUiPlan({
        fallback: mockPlanDetail,
        plan,
        summaryRiskLevel: summaryQuery.data?.risk_level,
        summaryPace: summaryQuery.data?.pace,
        summaryBudget: summaryQuery.data?.estimated_total,
        warnings: warningsQuery.data?.warnings,
        selectedVersion,
      }),
    [
      plan,
      summaryQuery.data?.risk_level,
      summaryQuery.data?.pace,
      summaryQuery.data?.estimated_total,
      warningsQuery.data?.warnings,
      selectedVersion,
    ],
  );

  useEffect(() => {
    const dayNumber = Number(activeDay);
    if (!Number.isFinite(dayNumber) || dayNumber < 1 || dayNumber > uiPlan.itinerary.length) {
      setActiveDay('1');
    }
  }, [activeDay, uiPlan.itinerary.length]);

  const activeDayIndex = Math.max(0, Number(activeDay) - 1);
  const activeWeather = uiPlan.weather[activeDayIndex];
  const activeItinerary = uiPlan.itinerary[activeDayIndex];

  const invalidatePlanQueries = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['plan', planIdNumber] }),
      queryClient.invalidateQueries({ queryKey: ['plan-summary', planIdNumber] }),
      queryClient.invalidateQueries({ queryKey: ['plan-versions', planIdNumber] }),
      queryClient.invalidateQueries({ queryKey: ['plan-warnings', planIdNumber] }),
    ]);
  };

  const restoreMutation = useMutation({
    mutationFn: (versionId: number) => restorePlanVersion(planIdNumber, versionId),
    onSuccess: async () => {
      message.success('已恢复到选中版本');
      await invalidatePlanQueries();
    },
    onError: (err: Error) => {
      message.error(err.message || '恢复失败');
    },
  });

  const editMutation = useMutation({
    mutationFn: ({ summary, content }: { summary: string; content: Record<string, unknown> }) => {
      if (!selectedVersion) {
        throw new Error('当前没有可编辑版本');
      }
      return editPlanVersion(planIdNumber, selectedVersion.id, {
        title: plan?.title,
        change_summary: summary,
        content,
      });
    },
    onSuccess: async () => {
      message.success('已创建新编辑版本');
      await invalidatePlanQueries();
    },
    onError: (err: Error) => {
      message.error(err.message || '编辑版本失败');
    },
  });

  const regenerateMutation = useMutation({
    mutationFn: (payload: TripPlanCreateRequest) => {
      if (!selectedVersion) {
        throw new Error('当前没有可再生成版本');
      }
      return regeneratePlan(planIdNumber, selectedVersion.id, payload);
    },
    onSuccess: (res) => {
      message.success('已提交再生成任务');
      setDrawerVisible(false);
      navigate(`/tasks/${res.task_id}`);
    },
    onError: (err: Error) => {
      message.error(err.message || '再生成失败');
    },
  });

  const onApplyLowerBudget = () => {
    const currentContent = getVersionContent(selectedVersion);
    const next = applyLowerBudget(currentContent);
    editMutation.mutate({
      summary: editSummary || '降低预算',
      content: next,
    });
  };

  const onApplySeniorMode = () => {
    const currentContent = getVersionContent(selectedVersion);
    const next = applySeniorMode(currentContent);
    editMutation.mutate({
      summary: editSummary || '调整为长辈模式',
      content: next,
    });
  };

  const onApplyRainAvoid = () => {
    const payload = buildRegeneratePayload(plan, regenBudgetRange, regenNotes || '规避降雨，增加室内活动');
    regenerateMutation.mutate(payload);
  };

  const selectedVersionText = selectedVersion ? `v${selectedVersion.version_no}` : uiPlan.version;

  if (!validPlanId) {
    return (
      <Alert
        type="warning"
        showIcon
        message="缺少方案 ID 参数"
        description="请从历史页面进入详情页，或在 URL 中携带 /plans/{planId}。"
      />
    );
  }

  if (planQuery.isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
        <Spin />
      </div>
    );
  }

  if (planQuery.isError) {
    return <Alert type="error" showIcon message="方案详情加载失败" description={planQuery.error.message} />;
  }

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', paddingBottom: 40 }}>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        style={{
          background: 'linear-gradient(120deg, #e6f7ff 0%, #ffffff 100%)',
          borderRadius: 24,
          padding: '32px 40px',
          marginBottom: 24,
          position: 'relative',
          border: '1px solid #91d5ff',
        }}
      >
        <Row justify="space-between" align="middle" gutter={[16, 16]}>
          <Col>
            <Space direction="vertical" size={2}>
              <Space>
                <Tag color="blue" style={{ borderRadius: 12 }}>
                  {selectedVersionText}
                </Tag>
                <Text type="secondary">
                  {uiPlan.date} 出发 · 共 {uiPlan.days} 天
                </Text>
              </Space>
              <Title level={2} style={{ margin: '8px 0' }}>
                {uiPlan.city} {uiPlan.days} 日游
              </Title>
              <Space size="large" style={{ marginTop: 8 }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Wallet size={16} color="#8c8c8c" /> 总预算 ¥{uiPlan.totalBudget}
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Activity size={16} color="#8c8c8c" /> {uiPlan.pace}
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <SunSnow size={16} color={riskColor(uiPlan.riskLevel)} /> 天气风险: {uiPlan.riskLevel}
                </span>
              </Space>
            </Space>
          </Col>
          <Col>
            <Space wrap>
              <Button icon={<FileText size={16} />}>导出 PDF</Button>
              <Button icon={<History size={16} />} onClick={() => navigate('/versions?planId=' + (planId ?? ''))}>
                版本历史
              </Button>
              <Select
                size="middle"
                style={{ minWidth: 140 }}
                value={selectedVersionId ?? undefined}
                placeholder="选择版本"
                onChange={(value) => setSelectedVersionId(value)}
                options={versions.map((item) => ({
                  value: item.id,
                  label: `v${item.version_no} · ${mapSourceType(item.source_type)}`,
                }))}
              />
              <Button
                icon={<RotateCcw size={16} />}
                loading={restoreMutation.isPending}
                disabled={!selectedVersion}
                onClick={() => {
                  if (!selectedVersion) return;
                  restoreMutation.mutate(selectedVersion.id);
                }}
              >
                恢复该版本
              </Button>
              <Button
                type="primary"
                icon={<Wand2 size={16} />}
                style={{ background: '#13c2c2', borderColor: '#13c2c2' }}
                onClick={() => setDrawerVisible(true)}
              >
                AI 优化
              </Button>
            </Space>
          </Col>
        </Row>
      </motion.div>

      {summaryQuery.isError || warningsQuery.isError || versionsQuery.isError ? (
        <Alert
          style={{ marginBottom: 16 }}
          type="warning"
          showIcon
          message="部分接口加载失败，已回退到可用数据"
          description={
            summaryQuery.error?.message ||
            warningsQuery.error?.message ||
            versionsQuery.error?.message ||
            '请稍后重试。'
          }
        />
      ) : null}

      <Row gutter={24}>
        <Col xs={24} lg={16}>
          <Card bordered={false} style={{ borderRadius: 16, marginBottom: 24 }} bodyStyle={{ padding: 0 }}>
            <Tabs
              activeKey={activeDay}
              onChange={setActiveDay}
              style={{ padding: '0 24px' }}
              items={uiPlan.itinerary.map((day) => ({
                label: `Day ${day.day}`,
                key: String(day.day),
              }))}
            />

            <div style={{ padding: 24 }}>
              {activeWeather?.suggestion ? (
                <div
                  style={{
                    marginBottom: 24,
                    padding: '12px 16px',
                    background: '#fffbe6',
                    border: '1px solid #ffe58f',
                    borderRadius: 8,
                    display: 'flex',
                    gap: 8,
                  }}
                >
                  <SunSnow size={20} color="#faad14" />
                  <Text style={{ color: '#d46b08' }}>
                    <strong>天气提示：</strong>
                    {activeWeather.suggestion}
                  </Text>
                </div>
              ) : null}

              {!activeItinerary ? (
                <Empty description="暂无行程数据" />
              ) : (
                <Timeline
                  items={activeItinerary.items.map((item) => ({
                    color: item.type === 'food' ? 'orange' : item.type === 'transport' ? 'green' : 'blue',
                    dot: (
                      <div
                        style={{
                          background: '#fff',
                          padding: 4,
                          borderRadius: '50%',
                          border: '2px solid #f0f0f0',
                        }}
                      >
                        {getIconForType(item.type)}
                      </div>
                    ),
                    children: (
                      <Card
                        hoverable
                        size="small"
                        style={{ marginBottom: 16, borderRadius: 12, border: '1px solid #f0f0f0' }}
                      >
                        <Row justify="space-between">
                          <Col>
                            <Space align="center">
                              <Text strong style={{ fontSize: 16 }}>
                                {item.time}
                              </Text>
                              <Divider type="vertical" />
                              <Title level={5} style={{ margin: 0 }}>
                                {item.title}
                              </Title>
                            </Space>
                            <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 8 }}>
                              {item.reason}
                            </Paragraph>
                            <Space wrap>
                              {item.tags.map((tag) => (
                                <Tag key={tag} bordered={false} style={{ background: '#f5f5f5' }}>
                                  {tag}
                                </Tag>
                              ))}
                            </Space>
                          </Col>
                          <Col style={{ textAlign: 'right' }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, color: '#8c8c8c' }}>
                              <span
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 4,
                                  justifyContent: 'flex-end',
                                }}
                              >
                                <Clock size={14} /> {item.duration}
                              </span>
                              {item.budget > 0 ? (
                                <span
                                  style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 4,
                                    justifyContent: 'flex-end',
                                    color: '#52c41a',
                                  }}
                                >
                                  <Wallet size={14} /> ¥{item.budget}
                                </span>
                              ) : null}
                            </div>
                          </Col>
                        </Row>
                      </Card>
                    ),
                  }))}
                />
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Card
              bordered={false}
              style={{ borderRadius: 16, overflow: 'hidden' }}
              bodyStyle={{ padding: 0 }}
            >
              <div
                style={{
                  height: 250,
                  background: '#e6f7ff',
                  position: 'relative',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  backgroundImage: 'radial-gradient(#91d5ff 1px, transparent 1px)',
                  backgroundSize: '20px 20px',
                }}
              >
                <MapIcon size={48} color="#1890ff" opacity={0.2} />
                <div
                  style={{
                    position: 'absolute',
                    top: '40%',
                    left: '30%',
                    width: 12,
                    height: 12,
                    background: '#1890ff',
                    borderRadius: '50%',
                    boxShadow: '0 0 0 4px rgba(24,144,255,0.2)',
                  }}
                />
                <div
                  style={{
                    position: 'absolute',
                    top: '60%',
                    left: '50%',
                    width: 12,
                    height: 12,
                    background: '#faad14',
                    borderRadius: '50%',
                    boxShadow: '0 0 0 4px rgba(250,173,20,0.2)',
                  }}
                />
                <div
                  style={{
                    position: 'absolute',
                    top: '30%',
                    left: '70%',
                    width: 12,
                    height: 12,
                    background: '#1890ff',
                    borderRadius: '50%',
                    boxShadow: '0 0 0 4px rgba(24,144,255,0.2)',
                  }}
                />
                <svg
                  style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
                >
                  <path
                    d="M 30% 40% L 50% 60% L 70% 30%"
                    stroke="#1890ff"
                    strokeWidth="2"
                    strokeDasharray="4 4"
                    fill="none"
                    opacity={0.5}
                  />
                </svg>

                <div style={{ position: 'absolute', bottom: 16, right: 16 }}>
                  <Button size="small" style={{ borderRadius: 12 }}>
                    查看大地图
                  </Button>
                </div>
              </div>
            </Card>

            <Card title="预算拆解" bordered={false} style={{ borderRadius: 16 }}>
              <div style={{ height: 200 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={uiPlan.budgetBreakdown} innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                      {uiPlan.budgetBreakdown.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value) => `¥${value}`} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <Row gutter={[16, 16]}>
                {uiPlan.budgetBreakdown.map((item, index) => (
                  <Col span={12} key={item.name}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: '50%',
                          background: COLORS[index % COLORS.length],
                        }}
                      />
                      <Text type="secondary">{item.name}</Text>
                      <Text strong>¥{item.value}</Text>
                    </div>
                  </Col>
                ))}
              </Row>
            </Card>

            <Card title="天气预报" bordered={false} style={{ borderRadius: 16 }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                {uiPlan.weather.map((w, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      padding: '8px 0',
                      borderBottom: idx !== uiPlan.weather.length - 1 ? '1px solid #f0f0f0' : 'none',
                    }}
                  >
                    <Text>{w.day}</Text>
                    <Text>{w.condition}</Text>
                    <Text strong>{w.temp}</Text>
                    <Tag color={riskTagColor(w.risk)} style={{ margin: 0 }}>
                      {w.risk}风险
                    </Tag>
                  </div>
                ))}
              </Space>
            </Card>
          </Space>
        </Col>
      </Row>

      <Drawer
        title="AI 行程优化"
        placement="right"
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
        width={430}
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Card size="small" title="降低预算" hoverable style={{ border: '1px solid #91d5ff' }}>
            <Text type="secondary">自动下调餐饮与住宿预算项，并补充预算优化建议，生成一个新编辑版本。</Text>
            <Input
              size="small"
              style={{ marginTop: 12 }}
              placeholder="变更摘要（例如：降低预算 15%）"
              value={editSummary}
              onChange={(e) => setEditSummary(e.target.value)}
            />
            <Button
              type="primary"
              size="small"
              style={{ marginTop: 12 }}
              loading={editMutation.isPending}
              onClick={onApplyLowerBudget}
            >
              应用
            </Button>
          </Card>

          <Card size="small" title="调整为长辈模式" hoverable>
            <Text type="secondary">减少每天活动密度，优先保留上午/下午核心活动并加入休息提示，生成新编辑版本。</Text>
            <Button
              type="default"
              size="small"
              style={{ marginTop: 12 }}
              loading={editMutation.isPending}
              onClick={onApplySeniorMode}
            >
              应用
            </Button>
          </Card>

          <Card size="small" title="规避降雨" hoverable>
            <Text type="secondary">基于当前方案参数触发再生成任务，并附加“增加室内活动”的说明。</Text>
            <Space direction="vertical" style={{ width: '100%', marginTop: 12 }} size={8}>
              <Select
                value={regenBudgetRange}
                onChange={setRegenBudgetRange}
                options={[
                  { label: '低预算', value: 'low' },
                  { label: '中预算', value: 'medium' },
                  { label: '高预算', value: 'high' },
                ]}
              />
              <Input.TextArea
                rows={3}
                placeholder="再生成备注（可选）"
                value={regenNotes}
                onChange={(e) => setRegenNotes(e.target.value)}
              />
            </Space>
            <Button
              type="default"
              size="small"
              style={{ marginTop: 12 }}
              loading={regenerateMutation.isPending}
              onClick={onApplyRainAvoid}
            >
              应用
            </Button>
          </Card>
        </Space>
      </Drawer>
    </div>
  );
}

function getIconForType(type: string) {
  switch (type) {
    case 'attraction':
      return <Camera size={16} color="#1890ff" />;
    case 'food':
      return <Coffee size={16} color="#faad14" />;
    case 'transport':
      return <Bus size={16} color="#52c41a" />;
    default:
      return <MapPin size={16} color="#13c2c2" />;
  }
}

function riskColor(risk: string): string {
  if (risk === '高') return '#f5222d';
  if (risk === '中') return '#faad14';
  return '#52c41a';
}

function riskTagColor(risk: string): string {
  if (risk === '高') return 'red';
  if (risk === '中') return 'orange';
  return 'green';
}

function mapRiskToChinese(value: unknown): string {
  const raw = String(value ?? '').trim().toLowerCase();
  if (!raw) return '低';
  if (raw === 'high' || raw.includes('高')) return '高';
  if (raw === 'medium' || raw.includes('中')) return '中';
  if (raw === 'low' || raw.includes('低')) return '低';
  return '低';
}

function mapPaceToChinese(value: unknown): string {
  const raw = String(value ?? '').trim().toLowerCase();
  if (!raw) return '轻松';
  if (raw === 'intensive' || raw.includes('紧凑')) return '紧凑';
  if (raw === 'balanced' || raw.includes('适中')) return '适中';
  if (raw === 'relaxed' || raw.includes('轻松')) return '轻松';
  return String(value);
}

function mapSourceType(value: string): string {
  if (value === 'created') return '初始生成';
  if (value === 'regenerated') return 'AI 再生成';
  if (value === 'edited') return '手动编辑';
  if (value === 'restored') return '版本恢复';
  return value || '未知来源';
}

function mapActivityType(type: unknown): 'attraction' | 'food' | 'transport' {
  const raw = String(type ?? '').toLowerCase();
  if (raw.includes('food') || raw.includes('meal') || raw.includes('lunch') || raw.includes('evening')) return 'food';
  if (raw.includes('transport') || raw.includes('transit') || raw.includes('drive') || raw.includes('walk')) return 'transport';
  return 'attraction';
}

function mapBudgetName(rawName: unknown, rawKey: unknown): string {
  const key = String(rawKey ?? '').toLowerCase();
  const name = String(rawName ?? '').trim();
  if (name) return name;
  if (key === 'lodging') return '住宿';
  if (key === 'meals') return '餐饮';
  if (key === 'transport') return '交通';
  if (key === 'tickets') return '门票';
  if (key === 'buffer') return '预留';
  return '其他';
}

function mapWeatherCondition(value: unknown): string {
  const raw = String(value ?? '').toLowerCase();
  if (!raw) return '未知';
  if (raw.includes('sunny') || raw.includes('晴')) return '晴';
  if (raw.includes('cloudy') || raw.includes('多云')) return '多云';
  if (raw.includes('light_rain') || raw.includes('小雨')) return '小雨';
  if (raw.includes('moderate_rain') || raw.includes('中雨') || raw.includes('阵雨')) return '阵雨';
  if (raw.includes('heavy_rain') || raw.includes('大雨') || raw.includes('暴雨')) return '大雨';
  return String(value);
}

function buildUiPlan(params: {
  fallback: typeof mockPlanDetail;
  plan?: TripPlanResponse;
  summaryRiskLevel?: string;
  summaryPace?: string;
  summaryBudget?: number | null;
  warnings?: Array<{ date: string; level: string; suggestion: string }>;
  selectedVersion?: TripPlanVersionResponse | null;
}): UiPlanDetail {
  const { fallback, plan, summaryRiskLevel, summaryPace, summaryBudget, warnings = [], selectedVersion } = params;
  const content = getVersionContent(selectedVersion);

  const city = plan?.city || readString(content, 'city') || fallback.city;

  const startDate = plan?.start_date || readString(content, 'start_date');
  const endDate = plan?.end_date || readString(content, 'end_date');
  const daysFromDate = startDate && endDate ? Math.max(dayjs(endDate).diff(dayjs(startDate), 'day') + 1, 1) : null;
  const itinerary = extractItinerary(content, fallback.itinerary);
  const days = daysFromDate ?? itinerary.length ?? fallback.days;

  const version = selectedVersion ? `v${selectedVersion.version_no}` : fallback.version;

  const riskLevel = mapRiskToChinese(summaryRiskLevel);
  const pace = mapPaceToChinese(summaryPace || readString(content, 'pace') || fallback.pace);

  const budget = extractBudget(content, fallback.budgetBreakdown, summaryBudget ?? undefined);
  const weather = extractWeather(content, warnings, fallback.weather);

  return {
    city,
    days,
    date: startDate ? dayjs(startDate).format('YYYY-MM-DD') : fallback.date,
    version,
    totalBudget: budget.total,
    riskLevel,
    pace,
    budgetBreakdown: budget.breakdown,
    weather,
    itinerary,
  };
}

function extractItinerary(content: Record<string, unknown>, fallback: typeof mockPlanDetail.itinerary): UiDay[] {
  const fallbackMapped: UiDay[] = fallback.map((day) => ({
    day: day.day,
    items: day.items.map((item) => ({
      ...item,
      type: mapActivityType(item.type),
    })),
  }));

  const rawDays = readArray(content, 'days');
  if (!rawDays.length) {
    return fallbackMapped;
  }

  const result: UiDay[] = rawDays
    .map((day, index) => {
      const dayObj = asRecord(day);
      const activities = readArray(dayObj, 'activities');
      const items: UiItineraryItem[] = activities
        .map((activity) => {
          const act = asRecord(activity);
          const title = readString(act, 'title') || '未命名活动';
          const tagsRaw = readArray(act, 'tags')
            .map((tag) => String(tag))
            .filter(Boolean);
          return {
            time: readString(act, 'time') || '--:--',
            type: mapActivityType(act.type),
            title,
            reason: readString(act, 'reason') || '结合天气、预算和动线安排',
            duration: readString(act, 'duration') || '1小时',
            budget: toNumber(act.budget),
            tags: tagsRaw.length ? tagsRaw : ['行程活动'],
          };
        })
        .sort((a, b) => a.time.localeCompare(b.time));

      return {
        day: toNumber(dayObj.day_number) || index + 1,
        items,
      };
    })
    .filter((day) => day.items.length > 0);

  return result.length ? result : fallbackMapped;
}

function extractBudget(
  content: Record<string, unknown>,
  fallback: UiBudgetItem[],
  summaryBudget?: number,
): { total: number; breakdown: UiBudgetItem[] } {
  const budget = asRecord(content.budget);
  const breakdownRaw = readArray(budget, 'breakdown');

  const breakdown = breakdownRaw
    .map((item) => {
      const row = asRecord(item);
      const value = toNumber(row.value);
      if (value <= 0) return null;
      return {
        name: mapBudgetName(row.name, row.key),
        value,
      } as UiBudgetItem;
    })
    .filter((item): item is UiBudgetItem => item != null);

  const finalBreakdown = breakdown.length ? breakdown : fallback;
  const computedTotal = finalBreakdown.reduce((sum, item) => sum + item.value, 0);
  const total =
    typeof summaryBudget === 'number'
      ? summaryBudget
      : toNumber(budget.estimated_total) || computedTotal || fallback.reduce((s, i) => s + i.value, 0);

  return { total, breakdown: finalBreakdown };
}

function extractWeather(
  content: Record<string, unknown>,
  warnings: Array<{ date: string; level: string; suggestion: string }>,
  fallback: typeof mockPlanDetail.weather,
): UiWeather[] {
  const warningMap = new globalThis.Map(warnings.map((item) => [item.date, item]));

  const days = readArray(content, 'days');
  if (days.length) {
    const ui = days.map((item, index) => {
      const day = asRecord(item);
      const date = readString(day, 'date');
      const weather = asRecord(day.weather);
      const high = toNumber(weather.high);
      const low = toNumber(weather.low);
      const warning = date ? warningMap.get(date) : undefined;
      const risk = warning ? mapRiskToChinese(warning.level) : inferRiskFromWeather(weather);
      const suggestion = readString(day, 'weather_suggestion') || warning?.suggestion;

      return {
        day: `Day ${index + 1}`,
        temp: formatTemp(low, high),
        condition: mapWeatherCondition(weather.condition),
        risk,
        suggestion,
      };
    });

    if (ui.length) {
      return ui;
    }
  }

  const weatherInfo = readArray(content, 'weather_info');
  if (weatherInfo.length) {
    const ui = weatherInfo.map((item, index) => {
      const row = asRecord(item);
      const date = readString(row, 'date');
      const warning = date ? warningMap.get(date) : undefined;
      const risk = warning ? mapRiskToChinese(warning.level) : inferRiskFromWeather(row);
      return {
        day: `Day ${index + 1}`,
        temp: formatTemp(toNumber(row.low), toNumber(row.high)),
        condition: mapWeatherCondition(row.condition),
        risk,
        suggestion: warning?.suggestion,
      };
    });

    if (ui.length) {
      return ui;
    }
  }

  return fallback;
}

function formatTemp(low: number, high: number): string {
  if (low > 0 && high > 0) return `${low}-${high}°C`;
  return '--';
}

function inferRiskFromWeather(weather: Record<string, unknown>): string {
  const riskScore = toNumber(weather.risk_score);
  if (riskScore <= -3) return '高';
  if (riskScore < 0) return '中';
  return '低';
}

function getVersionContent(version: TripPlanVersionResponse | null | undefined): Record<string, unknown> {
  if (!version || !version.content_json || typeof version.content_json !== 'object') {
    return {};
  }
  return deepClone(asRecord(version.content_json));
}

function buildRegeneratePayload(
  plan: TripPlanResponse | undefined,
  budgetRange: string,
  notes: string,
): TripPlanCreateRequest {
  const today = dayjs().format('YYYY-MM-DD');
  return {
    title: plan?.title || '行程再生成',
    city: plan?.city || '目的地',
    start_date: plan?.start_date || today,
    end_date: plan?.end_date || today,
    budget_range: budgetRange || plan?.budget_range || 'medium',
    transport_preference: 'public_transit',
    accommodation_preference: 'comfort',
    notes: notes || '基于当前版本进行再生成',
  };
}

function applyLowerBudget(content: Record<string, unknown>): Record<string, unknown> {
  const next = deepClone(content);
  const budget = asRecord(next.budget);
  const breakdown = readArray(budget, 'breakdown').map((item) => {
    const row = asRecord(item);
    const key = String(row.key ?? '').toLowerCase();
    const value = toNumber(row.value);
    if (value <= 0) return row;

    if (key === 'lodging' || key === 'meals' || key.includes('住宿') || key.includes('餐饮')) {
      row.value = Math.max(Math.round(value * 0.85), 0);
    }
    return row;
  });

  if (breakdown.length) {
    budget.breakdown = breakdown;
    const total = breakdown.reduce((sum, item) => sum + toNumber(asRecord(item).value), 0);
    budget.estimated_total = total;
  }

  const suggestions = readArray(next, 'overall_suggestions').map((item) => String(item));
  suggestions.unshift('已自动降低住宿和餐饮预算，建议优先选择交通便利区域与本地餐馆。');
  next.overall_suggestions = Array.from(new Set(suggestions)).slice(0, 6);
  next.budget = budget;
  return next;
}

function applySeniorMode(content: Record<string, unknown>): Record<string, unknown> {
  const next = deepClone(content);
  const days = readArray(next, 'days').map((item) => {
    const day = asRecord(item);
    const activities = readArray(day, 'activities').map((activity) => asRecord(activity));
    if (activities.length > 3) {
      const core = [activities[0], activities[2], activities[activities.length - 1]].filter(Boolean);
      day.activities = core.map((act) => ({
        ...act,
        reason: `${readString(act, 'reason') || '行程安排'}；已降低行走强度并增加休息余量`,
      }));
    }
    day.weather_suggestion = `${readString(day, 'weather_suggestion') || '建议按时休息'}；可根据体力在午后增加休息点`;
    return day;
  });

  next.days = days;
  const suggestions = readArray(next, 'overall_suggestions').map((item) => String(item));
  suggestions.unshift('已切换为长辈模式：减少单日活动密度，优先平缓动线。');
  next.overall_suggestions = Array.from(new Set(suggestions)).slice(0, 6);
  return next;
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function readString(obj: Record<string, unknown>, key: string): string {
  const value = obj[key];
  return typeof value === 'string' ? value : '';
}

function readArray(obj: Record<string, unknown>, key: string): unknown[] {
  const value = obj[key];
  return Array.isArray(value) ? value : [];
}

function toNumber(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
