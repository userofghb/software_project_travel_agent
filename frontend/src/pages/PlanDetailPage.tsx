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
  InputNumber,
  Popconfirm,
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
  deletePlan,
  getPlan,
  getPlanSummary,
  listPlanVersions,
  regeneratePlan,
  restorePlanVersion,
  downloadPlanVersionPdf,
} from '../api/plans';
import { getPlanWarnings } from '../api/warnings';
import type { TripPlanCreateRequest, TripPlanResponse, TripPlanVersionResponse } from '../api/types';
import { PlanMap, type MapPoint } from '../components/PlanMap';
import {
  SunSnow,
  Wallet,
  Activity,
  Clock,
  MapPin,
  Coffee,
  Camera,
  Bus,
  Hotel,
  Plane,
  FileText,
  Wand2,
  History,
  RotateCcw,
  Edit3,
  Plus,
  Save,
  Trash2,
} from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

const { Title, Text, Paragraph } = Typography;

const COLORS = ['#13c2c2', '#1890ff', '#faad14', '#eb2f96'];
const EMPTY_PLAN_DETAIL = {
  city: '',
  days: 0,
  date: '',
  version: '-',
  totalBudget: 0,
  riskLevel: 'low',
  pace: 'relaxed',
  budgetBreakdown: [] as UiBudgetItem[],
  weather: [] as UiWeather[],
  itinerary: [] as UiDay[],
  map: {
    points: [] as MapPoint[],
  },
};

type UiItineraryItem = {
  id: string;
  time: string;
  type: 'attraction' | 'food' | 'transport' | 'hotel' | 'intercity' | 'rest';
  title: string;
  reason: string;
  duration: string;
  budget: number;
  tags: string[];
};

type UiDay = {
  day: number;
  date?: string;
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
  origin: string;
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
  map: {
    points: MapPoint[];
  };
};

export function PlanDetailPage() {
  const { planId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const planIdNumber = Number(planId);
  const validPlanId = Number.isFinite(planIdNumber) && planIdNumber > 0;

  const [activeDay, setActiveDay] = useState('1');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [manualDrawerVisible, setManualDrawerVisible] = useState(false);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [editSummary, setEditSummary] = useState('详情页微调');
  const [regenBudgetRange, setRegenBudgetRange] = useState<string>('medium');
  const [regenNotes, setRegenNotes] = useState('');
  const [aiGoal, setAiGoal] = useState('根据当前用户画像优化行程节奏，保留三餐和住宿安排');
  const [manualTitle, setManualTitle] = useState('');
  const [manualSummary, setManualSummary] = useState('用户手动修改计划');
  const [manualSuggestions, setManualSuggestions] = useState('');
  const [manualDays, setManualDays] = useState<UiDay[]>([]);
  const [exportingPdf, setExportingPdf] = useState(false);
  const itemRefs = React.useRef<Record<string, HTMLDivElement | null>>({});

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
        fallback: EMPTY_PLAN_DETAIL,
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

  const handlePointSelect = (nodeId: string) => {
    setSelectedNodeId(nodeId);
    window.setTimeout(() => {
      itemRefs.current[nodeId]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 0);
  };

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

  const deleteMutation = useMutation({
    mutationFn: () => deletePlan(planIdNumber),
    onSuccess: async () => {
      message.success('方案已删除');
      await queryClient.invalidateQueries({ queryKey: ['plans'] });
      navigate('/history');
    },
    onError: (err: Error) => {
      message.error(err.message || '删除失败');
    },
  });

  const exportPdf = async () => {
    if (!selectedVersion) {
      message.warning('请选择要导出的版本');
      return;
    }
    setExportingPdf(true);
    try {
      const blob = await downloadPlanVersionPdf(planIdNumber, selectedVersion.id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${plan?.title || 'travel-plan'}-v${selectedVersion.version_no}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      message.success('PDF 导出已开始');
    } catch (err) {
      message.error((err as Error).message || 'PDF 导出失败');
    } finally {
      setExportingPdf(false);
    }
  };

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

  const openManualEditor = () => {
    const content = getVersionContent(selectedVersion);
    setManualTitle(readString(content, 'title') || plan?.title || '');
    setManualSummary('用户手动修改计划');
    setManualSuggestions(readArray(content, 'overall_suggestions').map((item) => String(item)).join('\n'));
    setManualDays(deepClone(uiPlan.itinerary));
    setManualDrawerVisible(true);
  };

  const saveManualEdit = () => {
    if (!selectedVersion) {
      message.warning('当前没有可编辑版本');
      return;
    }
    const content = getVersionContent(selectedVersion);
    const next = applyManualPlanEdit(content, manualTitle, manualDays, manualSuggestions);
    editMutation.mutate(
      {
        summary: manualSummary || '用户手动修改计划',
        content: next,
      },
      {
        onSuccess: () => setManualDrawerVisible(false),
      },
    );
  };

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
    const payload = buildRegeneratePayload(
      plan,
      regenBudgetRange,
      [aiGoal, regenNotes].filter(Boolean).join('\n'),
      getVersionContent(selectedVersion),
    );
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
                {uiPlan.origin ? `${uiPlan.origin} → ` : ''}{uiPlan.city} {uiPlan.days} 日游
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
              <Button icon={<FileText size={16} />} loading={exportingPdf} onClick={exportPdf}>
                导出 PDF
              </Button>
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
                icon={<Edit3 size={16} />}
                disabled={!selectedVersion}
                onClick={openManualEditor}
              >
                手动修改
              </Button>
              <Button
                type="primary"
                icon={<Wand2 size={16} />}
                style={{ background: '#13c2c2', borderColor: '#13c2c2' }}
                onClick={() => setDrawerVisible(true)}
              >
                AI 优化
              </Button>
              <Popconfirm
                title="删除方案"
                description="删除后将移除该方案及其版本记录，无法恢复。"
                okText="删除"
                cancelText="取消"
                okButtonProps={{ danger: true, loading: deleteMutation.isPending }}
                onConfirm={() => deleteMutation.mutate()}
              >
                <Button danger icon={<Trash2 size={16} />} loading={deleteMutation.isPending}>
                  删除
                </Button>
              </Popconfirm>
            </Space>
          </Col>
        </Row>
      </motion.div>

      {summaryQuery.isError || warningsQuery.isError || versionsQuery.isError ? (
        <Alert
          style={{ marginBottom: 16 }}
          type="warning"
          showIcon
          message="部分信息暂时加载失败，已显示当前可用内容"
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
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  <Timeline
                    items={activeItinerary.items.map((item) => ({
                      color: timelineColor(item.type),
                      dot: (
                        <div
                          style={{
                            background: '#fff',
                            padding: 4,
                            borderRadius: '50%',
                            border: selectedNodeId === item.id ? '2px solid #faad14' : '2px solid #f0f0f0',
                          }}
                        >
                          {getIconForType(item.type)}
                        </div>
                      ),
                      children: renderItineraryCard(item, itemRefs, selectedNodeId, setSelectedNodeId),
                    }))}
                  />
                </Space>
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
              <PlanMap
                points={uiPlan.map.points}
                activeDate={activeItinerary?.date ?? String(activeItinerary?.day ?? '')}
                selectedNodeId={selectedNodeId}
                onPointSelect={handlePointSelect}
                height={300}
              />
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
        title="手动修改计划"
        placement="right"
        onClose={() => setManualDrawerVisible(false)}
        open={manualDrawerVisible}
        width={620}
        extra={
          <Button type="primary" icon={<Save size={16} />} loading={editMutation.isPending} onClick={saveManualEdit}>
            保存为新版本
          </Button>
        }
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Card size="small" title="方案信息">
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <Input value={manualTitle} onChange={(event) => setManualTitle(event.target.value)} placeholder="方案标题" />
              <Input value={manualSummary} onChange={(event) => setManualSummary(event.target.value)} placeholder="修改摘要" />
              <Input.TextArea
                rows={4}
                value={manualSuggestions}
                onChange={(event) => setManualSuggestions(event.target.value)}
                placeholder="整体建议，每行一条"
              />
            </Space>
          </Card>

          {manualDays.map((day, dayIndex) => (
            <Card
              key={`${day.day}-${day.date ?? dayIndex}`}
              size="small"
              title={`Day ${day.day}${day.date ? ` · ${day.date}` : ''}`}
              extra={
                <Button
                  size="small"
                  icon={<Plus size={14} />}
                  onClick={() => setManualDays(addManualActivity(manualDays, dayIndex))}
                >
                  添加活动
                </Button>
              }
            >
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                {day.items.map((item, itemIndex) => (
                  <Card key={item.id} size="small" style={{ borderRadius: 8 }}>
                    <Space direction="vertical" size={8} style={{ width: '100%' }}>
                      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                        <Text strong>{item.time || '未设置时间'}</Text>
                        <Button
                          danger
                          size="small"
                          icon={<Trash2 size={14} />}
                          onClick={() => setManualDays(removeManualActivity(manualDays, dayIndex, itemIndex))}
                        >
                          删除
                        </Button>
                      </Space>
                      <Row gutter={[8, 8]}>
                        <Col span={8}>
                          <Input
                            value={item.time}
                            placeholder="时间"
                            onChange={(event) => setManualDays(updateManualActivity(manualDays, dayIndex, itemIndex, { time: event.target.value }))}
                          />
                        </Col>
                        <Col span={8}>
                          <Select
                            value={item.type}
                            style={{ width: '100%' }}
                            onChange={(value) => setManualDays(updateManualActivity(manualDays, dayIndex, itemIndex, { type: value }))}
                            options={[
                              { label: '景点', value: 'attraction' },
                              { label: '餐饮', value: 'food' },
                              { label: '交通', value: 'transport' },
                              { label: '住宿', value: 'hotel' },
                              { label: '往返交通', value: 'intercity' },
                              { label: '休息', value: 'rest' },
                            ]}
                          />
                        </Col>
                        <Col span={8}>
                          <InputNumber
                            min={0}
                            value={item.budget}
                            style={{ width: '100%' }}
                            prefix="¥"
                            onChange={(value) => setManualDays(updateManualActivity(manualDays, dayIndex, itemIndex, { budget: Number(value ?? 0) }))}
                          />
                        </Col>
                        <Col span={24}>
                          <Input
                            value={item.title}
                            placeholder="活动标题"
                            onChange={(event) => setManualDays(updateManualActivity(manualDays, dayIndex, itemIndex, { title: event.target.value }))}
                          />
                        </Col>
                        <Col span={12}>
                          <Input
                            value={item.duration}
                            placeholder="时长"
                            onChange={(event) => setManualDays(updateManualActivity(manualDays, dayIndex, itemIndex, { duration: event.target.value }))}
                          />
                        </Col>
                        <Col span={12}>
                          <Input
                            value={item.tags.join('、')}
                            placeholder="标签，用顿号分隔"
                            onChange={(event) =>
                              setManualDays(updateManualActivity(manualDays, dayIndex, itemIndex, { tags: splitTags(event.target.value) }))
                            }
                          />
                        </Col>
                        <Col span={24}>
                          <Input.TextArea
                            rows={2}
                            value={item.reason}
                            placeholder="安排理由"
                            onChange={(event) => setManualDays(updateManualActivity(manualDays, dayIndex, itemIndex, { reason: event.target.value }))}
                          />
                        </Col>
                      </Row>
                    </Space>
                  </Card>
                ))}
              </Space>
            </Card>
          ))}
        </Space>
      </Drawer>

      <Drawer
        title="AI 优化计划"
        placement="right"
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
        width={430}
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Card size="small" title="优化目标">
            <Space direction="vertical" style={{ width: '100%' }} size={8}>
              <Input.TextArea
                rows={5}
                value={aiGoal}
                onChange={(event) => setAiGoal(event.target.value)}
                placeholder="例如：减少转场、增加亲子友好、保留三餐、雨天优先室内..."
              />
              <Text type="secondary">AI 会基于当前方案重新生成一个版本，并尽量保留已有行程结构。</Text>
            </Space>
          </Card>

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
            <Text type="secondary">基于当前方案参数触发再生成任务，并附加你的优化目标。</Text>
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
                placeholder="补充备注（可选）"
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
              提交 AI 优化
            </Button>
          </Card>
        </Space>
      </Drawer>
    </div>
  );
}

function renderItineraryCard(
  item: UiItineraryItem,
  itemRefs: React.MutableRefObject<Record<string, HTMLDivElement | null>>,
  selectedNodeId: string | null,
  setSelectedNodeId: (id: string | null) => void,
) {
  const isTransport = item.type === 'transport';
  const selected = selectedNodeId === item.id;
  return (
    <div
      key={item.id}
      ref={(node) => {
        itemRefs.current[item.id] = node;
      }}
      onClick={() => setSelectedNodeId(item.id)}
    >
      <Card
        hoverable
        size="small"
        style={{
          marginBottom: 16,
          borderRadius: 8,
          border: selected ? '1px solid #faad14' : '1px solid #f0f0f0',
          background: isTransport ? '#fbfffb' : '#fff',
        }}
        bodyStyle={{ padding: isTransport ? 12 : 16 }}
      >
        <Row justify="space-between" gutter={12}>
          <Col flex="auto">
            <Space align="center" wrap>
              <Text strong style={{ fontSize: isTransport ? 14 : 16 }}>
                {item.time}
              </Text>
              <Tag color={activityTagColor(item.type)} bordered={false} style={{ marginInlineEnd: 0 }}>
                {activityTypeLabel(item.type)}
              </Tag>
              <Title level={isTransport ? 5 : 4} style={{ margin: 0, fontSize: isTransport ? 14 : 16 }}>
                {item.title}
              </Title>
            </Space>
            {!isTransport ? (
              <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 8 }}>
                {item.reason}
              </Paragraph>
            ) : null}
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
              <span style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'flex-end' }}>
                <Clock size={14} /> {item.duration}
              </span>
              {item.budget > 0 || item.type === 'transport' ? (
                <span style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'flex-end', color: '#52c41a' }}>
                  <Wallet size={14} /> ¥{item.budget}
                </span>
              ) : null}
            </div>
          </Col>
        </Row>
      </Card>
    </div>
  );
}

function timelineColor(type: string): string {
  if (type === 'food') return 'orange';
  if (type === 'transport') return 'green';
  if (type === 'hotel') return 'purple';
  if (type === 'intercity') return 'cyan';
  if (type === 'rest') return 'gray';
  return 'blue';
}

function getIconForType(type: string) {
  switch (type) {
    case 'attraction':
      return <Camera size={16} color="#1890ff" />;
    case 'food':
      return <Coffee size={16} color="#faad14" />;
    case 'transport':
      return <Bus size={16} color="#52c41a" />;
    case 'hotel':
      return <Hotel size={16} color="#722ed1" />;
    case 'intercity':
      return <Plane size={16} color="#13c2c2" />;
    default:
      return <MapPin size={16} color="#13c2c2" />;
  }
}

function activityTypeLabel(type: string): string {
  if (type === 'attraction') return '景点';
  if (type === 'food') return '餐饮';
  if (type === 'transport') return '交通';
  if (type === 'hotel') return '住宿';
  if (type === 'intercity') return '往返交通';
  return '活动';
}

function activityTagColor(type: string): string {
  if (type === 'attraction') return 'blue';
  if (type === 'food') return 'orange';
  if (type === 'transport') return 'green';
  if (type === 'hotel') return 'purple';
  if (type === 'intercity') return 'cyan';
  return 'cyan';
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

function mapActivityType(type: unknown): 'attraction' | 'food' | 'transport' | 'hotel' | 'intercity' | 'rest' {
  const raw = String(type ?? '').toLowerCase();
  if (raw.includes('intercity') || raw.includes('flight') || raw.includes('rail') || raw.includes('train') || raw.includes('高铁') || raw.includes('飞机') || raw.includes('往返')) return 'intercity';
  if (raw.includes('food') || raw.includes('meal') || raw.includes('lunch')) return 'food';
  if (raw.includes('transport') || raw.includes('transit') || raw.includes('drive') || raw.includes('walk')) return 'transport';
  if (raw.includes('hotel') || raw.includes('lodging') || raw.includes('stay') || raw.includes('住宿') || raw.includes('酒店')) return 'hotel';
  if (raw.includes('rest') || raw.includes('free_time') || raw.includes('休息')) return 'rest';
  return 'attraction';
}

function mapBudgetName(rawName: unknown, rawKey: unknown): string {
  const key = String(rawKey ?? '').toLowerCase();
  const name = String(rawName ?? '').trim();
  if (name) return name;
  if (key === 'lodging') return '住宿';
  if (key === 'meals') return '餐饮';
  if (key === 'transport') return '交通';
  if (key === 'intercity') return '往返大交通';
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
  fallback: typeof EMPTY_PLAN_DETAIL;
  plan?: TripPlanResponse;
  summaryRiskLevel?: string;
  summaryPace?: string;
  summaryBudget?: number | null;
  warnings?: Array<{ date: string; level: string; suggestion: string }>;
  selectedVersion?: TripPlanVersionResponse | null;
}): UiPlanDetail {
  const { fallback, plan, summaryRiskLevel, summaryPace, summaryBudget, warnings = [], selectedVersion } = params;
  const content = getVersionContent(selectedVersion);

  const origin = plan?.origin || readString(content, 'origin') || '';
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
  const map = extractMap(content, fallback.map);

  return {
    origin,
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
    map,
  };
}

function extractItinerary(content: Record<string, unknown>, fallback: typeof EMPTY_PLAN_DETAIL.itinerary): UiDay[] {
  const fallbackMapped: UiDay[] = fallback.map((day) => ({
    day: day.day,
    items: day.items.map((item) => ({
      ...item,
      id: item.id || `${day.day}-${item.time}-${item.title}`,
      type: mapActivityType(item.type),
    })),
  }));

  const rawDays = readArray(content, 'days');
  if (!rawDays.length) {
    return fallbackMapped;
  }
  const city = readString(content, 'city');

  const result: UiDay[] = rawDays
    .map((day, index) => {
      const dayObj = asRecord(day);
      const nodeRows = readArray(dayObj, 'nodes');
      const activities = nodeRows.length ? nodeRows : readArray(dayObj, 'activities');
      const items: UiItineraryItem[] = activities
        .map((activity) => {
          const act = asRecord(activity);
          const type = mapActivityType(act.type);
          const title = cleanUiActivityTitle(readString(act, 'title') || '未命名活动', type, city);
          const tagsRaw = readArray(act, 'tags')
            .map((tag) => String(tag))
            .filter((tag) => !(type === 'food' && (tag === '本地特色' || tag === '当地特色')))
            .filter(Boolean);
          const startTime = readString(act, 'start_time');
          const endTime = readString(act, 'end_time');
          const fallbackTime = readString(act, 'time') || '--:--';
          return {
            id: readString(act, 'id') || readString(act, 'source_id') || `${index}-${fallbackTime}-${title}`,
            time: startTime && endTime ? `${startTime}-${endTime}` : fallbackTime,
            type,
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
        date: readString(dayObj, 'date') || undefined,
        items,
      };
    })
    .filter((day) => day.items.length > 0);

  return result.length ? result : fallbackMapped;
}

function cleanUiActivityTitle(title: string, type: UiItineraryItem['type'], city: string): string {
  if (type !== 'food') return title;
  let next = title.trim();
  if (city) {
    next = next.replace(city, '').trim();
  }
  if (['本地午餐', '当地午餐', '特色午餐', '午餐'].includes(next)) return '午餐与休息';
  if (['本地晚餐', '当地晚餐', '特色晚餐', '晚餐'].includes(next)) return '晚餐与自由活动';
  return next || title;
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
  fallback: typeof EMPTY_PLAN_DETAIL.weather,
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

function extractMap(
  content: Record<string, unknown>,
  fallback: typeof EMPTY_PLAN_DETAIL.map,
): { points: MapPoint[] } {
  const map = asRecord(content.map);
  const points = readArray(map, 'points') as MapPoint[];

  return {
    points: points.length ? points : fallback.points,
  };
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
  content: Record<string, unknown> = {},
): TripPlanCreateRequest {
  const today = dayjs().format('YYYY-MM-DD');
  const profile = asRecord(content.user_profile);
  return {
    title: plan?.title || '行程再生成',
    origin: plan?.origin || undefined,
    city: plan?.city || '目的地',
    start_date: plan?.start_date || today,
    end_date: plan?.end_date || today,
    budget_range: budgetRange || plan?.budget_range || 'medium',
    transport_preference: readString(profile, 'transport_preference') || 'public_transit',
    accommodation_preference: readString(profile, 'accommodation_preference') || 'comfort',
    notes: `基于当前版本进行 AI 优化。请尽量保留合理的住宿、三餐、重点景点和日期结构，只按下列目标调整。\n优化目标：${notes || '提升整体行程体验'}`,
  };
}

function applyManualPlanEdit(
  content: Record<string, unknown>,
  title: string,
  days: UiDay[],
  suggestionsText: string,
): Record<string, unknown> {
  const next = deepClone(content);
  if (title.trim()) {
    next.title = title.trim();
  }
  next.days = days.map((day) => ({
    date: day.date,
    day_number: day.day,
    activities: day.items.map((item, index) => ({
      id: item.id || `manual-${day.day}-${index + 1}`,
      time: item.time,
      period: periodFromTime(item.time),
      type: item.type === 'intercity' ? 'intercity_transport' : item.type,
      title: item.title,
      reason: item.reason,
      duration: item.duration,
      budget: item.budget,
      tags: item.tags,
    })),
  }));
  next.overall_suggestions = suggestionsText
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
  next.meals = days.flatMap((day) =>
    day.items
      .filter((item) => item.type === 'food')
      .map((item) => ({
        date: day.date,
        time: item.time,
        suggestion: item.title,
        budget: item.budget,
        tags: item.tags,
      })),
  );
  return next;
}

function periodFromTime(time: string): string {
  const match = time.match(/(\d{1,2}):(\d{2})/);
  if (!match) return 'morning';
  const hour = Number(match[1]);
  if (hour < 12) return 'morning';
  if (hour < 14) return 'lunch';
  if (hour < 18) return 'afternoon';
  return 'evening';
}

function updateManualActivity(days: UiDay[], dayIndex: number, itemIndex: number, patch: Partial<UiItineraryItem>): UiDay[] {
  return days.map((day, currentDayIndex) => {
    if (currentDayIndex !== dayIndex) return day;
    return {
      ...day,
      items: day.items.map((item, currentItemIndex) => (currentItemIndex === itemIndex ? { ...item, ...patch } : item)),
    };
  });
}

function addManualActivity(days: UiDay[], dayIndex: number): UiDay[] {
  return days.map((day, currentDayIndex) => {
    if (currentDayIndex !== dayIndex) return day;
    const nextIndex = day.items.length + 1;
    return {
      ...day,
      items: [
        ...day.items,
        {
          id: `manual-${day.day}-${Date.now()}-${nextIndex}`,
          time: '15:00-16:00',
          type: 'rest',
          title: '新增活动',
          reason: '用户手动添加',
          duration: '1小时',
          budget: 0,
          tags: ['手动添加'],
        },
      ],
    };
  });
}

function removeManualActivity(days: UiDay[], dayIndex: number, itemIndex: number): UiDay[] {
  return days.map((day, currentDayIndex) => {
    if (currentDayIndex !== dayIndex) return day;
    return {
      ...day,
      items: day.items.filter((_, currentItemIndex) => currentItemIndex !== itemIndex),
    };
  });
}

function splitTags(value: string): string[] {
  return value
    .split(/[、,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
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
