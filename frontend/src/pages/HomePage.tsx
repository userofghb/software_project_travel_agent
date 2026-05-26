import React, { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Typography, Row, Col, Card, Input, Button, Tag, Space, Divider, message, Badge, Alert, Empty, Spin } from 'antd';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Wand2,
  MapPin,
  Calendar,
  Users,
  Wallet,
  SunSnow,
  Activity,
  Coffee,
  Trees,
  Landmark,
  Compass,
  Zap,
  ShieldAlert,
  GitCommit,
  CheckCircle2,
  ArrowRight,
} from 'lucide-react';
import { createPlan, getPlanSummary, listPlans } from '../api/plans';
import type { TripPlanCreateRequest } from '../api/types';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

export function HomePage() {
  const navigate = useNavigate();
  const [demandText, setDemandText] = useState('');
  const [parsed, setParsed] = useState(false);
  const [isParsing, setIsParsing] = useState(false);

  const [parsedData, setParsedData] = useState({
    destination: '',
    duration: '',
    budget: '',
    style: '',
  });

  const plansQuery = useQuery({
    queryKey: ['plans', 'home'],
    queryFn: listPlans,
  });
  const createPlanMutation = useMutation({
    mutationFn: createPlan,
    onSuccess: (task) => {
      message.success('已创建真实生成任务');
      navigate(`/tasks/${task.task_id}`);
    },
    onError: (err: Error) => {
      message.error(err.message || '创建生成任务失败');
    },
  });
  const plans = useMemo(() => {
    const data = plansQuery.data as unknown;
    if (Array.isArray(data)) return data;
    if (data && typeof data === 'object') {
      const maybeData = (data as { data?: unknown }).data;
      if (Array.isArray(maybeData)) return maybeData;
      const maybeItems = (data as { items?: unknown }).items;
      if (Array.isArray(maybeItems)) return maybeItems;
    }
    return [];
  }, [plansQuery.data]);
  const recentPlans = useMemo(() => plans.slice(0, 3), [plans]);

  const handleParse = () => {
    if (!demandText.trim()) {
      message.warning('请输入您的旅行想法');
      return;
    }
    setIsParsing(true);
    setTimeout(() => {
      const payload = buildCreatePayload(demandText);
      setParsedData({
        destination: payload.city,
        duration: formatDuration(payload.start_date, payload.end_date),
        budget: mapBudgetLabel(payload.budget_range),
        style: payload.notes || '结合用户画像生成',
      });
      setParsed(true);
      setIsParsing(false);
      message.success('需求解析成功');
    }, 1000);
  };

  const handleGenerate = () => {
    if (!demandText.trim()) {
      message.warning('请输入您的旅行想法');
      return;
    }
    const payload = buildCreatePayload(demandText);
    setParsedData({
      destination: payload.city,
      duration: formatDuration(payload.start_date, payload.end_date),
      budget: mapBudgetLabel(payload.budget_range),
      style: payload.notes || '结合用户画像生成',
    });
    setParsed(true);
    createPlanMutation.mutate(payload);
  };

  const applyTemplate = (template: string) => {
    setDemandText(template);
    setParsed(false);
  };

  const templates = [
    { title: '周末轻旅行', desc: '周边城市 2 日游', icon: <Coffee size={20} color="#13c2c2" />, text: '周末两天，预算2000，想轻松一点。' },
    { title: '美食深度游', desc: '吃货专属路线', icon: <Activity size={20} color="#fa8c16" />, text: '去成都3天，预算3000，优先安排地道美食。' },
    { title: '亲子舒适游', desc: '适合带娃，节奏宽松', icon: <Users size={20} color="#eb2f96" />, text: '一家三口去三亚，行程不要太赶。' },
    { title: '高效打卡游', desc: '有限时间看更多', icon: <Zap size={20} color="#722ed1" />, text: '北京周末两日，想打卡核心景点。' },
    { title: '人文城市游', desc: '历史文化体验', icon: <Landmark size={20} color="#2f54eb" />, text: '西安4日，重点历史文化路线。' },
    { title: '自然放松游', desc: '山水疗愈', icon: <Trees size={20} color="#52c41a" />, text: '大理或桂林，亲近自然。' },
  ];

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', paddingBottom: 40 }}>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        style={{
          background: 'linear-gradient(135deg, #001529 0%, #003a4f 100%)',
          borderRadius: 24,
          padding: '48px 64px',
          color: '#fff',
          position: 'relative',
          overflow: 'hidden',
          marginBottom: 40,
          boxShadow: '0 20px 40px rgba(0,0,0,0.1)',
        }}
      >
        <div style={{ position: 'absolute', right: -50, top: -50, opacity: 0.1 }}>
          <Compass size={400} />
        </div>

        <Row align="middle" gutter={64}>
          <Col xs={24} md={14}>
            <Space direction="vertical" size="large">
              <Space>
                <Tag color="cyan" style={{ borderRadius: 12, padding: '4px 12px', border: 0 }}>v2.0 智能引擎</Tag>
                <Tag color="blue" style={{ borderRadius: 12, padding: '4px 12px', border: 0 }}>Agent 工作流</Tag>
              </Space>
              <Title level={1} style={{ color: '#fff', margin: 0, fontSize: 42 }}>
                让 AI 为你生成一份<br />
                <span style={{ color: '#13c2c2' }}>真正可执行</span>的旅行计划
              </Title>
              <Paragraph style={{ color: 'rgba(255,255,255,0.8)', fontSize: 18, maxWidth: 500, lineHeight: 1.6 }}>
                结合天气、预算、路线和偏好，生成可调整、可追踪的完整行程。
              </Paragraph>

              <Space size="middle" style={{ marginTop: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', color: 'rgba(255,255,255,0.9)' }}>
                  <ShieldAlert size={18} style={{ marginRight: 8, color: '#faad14' }} /> 天气风险约束
                </div>
                <div style={{ display: 'flex', alignItems: 'center', color: 'rgba(255,255,255,0.9)' }}>
                  <Wallet size={18} style={{ marginRight: 8, color: '#52c41a' }} /> 预算自动拆解
                </div>
                <div style={{ display: 'flex', alignItems: 'center', color: 'rgba(255,255,255,0.9)' }}>
                  <GitCommit size={18} style={{ marginRight: 8, color: '#1890ff' }} /> 多版本追踪
                </div>
              </Space>
            </Space>
          </Col>
          <Col xs={24} md={10}>
            <Card variant="borderless" style={{ background: 'rgba(255,255,255,0.1)', backdropFilter: 'blur(10px)', borderRadius: 20, color: '#fff' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
                <Text style={{ color: 'rgba(255,255,255,0.6)' }}>行程预览示例</Text>
                <Badge status="processing" text={<span style={{ color: '#fff' }}>Agent Ready</span>} />
              </div>
              <Title level={3} style={{ color: '#fff', marginTop: 0 }}>成都 3 日游</Title>
              <Space direction="vertical" style={{ width: '100%' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Text style={{ color: 'rgba(255,255,255,0.8)' }}>预算</Text>
                  <Text strong style={{ color: '#fff' }}>¥3,000</Text>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Text style={{ color: 'rgba(255,255,255,0.8)' }}>天气风险</Text>
                  <Text strong style={{ color: '#faad14' }}>中</Text>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Text style={{ color: 'rgba(255,255,255,0.8)' }}>行程节奏</Text>
                  <Text strong style={{ color: '#52c41a' }}>适中</Text>
                </div>
              </Space>
            </Card>
          </Col>
        </Row>
      </motion.div>

      <Row gutter={24} style={{ marginBottom: 40 }}>
        <Col xs={24} lg={14}>
          <Card title={<Space><Wand2 size={20} color="#1890ff" /><span>一句话生成你的专属行程</span></Space>} variant="borderless" style={{ borderRadius: 16, height: '100%', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}>
            <TextArea rows={5} placeholder="例如：去成都玩三天，预算3000，想吃火锅，行程不要太赶。" value={demandText} onChange={(e) => setDemandText(e.target.value)} style={{ borderRadius: 12, resize: 'none', marginBottom: 16, fontSize: 16, padding: 16 }} />
            <Row justify="space-between" align="middle">
              <Col>
                <Button type="default" icon={<Activity size={16} />} onClick={handleParse} loading={isParsing} style={{ borderRadius: 8 }}>
                  智能解析需求
                </Button>
              </Col>
              <Col>
                <Button type="primary" size="large" icon={<ArrowRight size={18} />} loading={createPlanMutation.isPending} onClick={handleGenerate} style={{ borderRadius: 8, background: '#13c2c2', borderColor: '#13c2c2' }}>
                  {parsed ? '开始生成完整方案' : '解析并生成方案'}
                </Button>
              </Col>
            </Row>

            <Divider dashed style={{ margin: '20px 0' }} />
            <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>推荐输入示例：</Text>
            <Row gutter={[12, 12]}>
              {templates.map((tpl, idx) => (
                <Col xs={12} sm={8} key={idx}>
                  <Card hoverable size="small" style={{ borderRadius: 12, background: '#fafafa', border: '1px solid #f0f0f0' }} onClick={() => applyTemplate(tpl.text)}>
                    <Space direction="vertical" size={2}>
                      <Space>{tpl.icon}<Text strong style={{ fontSize: 14 }}>{tpl.title}</Text></Space>
                      <Text type="secondary" style={{ fontSize: 12 }}>{tpl.desc}</Text>
                    </Space>
                  </Card>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>

        <Col xs={24} lg={10}>
          <Card title="AI 解析结果" variant="borderless" style={{ borderRadius: 16, height: '100%', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}>
            {parsed ? (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  <div style={{ display: 'flex', alignItems: 'center', background: '#f6ffed', padding: '12px 16px', borderRadius: 8 }}>
                    <CheckCircle2 size={20} color="#52c41a" style={{ marginRight: 12 }} />
                    <Text strong style={{ color: '#52c41a' }}>已成功提取关键信息</Text>
                  </div>

                  <Row gutter={[16, 16]}>
                    <Col span={12}><InfoItem icon={<MapPin size={14} />} label="目的地" value={parsedData.destination} /></Col>
                    <Col span={12}><InfoItem icon={<Calendar size={14} />} label="时长" value={parsedData.duration} /></Col>
                    <Col span={12}><InfoItem icon={<Wallet size={14} />} label="预算" value={parsedData.budget} /></Col>
                    <Col span={12}><InfoItem icon={<Compass size={14} />} label="风格" value={parsedData.style} /></Col>
                  </Row>
                </Space>
              </motion.div>
            ) : (
              <div style={{ height: 250, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#bfbfbf' }}>
                <Wand2 size={48} style={{ marginBottom: 16, opacity: 0.5 }} />
                <Text type="secondary">输入旅行想法，AI 将自动提取核心要素</Text>
              </div>
            )}
          </Card>
        </Col>
      </Row>

      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={4} style={{ margin: 0 }}>最近生成的方案</Title>
        <Button type="link" onClick={() => navigate('/history')}>查看全部</Button>
      </div>

      <Row gutter={24}>
        {plansQuery.isLoading && (
          <Col span={24}>
            <div style={{ padding: '24px 0', display: 'flex', justifyContent: 'center' }}>
              <Spin />
            </div>
          </Col>
        )}
        {plansQuery.isError && (
          <Col span={24}>
            <Alert
              type="error"
              showIcon
              message="最近方案加载失败"
              description={(plansQuery.error as Error)?.message ?? '未知错误'}
            />
          </Col>
        )}
        {!plansQuery.isLoading && !plansQuery.isError && recentPlans.length === 0 && (
          <Col span={24}>
            <Empty description="当前用户暂无可展示的方案" />
          </Col>
        )}
        {recentPlans.map((plan) => (
          <Col xs={24} md={8} key={plan.id}>
            <Card hoverable style={{ borderRadius: 16, overflow: 'hidden', border: '1px solid #f0f0f0' }} bodyStyle={{ padding: 0 }} onClick={() => navigate(`/plans/${plan.id}`)}>
              <div style={{ height: 100, background: 'linear-gradient(135deg, #e6f7ff 0%, #bae7ff 100%)', padding: 20, position: 'relative' }}>
                <Title level={4} style={{ margin: 0 }}>{plan.title}</Title>
                <Text type="secondary">{plan.start_date}</Text>
                <Tag color="blue" style={{ position: 'absolute', top: 20, right: 10, borderRadius: 10 }}>
                  {plan.current_version?.version_no ? `v${plan.current_version.version_no}` : '-'}
                </Tag>
              </div>
              <div style={{ padding: 20 }}>
                <PlanSummaryMetrics planId={plan.id} />
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}

function InfoItem({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div style={{ padding: '12px', background: '#fafafa', borderRadius: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4, color: '#8c8c8c', gap: 4 }}>
        {icon} {label}
      </div>
      <Text strong style={{ fontSize: 16 }}>{value}</Text>
    </div>
  );
}

function PlanSummaryMetrics({ planId }: { planId: number }) {
  const summaryQuery = useQuery({
    queryKey: ['plan-summary', planId],
    queryFn: () => getPlanSummary(planId),
  });

  const summary = summaryQuery.data;
  const riskLevelRaw = summary?.risk_level ?? '-';
  const riskLevel = mapRiskLevel(riskLevelRaw);
  const pace = mapPace(summary?.pace ?? '-');
  const budget = summary?.estimated_total;
  const riskColor = riskLevelRaw === 'high' ? '#f5222d' : riskLevelRaw === 'medium' ? '#faad14' : '#52c41a';

  return (
    <Row gutter={[0, 12]}>
      <Col span={12}>
        <Space size="small">
          <Wallet size={16} color="#8c8c8c" />
          <Text>{budget == null ? '-' : `¥${budget}`}</Text>
        </Space>
      </Col>
      <Col span={12}>
        <Space size="small">
          <Activity size={16} color="#8c8c8c" />
          <Text>{pace}</Text>
        </Space>
      </Col>
      <Col span={12}>
        <Space size="small">
          <SunSnow size={16} color={riskColor} />
          <Text>天气风险: {riskLevel}</Text>
        </Space>
      </Col>
    </Row>
  );
}

function mapRiskLevel(level: string): string {
  if (level === 'high') return '高';
  if (level === 'medium') return '中';
  if (level === 'low') return '低';
  return level;
}

function mapPace(pace: string): string {
  if (pace === 'intensive') return '紧凑';
  if (pace === 'balanced') return '适中';
  if (pace === 'relaxed') return '轻松';
  return pace;
}

function buildCreatePayload(text: string): TripPlanCreateRequest {
  const city = extractCity(text);
  const days = extractDays(text);
  const startDate = nextDate(7);
  const endDate = addDays(startDate, days - 1);
  const budgetRange = extractBudgetRange(text);

  return {
    title: `${city}${days}日旅行方案`,
    city,
    start_date: toDateString(startDate),
    end_date: toDateString(endDate),
    budget_range: budgetRange,
    transport_preference: text.includes('自驾') ? 'driving' : text.includes('打车') ? 'taxi' : 'public_transit',
    accommodation_preference: budgetRange === 'high' ? 'luxury' : budgetRange === 'low' ? 'budget' : 'comfort',
    notes: text.trim(),
  };
}

function extractCity(text: string): string {
  const knownCities = ['北京', '上海', '广州', '深圳', '成都', '重庆', '杭州', '南京', '苏州', '西安', '武汉', '长沙', '厦门', '青岛', '大理', '桂林', '三亚'];
  const matched = knownCities.find((city) => text.includes(city));
  if (matched) return matched;

  const match = text.match(/去([\u4e00-\u9fa5]{2,8})(?:玩|旅行|旅游|游|出差|，|,|\s|$)/);
  return match?.[1] ?? '成都';
}

function extractDays(text: string): number {
  const digitMatch = text.match(/(\d+)\s*[日天]/);
  if (digitMatch) return clampDays(Number(digitMatch[1]));

  const cnMap: Record<string, number> = { 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7 };
  const cnMatch = text.match(/([一二两三四五六七])\s*[日天]/);
  return clampDays(cnMatch ? cnMap[cnMatch[1]] : 3);
}

function extractBudgetRange(text: string): string {
  const match = text.match(/预算\s*(\d+)/);
  const amount = match ? Number(match[1]) : 0;
  if (amount > 0) {
    if (amount <= 2000) return 'low';
    if (amount >= 6000) return 'high';
    return 'medium';
  }
  if (text.includes('高端') || text.includes('品质')) return 'high';
  if (text.includes('省钱') || text.includes('经济')) return 'low';
  return 'medium';
}

function clampDays(days: number): number {
  if (!Number.isFinite(days)) return 3;
  return Math.min(Math.max(Math.round(days), 1), 10);
}

function nextDate(offsetDays: number): Date {
  return addDays(new Date(), offsetDays);
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function toDateString(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function formatDuration(startDate: string, endDate: string): string {
  const start = new Date(startDate);
  const end = new Date(endDate);
  const days = Math.round((end.getTime() - start.getTime()) / 86400000) + 1;
  return `${days}天`;
}

function mapBudgetLabel(range: string): string {
  if (range === 'low') return '低预算';
  if (range === 'high') return '高预算';
  return '中等预算';
}




