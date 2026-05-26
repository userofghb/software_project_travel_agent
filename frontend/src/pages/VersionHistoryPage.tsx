import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Card, Col, Divider, Empty, message, Row, Space, Spin, Tag, Timeline, Typography } from 'antd';
import { useSearchParams } from 'react-router-dom';
import { Bot, GitCommit, GitMerge, Minus, Plus, RefreshCw, TrendingDown, TrendingUp, User } from 'lucide-react';
import { motion } from 'framer-motion';

import { getPlanSummary, listPlanVersions, restorePlanVersion } from '../api/plans';
import type { TripPlanVersionResponse } from '../api/types';

const { Title, Text } = Typography;

type UiVersion = {
  id: number;
  version: string;
  source: string;
  createdAtText: string;
  summary: string;
  raw: TripPlanVersionResponse;
};

type VersionDiff = {
  budgetChange: number | null;
  risk: string;
  pace: string;
  added: string[];
  removed: string[];
  reordered: boolean;
};

export function VersionHistoryPage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const planIdNumber = Number(searchParams.get('planId'));
  const validPlanId = Number.isFinite(planIdNumber) && planIdNumber > 0;
  const [activeVersionId, setActiveVersionId] = useState<number | null>(null);

  const versionsQuery = useQuery({
    queryKey: ['plan-versions', planIdNumber],
    queryFn: () => listPlanVersions(planIdNumber),
    enabled: validPlanId,
  });

  const summaryQuery = useQuery({
    queryKey: ['plan-summary', planIdNumber],
    queryFn: () => getPlanSummary(planIdNumber),
    enabled: validPlanId,
  });

  const restoreMutation = useMutation({
    mutationFn: ({ versionId }: { versionId: number }) => restorePlanVersion(planIdNumber, versionId),
    onSuccess: async () => {
      message.success('版本恢复成功');
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['plan-versions', planIdNumber] }),
        queryClient.invalidateQueries({ queryKey: ['plan-summary', planIdNumber] }),
        queryClient.invalidateQueries({ queryKey: ['plan', planIdNumber] }),
      ]);
    },
    onError: (err: Error) => {
      message.error(err.message || '版本恢复失败');
    },
  });

  const uiVersions = useMemo<UiVersion[]>(() => {
    const list = versionsQuery.data ?? [];
    return list.map((item) => ({
      id: item.id,
      version: `v${item.version_no}`,
      source: mapSourceTypeToChinese(item.source_type),
      createdAtText: formatDateTime(item.created_at),
      summary: item.change_summary || '无变更摘要',
      raw: item,
    }));
  }, [versionsQuery.data]);

  useEffect(() => {
    if (!uiVersions.length) {
      setActiveVersionId(null);
      return;
    }
    const exists = uiVersions.some((item) => item.id === activeVersionId);
    if (!exists) {
      setActiveVersionId(uiVersions[uiVersions.length - 1].id);
    }
  }, [uiVersions, activeVersionId]);

  const activeVersion = useMemo(() => uiVersions.find((item) => item.id === activeVersionId) ?? null, [uiVersions, activeVersionId]);
  const activeDiff = useMemo(() => buildVersionDiff(activeVersion?.raw ?? null, versionsQuery.data ?? []), [activeVersion, versionsQuery.data]);

  const headerTitle = summaryQuery.data?.title ?? '方案版本控制';
  const headerSubtitle = summaryQuery.data ? `${summaryQuery.data.city} - 版本演进历史` : '版本演进历史';

  if (!validPlanId) {
    return (
      <Alert
        type="warning"
        showIcon
        message="缺少方案 ID 参数"
        description="请从方案历史页点击查看版本进入，或在 URL 中附加 ?planId=数字。"
      />
    );
  }

  if (versionsQuery.isLoading || summaryQuery.isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
        <Spin />
      </div>
    );
  }

  if (versionsQuery.isError) {
    return <Alert type="error" showIcon message="版本列表加载失败" description={versionsQuery.error.message} />;
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', paddingBottom: 40 }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={2} style={{ margin: 0 }}>
          <Space>
            <GitMerge size={28} color="#722ed1" />
            方案版本控制
          </Space>
        </Title>
        <Text type="secondary">
          {headerTitle} - {headerSubtitle}
        </Text>
      </div>

      {uiVersions.length === 0 ? (
        <Card bordered={false} style={{ borderRadius: 16 }}>
          <Empty description="暂无版本记录" />
        </Card>
      ) : (
        <Row gutter={24}>
          <Col xs={24} md={8}>
            <Card bordered={false} style={{ borderRadius: 16, height: '100%' }}>
              <Timeline
                items={uiVersions.map((ver) => ({
                  color: ver.id === activeVersionId ? '#722ed1' : 'gray',
                  dot: <GitCommit size={16} color={ver.id === activeVersionId ? '#722ed1' : '#bfbfbf'} />,
                  children: (
                    <div
                      style={{
                        cursor: 'pointer',
                        padding: 12,
                        borderRadius: 8,
                        background: ver.id === activeVersionId ? '#f9f0ff' : 'transparent',
                        transition: 'all 0.3s',
                      }}
                      onClick={() => setActiveVersionId(ver.id)}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Text strong style={{ color: ver.id === activeVersionId ? '#722ed1' : 'inherit' }}>
                          {ver.version}
                        </Text>
                        <Tag color={isAiSource(ver.raw.source_type) ? 'cyan' : 'blue'} style={{ border: 0 }}>
                          {isAiSource(ver.raw.source_type) ? <Bot size={12} style={{ marginRight: 4 }} /> : <User size={12} style={{ marginRight: 4 }} />}
                          {ver.source}
                        </Tag>
                      </div>
                      <Text style={{ display: 'block', margin: '8px 0', fontSize: 13 }}>{ver.summary}</Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {ver.createdAtText}
                      </Text>
                    </div>
                  ),
                }))}
              />
            </Card>
          </Col>

          <Col xs={24} md={16}>
            {activeVersion == null ? null : (
              <motion.div key={activeVersion.id} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3 }}>
                <Card bordered={false} style={{ borderRadius: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                    <Title level={3} style={{ margin: 0 }}>
                      版本详情 {activeVersion.version}
                    </Title>
                    <Button
                      type="primary"
                      style={{ background: '#722ed1', borderColor: '#722ed1' }}
                      loading={restoreMutation.isPending}
                      onClick={() => restoreMutation.mutate({ versionId: activeVersion.id })}
                    >
                      恢复此版本
                    </Button>
                  </div>

                  <Row gutter={24} style={{ marginBottom: 24 }}>
                    <Col span={8}>
                      <Card size="small" style={{ background: '#fafafa', border: 'none' }}>
                        <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                          预算变化
                        </Text>
                        <Space align="center">
                          <Text strong style={{ fontSize: 20, color: budgetChangeColor(activeDiff.budgetChange) }}>
                            {formatBudgetChange(activeDiff.budgetChange)}
                          </Text>
                          {(activeDiff.budgetChange ?? 0) > 0 ? <TrendingUp color="#cf1322" size={16} /> : null}
                          {(activeDiff.budgetChange ?? 0) < 0 ? <TrendingDown color="#389e0d" size={16} /> : null}
                        </Space>
                      </Card>
                    </Col>
                    <Col span={8}>
                      <Card size="small" style={{ background: '#fafafa', border: 'none' }}>
                        <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                          天气风险评估
                        </Text>
                        <Tag color={getRiskTagColor(activeDiff.risk)}>{mapRiskToChinese(activeDiff.risk)}</Tag>
                      </Card>
                    </Col>
                    <Col span={8}>
                      <Card size="small" style={{ background: '#fafafa', border: 'none' }}>
                        <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                          行程强度
                        </Text>
                        <Text strong>{mapPaceToChinese(activeDiff.pace)}</Text>
                      </Card>
                    </Col>
                  </Row>

                  <Divider orientation="left" plain>
                    变更详情
                  </Divider>

                  <Row gutter={24}>
                    <Col span={12}>
                      <Card size="small" title={<Space><Plus size={16} color="#52c41a" /> 新增节点</Space>} style={{ border: '1px solid #b7eb8f', background: '#f6ffed' }}>
                        {activeDiff.added.length ? (
                          <ul style={{ margin: 0, paddingLeft: 20 }}>
                            {activeDiff.added.map((item) => <li key={item}>{item}</li>)}
                          </ul>
                        ) : (
                          <Text type="secondary">暂无新增</Text>
                        )}
                      </Card>
                    </Col>
                    <Col span={12}>
                      <Card size="small" title={<Space><Minus size={16} color="#f5222d" /> 移除节点</Space>} style={{ border: '1px solid #ffa39e', background: '#fff1f0' }}>
                        {activeDiff.removed.length ? (
                          <ul style={{ margin: 0, paddingLeft: 20 }}>
                            {activeDiff.removed.map((item) => <li key={item}>{item}</li>)}
                          </ul>
                        ) : (
                          <Text type="secondary">暂无移除</Text>
                        )}
                      </Card>
                    </Col>
                  </Row>

                  {activeDiff.reordered ? (
                    <div style={{ marginTop: 16, padding: 12, background: '#e6f7ff', border: '1px solid #91d5ff', borderRadius: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <RefreshCw size={16} color="#1890ff" />
                      <Text style={{ color: '#096dd9' }}>检测到行程顺序调整</Text>
                    </div>
                  ) : null}
                </Card>
              </motion.div>
            )}
          </Col>
        </Row>
      )}
    </div>
  );
}

function buildVersionDiff(version: TripPlanVersionResponse | null, versions: TripPlanVersionResponse[]): VersionDiff {
  const content = asRecord(version?.content_json);
  const parent = version?.parent_version_id ? versions.find((item) => item.id === version.parent_version_id) : null;
  const parentContent = asRecord(parent?.content_json);

  const budget = readEstimatedBudget(content);
  const parentBudget = readEstimatedBudget(parentContent);
  const currentTitles = extractActivityTitles(content);
  const parentTitles = extractActivityTitles(parentContent);

  return {
    budgetChange: budget == null || parentBudget == null ? null : budget - parentBudget,
    risk: inferRisk(content),
    pace: inferPace(content),
    added: currentTitles.filter((item) => !parentTitles.includes(item)),
    removed: parentTitles.filter((item) => !currentTitles.includes(item)),
    reordered: parentTitles.length > 0 && currentTitles.length > 0 && parentTitles.join('|') !== currentTitles.filter((item) => parentTitles.includes(item)).join('|'),
  };
}

function readEstimatedBudget(content: Record<string, unknown>): number | null {
  const budget = asRecord(content.budget);
  const value = budget.estimated_total;
  return typeof value === 'number' ? value : null;
}

function extractActivityTitles(content: Record<string, unknown>): string[] {
  const days = Array.isArray(content.days) ? content.days : [];
  return days.flatMap((day) => {
    const activities = asRecord(day).activities;
    if (!Array.isArray(activities)) return [];
    return activities.map((activity) => String(asRecord(activity).title ?? '')).filter(Boolean);
  });
}

function inferRisk(content: Record<string, unknown>): string {
  const warnings = Array.isArray(content.warnings) ? content.warnings : [];
  if (warnings.some((item) => asRecord(item).level === 'high')) return 'high';
  if (warnings.length > 0) return 'medium';
  return 'low';
}

function inferPace(content: Record<string, unknown>): string {
  const days = Array.isArray(content.days) ? content.days : [];
  const counts = days
    .map((day) => asRecord(day).activities)
    .filter(Array.isArray)
    .map((activities) => activities.length);
  if (!counts.length) return 'relaxed';
  const avg = counts.reduce((sum, count) => sum + count, 0) / counts.length;
  if (avg >= 5) return 'intensive';
  if (avg >= 4) return 'balanced';
  return 'relaxed';
}

function mapSourceTypeToChinese(sourceType: string): string {
  if (sourceType === 'created') return 'AI 初始生成';
  if (sourceType === 'regenerated') return 'AI 重新生成';
  if (sourceType === 'edited') return '用户编辑';
  if (sourceType === 'restored') return '版本恢复';
  return `未知来源(${sourceType || '空'})`;
}

function isAiSource(sourceType: string): boolean {
  return sourceType === 'created' || sourceType === 'regenerated';
}

function mapRiskToChinese(value?: string): string {
  if (value === 'low') return '低';
  if (value === 'medium') return '中';
  if (value === 'high') return '高';
  return '暂缺';
}

function getRiskTagColor(value?: string): string {
  if (value === 'low') return 'green';
  if (value === 'medium') return 'orange';
  if (value === 'high') return 'red';
  return 'default';
}

function mapPaceToChinese(value?: string): string {
  if (value === 'relaxed') return '轻松';
  if (value === 'balanced') return '适中';
  if (value === 'intensive') return '紧凑';
  return value ?? '暂缺';
}

function formatBudgetChange(value: number | null): string {
  if (value == null) return '暂缺';
  if (value > 0) return `+${value}`;
  return String(value);
}

function budgetChangeColor(value: number | null): string {
  if (value == null || value === 0) return '#595959';
  return value > 0 ? '#cf1322' : '#389e0d';
}

function formatDateTime(value: string): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}
