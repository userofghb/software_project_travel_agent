import React, { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Typography, Card, Row, Col, Space, Tag, Divider, Slider, Switch, message, Button, Input } from 'antd';
import { 
  Radar, 
  RadarChart, 
  PolarGrid, 
  PolarAngleAxis, 
  ResponsiveContainer, 
  PolarRadiusAxis 
} from 'recharts';
import { 
  User, 
  Settings, 
  Save, 
  Plus, 
  X, 
  Wallet, 
  Bus, 
  Home, 
  SunSnow, 
  Activity 
} from 'lucide-react';
import { motion } from 'framer-motion';
import { fetchMyProfile, updateMyInterestTags, updateMyProfile } from '../api/profile';
import { ApiError } from '../api/client';
import type { UserProfileResponse, UserProfileUpdateRequest } from '../api/types';

const { Title, Text, Paragraph } = Typography;

type ProfileFormState = {
  travelStyle: string;
  interestTags: string[];
  budgetScore: number;
  paceScore: number;
  riskScore: number;
  preferPublicTransit: boolean;
  acceptLongWalk: boolean;
  mustHaveBreakfast: boolean;
  preferHomestay: boolean;
};

const DEFAULT_PAYLOAD: UserProfileUpdateRequest = {
  travel_style: 'leisure',
  budget_level: 'medium',
  interest_tags: [],
  transport_preference: 'public_transit',
  accommodation_preference: 'comfort',
  risk_sensitivity: 'medium',
  pace_preference: 'balanced',
};

function mapBudgetLevelToScore(level: string): number {
  const normalized = (level || '').toLowerCase();
  if (normalized.includes('low') || normalized.includes('economy') || normalized.includes('budget')) return 20;
  if (normalized.includes('high') || normalized.includes('luxury') || normalized.includes('premium')) return 90;
  return 60;
}

function mapScoreToBudgetLevel(score: number): string {
  if (score < 34) return 'low';
  if (score < 67) return 'medium';
  return 'high';
}

function mapPacePreferenceToScore(pace: string): number {
  const normalized = (pace || '').toLowerCase();
  if (normalized.includes('relaxed') || normalized.includes('leisure') || normalized.includes('slow')) return 20;
  if (normalized.includes('intensive') || normalized.includes('fast') || normalized.includes('adventure')) return 90;
  return 50;
}

function mapScoreToPacePreference(score: number): string {
  if (score < 34) return 'relaxed';
  if (score < 67) return 'balanced';
  return 'intensive';
}

function mapRiskSensitivityToScore(risk: string): number {
  const normalized = (risk || '').toLowerCase();
  if (normalized.includes('low') || normalized.includes('insensitive')) return 20;
  if (normalized.includes('high') || normalized.includes('sensitive')) return 90;
  return 50;
}

function mapScoreToRiskSensitivity(score: number): string {
  if (score < 34) return 'low';
  if (score < 67) return 'medium';
  return 'high';
}

function parseTransportPreference(value: string): { preferPublicTransit: boolean; acceptLongWalk: boolean } {
  const normalized = (value || '').toLowerCase();
  const preferPublicTransit = normalized.includes('public') || normalized.includes('transit') || normalized.includes('metro') || normalized.includes('bus');
  const acceptLongWalk = normalized.includes('walk') || normalized.includes('nearby') || normalized.includes('foot');
  return { preferPublicTransit, acceptLongWalk };
}

function buildTransportPreference(preferPublicTransit: boolean, acceptLongWalk: boolean): string {
  if (preferPublicTransit && acceptLongWalk) return 'walk_or_nearby';
  if (preferPublicTransit) return 'public_transit';
  if (acceptLongWalk) return 'mixed_walk';
  return 'private_transport';
}

function parseAccommodationPreference(value: string): { mustHaveBreakfast: boolean; preferHomestay: boolean } {
  const normalized = (value || '').toLowerCase();
  const mustHaveBreakfast = normalized.includes('breakfast');
  const preferHomestay = normalized.includes('homestay');
  return { mustHaveBreakfast, preferHomestay };
}

function buildAccommodationPreference(mustHaveBreakfast: boolean, preferHomestay: boolean): string {
  if (mustHaveBreakfast && preferHomestay) return 'homestay_with_breakfast';
  if (mustHaveBreakfast) return 'hotel_with_breakfast';
  if (preferHomestay) return 'homestay';
  return 'comfort';
}

function createFormState(profile: UserProfileUpdateRequest): ProfileFormState {
  const transportFlags = parseTransportPreference(profile.transport_preference);
  const accommodationFlags = parseAccommodationPreference(profile.accommodation_preference);
  return {
    travelStyle: profile.travel_style ?? 'leisure',
    interestTags: profile.interest_tags ?? [],
    budgetScore: mapBudgetLevelToScore(profile.budget_level ?? 'medium'),
    paceScore: mapPacePreferenceToScore(profile.pace_preference ?? 'balanced'),
    riskScore: mapRiskSensitivityToScore(profile.risk_sensitivity ?? 'medium'),
    preferPublicTransit: transportFlags.preferPublicTransit,
    acceptLongWalk: transportFlags.acceptLongWalk,
    mustHaveBreakfast: accommodationFlags.mustHaveBreakfast,
    preferHomestay: accommodationFlags.preferHomestay,
  };
}

function buildRadarData(formState: ProfileFormState) {
  const text = formState.interestTags.join(',').toLowerCase();
  const has = (keywords: string[]) => keywords.some((kw) => text.includes(kw));

  const food = has(['food', 'eat', '美食', '小吃', '火锅']) ? 90 : 55;
  const nature = has(['nature', 'mountain', 'hiking', '自然', '山']) ? 85 : 50;
  const history = has(['history', 'museum', '文化', '历史', '古']) ? 85 : 50;
  const shopping = has(['shopping', 'mall', '购物']) ? 80 : 40;
  const relax = Math.max(15, Math.min(95, 100 - formState.paceScore + 20));
  const extreme = Math.max(10, Math.min(95, formState.paceScore - 10));

  return [
    { subject: '美食探索', A: food, fullMark: 100 },
    { subject: '自然风光', A: nature, fullMark: 100 },
    { subject: '历史人文', A: history, fullMark: 100 },
    { subject: '购物打卡', A: shopping, fullMark: 100 },
    { subject: '休闲放松', A: relax, fullMark: 100 },
    { subject: '极限运动', A: extreme, fullMark: 100 },
  ];
}

export function ProfilePage() {
  const profileQuery = useQuery({
    queryKey: ['profile', 'me'],
    queryFn: fetchMyProfile,
  });
  const [formState, setFormState] = useState<ProfileFormState>(createFormState(DEFAULT_PAYLOAD));
  const [profileSummary, setProfileSummary] = useState('');
  const [isEditingTags, setIsEditingTags] = useState(false);
  const [newTagInput, setNewTagInput] = useState('');

  const saveMutation = useMutation({
    mutationFn: updateMyProfile,
    onSuccess: (res) => {
      setProfileSummary(res.profile_summary || '');
      setFormState(createFormState(res.profile));
      message.success('偏好画像保存成功，将在下次规划时生效');
    },
    onError: (err) => {
      message.error(err instanceof ApiError ? err.message : '保存失败，请稍后重试');
    },
  });
  const updateInterestTagsMutation = useMutation({
    mutationFn: updateMyInterestTags,
    onSuccess: (res) => {
      setFormState((prev) => ({ ...prev, interestTags: res.interest_tags }));
      setProfileSummary(res.profile_summary || '');
      message.success('兴趣标签已更新');
    },
    onError: (err) => {
      message.error(err instanceof ApiError ? err.message : '兴趣标签更新失败，请稍后重试');
    },
  });

  useEffect(() => {
    const data = profileQuery.data as UserProfileResponse | undefined;
    if (!data) return;
    setFormState(createFormState(data.profile));
    setProfileSummary(data.profile_summary || '');
  }, [profileQuery.data]);

  const radarData = useMemo(() => buildRadarData(formState), [formState]);
  const interests = formState.interestTags.length > 0 ? formState.interestTags : ['暂无兴趣标签'];

  const handleAddInterestTag = () => {
    const tag = newTagInput.trim();
    if (!tag) return;
    if (formState.interestTags.includes(tag)) {
      message.warning('该标签已存在');
      return;
    }
    const nextTags = [...formState.interestTags, tag];
    setFormState((prev) => ({ ...prev, interestTags: nextTags }));
    setNewTagInput('');
    updateInterestTagsMutation.mutate({ interest_tags: nextTags });
  };

  const handleRemoveInterestTag = (tagToRemove: string) => {
    const nextTags = formState.interestTags.filter((tag) => tag !== tagToRemove);
    setFormState((prev) => ({ ...prev, interestTags: nextTags }));
    updateInterestTagsMutation.mutate({ interest_tags: nextTags });
  };

  const handleSave = () => {
    const payload: UserProfileUpdateRequest = {
      travel_style: formState.travelStyle || 'leisure',
      budget_level: mapScoreToBudgetLevel(formState.budgetScore),
      interest_tags: formState.interestTags,
      transport_preference: buildTransportPreference(formState.preferPublicTransit, formState.acceptLongWalk),
      accommodation_preference: buildAccommodationPreference(formState.mustHaveBreakfast, formState.preferHomestay),
      risk_sensitivity: mapScoreToRiskSensitivity(formState.riskScore),
      pace_preference: mapScoreToPacePreference(formState.paceScore),
    };
    saveMutation.mutate(payload);
  };

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', paddingBottom: 40 }}>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Title level={2} style={{ margin: 0 }}>
            <Space>
              <User size={28} color="#eb2f96" />
              旅行偏好画像
            </Space>
          </Title>
          <Text type="secondary">您的偏好将作为 AI Agent 生成方案的核心基础</Text>
          {profileQuery.isError ? <Text type="danger" style={{ display: 'block' }}>画像加载失败，当前显示默认值</Text> : null}
        </div>
        <Button type="primary" icon={<Save size={16} />} size="large" style={{ borderRadius: 8 }} onClick={handleSave} loading={saveMutation.isPending}>
          保存画像
        </Button>
      </div>

      <Row gutter={24}>
        {/* Left Column: Radar and Interests */}
        <Col xs={24} md={10}>
          <Card bordered={false} style={{ borderRadius: 16, marginBottom: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <Title level={4} style={{ margin: 0 }}>兴趣雷达</Title>
              <Tag color="magenta" style={{ borderRadius: 12, border: 0 }}>实时更新</Tag>
            </div>
            <div style={{ height: 300, width: '100%', marginBottom: 16 }}>
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                  <PolarGrid />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: '#8c8c8c', fontSize: 12 }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                  <Radar name="User" dataKey="A" stroke="#eb2f96" fill="#eb2f96" fillOpacity={0.3} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
            
            <Divider orientation="left" plain>核心兴趣标签</Divider>
            <Space wrap>
              {interests.map((tag) => (
                <motion.div key={tag} whileHover={{ scale: 1.05 }}>
                  <Tag 
                    color="pink" 
                    style={{ 
                      padding: '4px 12px', 
                      borderRadius: 16, 
                      fontSize: 14, 
                      border: '1px solid #ffadd2',
                      background: '#fff0f6'
                    }}
                  >
                    {tag}
                    {isEditingTags && tag !== '暂无兴趣标签' ? (
                      <X
                        size={12}
                        style={{ marginLeft: 6, cursor: 'pointer', verticalAlign: 'middle' }}
                        onClick={() => handleRemoveInterestTag(tag)}
                      />
                    ) : null}
                  </Tag>
                </motion.div>
              ))}
              <Button type="dashed" size="small" style={{ borderRadius: 16 }} icon={<Settings size={12} />} onClick={() => setIsEditingTags((prev) => !prev)}>
                {isEditingTags ? '完成' : '编辑'}
              </Button>
              {isEditingTags ? (
                <Space size={8}>
                  <Input
                    size="small"
                    placeholder="新增兴趣标签"
                    value={newTagInput}
                    onChange={(e) => setNewTagInput(e.target.value)}
                    onPressEnter={handleAddInterestTag}
                    style={{ width: 160, borderRadius: 16 }}
                  />
                  <Button
                    size="small"
                    type="primary"
                    icon={<Plus size={12} />}
                    style={{ borderRadius: 16 }}
                    onClick={handleAddInterestTag}
                    loading={updateInterestTagsMutation.isPending}
                  >
                    新增
                  </Button>
                </Space>
              ) : null}
            </Space>
          </Card>

          <Card bordered={false} style={{ borderRadius: 16, background: 'linear-gradient(135deg, #f6ffed 0%, #d9f7be 100%)' }}>
            <Space align="start">
              <BotIcon size={24} color="#52c41a" />
              <div>
                <Title level={5} style={{ margin: 0, color: '#237804' }}>系统画像摘要</Title>
                <Paragraph style={{ margin: 0, marginTop: 8, color: '#389e0d' }}>
                  {profileSummary || '暂无画像摘要'}
                </Paragraph>
              </div>
            </Space>
          </Card>
        </Col>

        {/* Right Column: Detailed Preferences */}
        <Col xs={24} md={14}>
          <Card title="规划参数基准" bordered={false} style={{ borderRadius: 16 }}>
            <Row gutter={[24, 32]}>
              <Col span={12}>
                <div style={{ marginBottom: 8 }}>
                  <Text strong><Space><Wallet size={16} /> 预算敏感度</Space></Text>
                </div>
                <Slider value={formState.budgetScore} marks={{ 0: '穷游', 50: '适中', 100: '奢华' }} onChange={(value) => setFormState((prev) => ({ ...prev, budgetScore: typeof value === 'number' ? value : prev.budgetScore }))} />
              </Col>
              
              <Col span={12}>
                <div style={{ marginBottom: 8 }}>
                  <Text strong><Space><Activity size={16} /> 行程节奏</Space></Text>
                </div>
                <Slider value={formState.paceScore} marks={{ 0: '轻松', 50: '适中', 100: '特种兵' }} onChange={(value) => setFormState((prev) => ({ ...prev, paceScore: typeof value === 'number' ? value : prev.paceScore }))} />
              </Col>

              <Col span={12}>
                <div style={{ marginBottom: 8 }}>
                  <Text strong><Space><SunSnow size={16} /> 天气敏感度</Space></Text>
                </div>
                <Slider value={formState.riskScore} marks={{ 0: '无所谓', 50: '一般', 100: '高度敏感' }} onChange={(value) => setFormState((prev) => ({ ...prev, riskScore: typeof value === 'number' ? value : prev.riskScore }))} />
                <Text type="secondary" style={{ fontSize: 12 }}>分数越高，AI 越倾向于避开恶劣天气安排室外活动。</Text>
              </Col>
            </Row>

            <Divider dashed />

            <Row gutter={[24, 24]}>
              <Col span={12}>
                <Card size="small" type="inner" title={<Space><Bus size={16}/> 交通偏好</Space>} style={{ background: '#fafafa' }}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Text>优先公共交通</Text>
                      <Switch checked={formState.preferPublicTransit} onChange={(checked) => setFormState((prev) => ({ ...prev, preferPublicTransit: checked }))} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Text>接受长时间步行</Text>
                      <Switch checked={formState.acceptLongWalk} onChange={(checked) => setFormState((prev) => ({ ...prev, acceptLongWalk: checked }))} />
                    </div>
                  </Space>
                </Card>
              </Col>
              
              <Col span={12}>
                <Card size="small" type="inner" title={<Space><Home size={16}/> 住宿偏好</Space>} style={{ background: '#fafafa' }}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Text>必须含早餐</Text>
                      <Switch checked={formState.mustHaveBreakfast} onChange={(checked) => setFormState((prev) => ({ ...prev, mustHaveBreakfast: checked }))} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Text>偏好特色民宿</Text>
                      <Switch checked={formState.preferHomestay} onChange={(checked) => setFormState((prev) => ({ ...prev, preferHomestay: checked }))} />
                    </div>
                  </Space>
                </Card>
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>
    </div>
  );
}

const BotIcon = ({ size, color }: { size: number, color: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="10" rx="2" />
    <circle cx="12" cy="5" r="2" />
    <path d="M12 7v4" />
    <line x1="8" y1="16" x2="8" y2="16" />
    <line x1="16" y1="16" x2="16" y2="16" />
  </svg>
);
