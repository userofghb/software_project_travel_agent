import React, { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Typography, Row, Col, Card, Input, Button, Tag, Space, Divider, message, Badge, Alert, Empty, Spin, DatePicker, Select } from 'antd';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import dayjs, { type Dayjs } from 'dayjs';
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
import { createPlan, getPlanSummary, listPlans, parsePlan } from '../api/plans';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { RangePicker } = DatePicker;
const DEFAULT_ORIGIN = '南京';

export function HomePage() {
  const navigate = useNavigate();
  const [demandText, setDemandText] = useState('');
  const [originInput, setOriginInput] = useState(DEFAULT_ORIGIN);
  const [destinationInput, setDestinationInput] = useState('');
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [budgetRange, setBudgetRange] = useState('medium');
  const [transportPreference, setTransportPreference] = useState('public_transit');
  const [originEdited, setOriginEdited] = useState(false);
  const [destinationEdited, setDestinationEdited] = useState(false);
  const [parsed, setParsed] = useState(false);
  const [isParsing, setIsParsing] = useState(false);

  const [parsedData, setParsedData] = useState({
    origin: DEFAULT_ORIGIN,
    destination: '',
    departureTime: '',
    duration: '',
    budget: '',
  });

  const plansQuery = useQuery({
    queryKey: ['plans', 'home'],
    queryFn: () => listPlans(),
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

  const handleParse = async () => {
    if (!demandText.trim()) {
      message.warning('请输入您的旅行想法');
      return;
    }
    setIsParsing(true);
    try {
      const payload = await parsePlan(demandText);
      const origin = resolveOrigin(payload.origin, originInput, originEdited);
      const destination = resolveDestination(payload.city, destinationInput, destinationEdited);
      setOriginInput(origin);
      setDestinationInput(destination);
      setOriginEdited(false);
      setDestinationEdited(false);
      setParsedData({
        origin,
        destination,
        departureTime: formatDepartureTime(payload.start_date),
        duration: payload.duration || formatDuration(payload.start_date, payload.end_date),
        budget: mapBudgetLabel(payload.budget_range),
      });
      setParsed(true);
      message.success('需求解析成功');
    } catch (err) {
      message.error('需求解析失败');
    } finally {
      setIsParsing(false);
    }
  };

  const handleGenerate = async () => {
    if (!demandText.trim() && !destinationInput.trim()) {
      message.warning('请至少填写目的地或补充描述');
      return;
    }
    try {
      const payload = demandText.trim() ? await parsePlan(demandText) : buildManualPayload(originInput, destinationInput, dateRange, budgetRange, transportPreference);
      const origin = resolveOrigin(payload.origin, originInput, originEdited);
      const destination = resolveDestination(payload.city, destinationInput, destinationEdited);
      const startDate = dateRange?.[0]?.format('YYYY-MM-DD') || payload.start_date;
      const endDate = dateRange?.[1]?.format('YYYY-MM-DD') || payload.end_date;
      const payloadWithRoute = {
        ...payload,
        origin,
        city: destination,
        start_date: startDate,
        end_date: endDate,
        budget_range: budgetRange || payload.budget_range,
        transport_preference: transportPreference || payload.transport_preference,
        title: replaceTitleCity(payload.title, payload.city, destination),
        notes: [payload.notes, demandText].filter(Boolean).join('\n'),
      };
      setOriginInput(origin);
      setDestinationInput(destination);
      setOriginEdited(false);
      setDestinationEdited(false);
      setParsedData({
        origin,
        destination,
        departureTime: formatDepartureTime(startDate),
        duration: formatDuration(startDate, endDate),
        budget: mapBudgetLabel(payloadWithRoute.budget_range),
      });
      setDateRange([dayjs(payload.start_date), dayjs(payload.end_date)]);
      setBudgetRange(payload.budget_range || 'medium');
      setTransportPreference(payload.transport_preference || 'public_transit');
      setParsed(true);
      createPlanMutation.mutate(payloadWithRoute);
    } catch (err) {
      message.error('解析失败，请检查输入');
    }
  };

  const applyTemplate = (template: string) => {
    setDemandText(template);
    setParsed(false);
    setDestinationInput('');
    setDestinationEdited(false);
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
          <Card title={<Space><Wand2 size={20} color="#1890ff" /><span>填写核心信息，生成专属行程</span></Space>} variant="borderless" style={{ borderRadius: 16, height: '100%', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}>
            <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
              <Col xs={24} sm={12}>
                <Input
                  value={originInput}
                  onChange={(e) => {
                    setOriginInput(e.target.value);
                    setOriginEdited(true);
                  }}
                  prefix={<MapPin size={16} color="#13c2c2" />}
                  addonBefore="出发地"
                  placeholder={DEFAULT_ORIGIN}
                />
              </Col>
              <Col xs={24} sm={12}>
                <Input
                  value={destinationInput}
                  onChange={(e) => {
                    setDestinationInput(e.target.value);
                    setDestinationEdited(true);
                  }}
                  prefix={<MapPin size={16} color="#1890ff" />}
                  addonBefore="目的地"
                  placeholder="例如：成都"
                />
              </Col>
              <Col xs={24} sm={12}>
                <RangePicker
                  value={dateRange}
                  onChange={(value) => setDateRange(value && value[0] && value[1] ? [value[0], value[1]] : null)}
                  style={{ width: '100%' }}
                  placeholder={['出发日期', '返程日期']}
                />
              </Col>
              <Col xs={12} sm={6}>
                <Select
                  value={budgetRange}
                  onChange={setBudgetRange}
                  style={{ width: '100%' }}
                  options={[
                    { label: '经济预算', value: 'low' },
                    { label: '中等预算', value: 'medium' },
                    { label: '品质预算', value: 'high' },
                  ]}
                />
              </Col>
              <Col xs={12} sm={6}>
                <Select
                  value={transportPreference}
                  onChange={setTransportPreference}
                  style={{ width: '100%' }}
                  options={[
                    { label: '公交地铁', value: 'public_transit' },
                    { label: '打车优先', value: 'private_transport' },
                    { label: '步行优先', value: 'walking' },
                  ]}
                />
              </Col>
            </Row>
            <TextArea rows={4} placeholder="补充描述：例如想吃火锅、行程不要太赶、希望多安排博物馆。" value={demandText} onChange={(e) => {
              setDemandText(e.target.value);
              setParsed(false);
            }} style={{ borderRadius: 12, resize: 'none', marginBottom: 16, fontSize: 16, padding: 16 }} />
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
                    <Col span={12}><InfoItem icon={<MapPin size={14} />} label="出发地" value={parsedData.origin || DEFAULT_ORIGIN} /></Col>
                    <Col span={12}><InfoItem icon={<MapPin size={14} />} label="目的地" value={parsedData.destination} /></Col>
                    <Col span={12}><InfoItem icon={<Calendar size={14} />} label="出发时间" value={parsedData.departureTime || '待确认'} /></Col>
                    <Col span={12}><InfoItem icon={<Calendar size={14} />} label="时长" value={parsedData.duration} /></Col>
                    <Col span={12}><InfoItem icon={<Wallet size={14} />} label="预算" value={parsedData.budget} /></Col>
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


function formatDuration(startDate: string, endDate: string): string {
  const start = new Date(startDate);
  const end = new Date(endDate);
  const days = Math.round((end.getTime() - start.getTime()) / 86400000) + 1;
  return `${days}天`;
}

function formatDepartureTime(dateString: string): string {
  const [year, month, day] = dateString.split('-');
  if (!year || !month || !day) return '待确认';
  return `${Number(month)}月${Number(day)}日`;
}

function mapBudgetLabel(range: string): string {
  if (range === 'low') return '低预算';
  if (range === 'high') return '高预算';
  return '中等预算';
}

function resolveOrigin(parsedOrigin: string | null | undefined, currentOrigin: string, userEdited: boolean): string {
  if (userEdited && currentOrigin.trim()) return currentOrigin.trim();
  return (parsedOrigin || currentOrigin || DEFAULT_ORIGIN).trim() || DEFAULT_ORIGIN;
}

function resolveDestination(parsedDestination: string | null | undefined, currentDestination: string, userEdited: boolean): string {
  if (userEdited && currentDestination.trim()) return currentDestination.trim();
  return (parsedDestination || currentDestination || '').trim() || parsedDestination || '';
}

function replaceTitleCity(title: string, parsedDestination: string, destination: string): string {
  if (!destination) return title;
  if (parsedDestination && title.includes(parsedDestination)) {
    return title.replace(parsedDestination, destination);
  }
  return `${destination}旅行方案`;
}

function buildManualPayload(
  origin: string,
  destination: string,
  dateRange: [Dayjs, Dayjs] | null,
  budgetRange: string,
  transportPreference: string,
) {
  const start = dateRange?.[0] ?? dayjs();
  const end = dateRange?.[1] ?? start.add(2, 'day');
  const city = destination.trim() || '目的地';
  return {
    title: `${city}旅行方案`,
    origin: origin.trim() || DEFAULT_ORIGIN,
    city,
    start_date: start.format('YYYY-MM-DD'),
    end_date: end.format('YYYY-MM-DD'),
    budget_range: budgetRange || 'medium',
    transport_preference: transportPreference || 'public_transit',
    accommodation_preference: 'comfort',
    notes: '',
    duration: formatDuration(start.format('YYYY-MM-DD'), end.format('YYYY-MM-DD')),
  };
}




